# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import json
import logging
from typing import Any, NamedTuple

from apps.log_desensitize.exceptions import DesensitizeDataErrorException

logger = logging.getLogger(__name__)

# 原文字段无法确认是否泄露时的整体遮罩值（fail-closed）
TEXT_FIELD_MASKED_VALUE = "***MASKED***"

# fail-closed 原因
FAIL_CLOSED_JSON_PARSE_FAILED = "json_parse_failed"
FAIL_CLOSED_JSON_TOO_DEEP = "json_too_deep"
FAIL_CLOSED_PARTIAL_LEAF_NOT_FOUND = "partial_leaf_not_found"

# 整字段规则做 JSON 叶子级回退时允许的最大嵌套层级，超过则 fail-closed
JSON_LEAF_MAX_DEPTH = 100


class JsonTooDeepError(Exception):
    """
    JSON 嵌套层级超过 JSON_LEAF_MAX_DEPTH
    """


class DesensitizeHit(NamedTuple):
    """
    字段脱敏时一次实际发生的替换，用于把脱敏结果同步到原文字段

    :param field: 展开后的字段名（字符串 key）
    :param value: 该字段脱敏前的原始值
    :param src: 被替换的原始子串（正则规则为命中片段，整字段规则为整个字段值的字符串）
    :param masked: 替换后的子串
    :param rules: 该字段使用的规则列表，用于整字段规则的 JSON 叶子级回退
    :param is_whole: 是否由整字段规则（未配置 match_pattern）产生
    """

    field: str
    value: Any
    src: str
    masked: str
    rules: list
    is_whole: bool


def expand_nested_data(data: dict):
    """
    递归将data中的object类型字段展开{"aaa": {"aa": 1, "bb": 2}} -> {"aaa.aa": 1, "aaa.bb": 2}
    """
    try:
        res_data = dict()

        def _expand(_data: dict, key: str = ""):
            for _k, _v in _data.items():
                _key = _k if not key else "{}.{}".format(key, _k)
                if not isinstance(_v, dict):
                    res_data[_key] = _v
                else:
                    _expand(_data[_k], _key)

        _expand(data)
        return res_data
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _has_prefix_conflict(data: dict) -> bool:
    """
    判断是否存在「键」与「以其为前缀的子路径」并存

    例如 {"a": 1, "a.b": 2}、{"a": {"c": 2}, "a.b": 1}：
    父键无论是标量还是对象，与子路径并存时折叠顺序会影响结果（覆盖或丢失），需要稳定排序
    """
    keys = set(data)
    dotted_keys = [key for key in keys if "." in key]
    if not dotted_keys:
        # 没有子路径就不可能与父键并存，快速短路
        return False

    for key in dotted_keys:
        parts = key.split(".")
        for index in range(1, len(parts)):
            if ".".join(parts[:index]) in keys:
                return True
    return False


def _clone_merge_value(value):
    """
    复制待写入的 dict 值，避免合并过程修改调用方传入的数据

    list 等非 dict 值按引用写入（与既有行为一致），只保证 dict 结构隔离
    """
    if isinstance(value, dict):
        return {key: _clone_merge_value(item) for key, item in value.items()}
    return value


def merge_nested_data(data: dict, on_conflict: str = "raise"):
    """
    将data中的object类型字段合并{"aaa.aa": 1, "aaa.bb": 2} -> {"aaa": {"aa": 1, "bb": 2}}

    无冲突时保持原始字段顺序；存在「键 + 子路径」并存时按点号段数稳定排序，
    保证「短 key 先于其子路径」、折叠结果与插入顺序无关。
    同层「标量键 + 同名前缀子路径」冲突时按 on_conflict 决定是抛异常还是保留扁平键。
    写入的 dict 值会递归复制，不会修改调用方传入的数据。

    :param data: 待合并的扁平字典
    :param on_conflict: 冲突处理方式
                        raise: 抛出 DesensitizeDataErrorException（默认）
                        keep: 保留冲突的扁平键并记录字段名，不中断检索
    :return: 合并后的嵌套字典
    """
    if on_conflict not in ("raise", "keep"):
        raise ValueError(f"invalid on_conflict: {on_conflict}")

    try:
        merged_data = {}
        # 无冲突时沿用原始顺序，不改变检索响应的字段顺序；
        # 存在「键 + 子路径」并存时排序，保证 raise / keep 两种模式的结果都与插入顺序无关
        if _has_prefix_conflict(data):
            keys_order = sorted(data, key=lambda item: item.count("."))
        else:
            keys_order = data

        for key in keys_order:
            value = data[key]
            keys = key.split('.')
            current = merged_data
            prefix_conflict = False
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                elif not isinstance(current[k], dict):
                    # 前缀已经是标量，无法继续向下建对象
                    prefix_conflict = True
                    break
                current = current[k]

            if prefix_conflict:
                if on_conflict == "raise":
                    raise DesensitizeDataErrorException(
                        DesensitizeDataErrorException.MESSAGE.format(e=f"prefix conflict: {key}")
                    )
                # 保留原始扁平键，避免字段丢失
                logger.warning("[desensitize] merge nested data conflict, keep flat key: %s", key)
                merged_data[key] = _clone_merge_value(value)
                continue

            current[keys[-1]] = _clone_merge_value(value)

        return merged_data
    except DesensitizeDataErrorException:
        raise
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _text_variants(text: str, masked: str) -> dict:
    """
    返回原文中可能出现的写法及其对应的脱敏写法

    覆盖：原样、JSON 转义（保留非 ASCII）、JSON 转义（\\u 编码），以及斜杠被转义为 \\/ 的写法

    :param text: 原始文本
    :param masked: 脱敏后的文本
    :return: {原文写法: 脱敏写法}
    """
    variants = {text: masked}
    for ensure_ascii in (False, True):
        escaped = json.dumps(text, ensure_ascii=ensure_ascii)[1:-1]
        escaped_masked = json.dumps(masked, ensure_ascii=ensure_ascii)[1:-1]
        variants.setdefault(escaped, escaped_masked)
        if "/" in escaped:
            variants.setdefault(escaped.replace("/", "\\/"), escaped_masked.replace("/", "\\/"))
    return variants


def _contains_any(text: str, source: str) -> bool:
    """
    判断原文中是否出现 source 的任一写法
    """
    return any(variant in text for variant in _text_variants(source, source))


def _add_replacements(replacements: dict, source: str, masked: str) -> None:
    """
    登记 source 各种写法的替换项，同一写法只登记第一次
    """
    for variant, variant_masked in _text_variants(source, masked).items():
        if variant:
            replacements.setdefault(variant, variant_masked)


def _value_texts(hit: DesensitizeHit) -> list:
    """
    整字段规则下，字段原始值在原文中可能的写法

    字符串直接使用原值；数字、布尔、列表等额外补充 JSON 写法（如 True -> true）
    """
    texts = [hit.src]
    if isinstance(hit.value, str):
        return texts
    try:
        dumped = json.dumps(hit.value, ensure_ascii=False)
    except (TypeError, ValueError):
        return texts
    if dumped not in texts:
        texts.append(dumped)
    return texts


def _load_json_container(value):
    """
    尝试把字段值解析为 JSON 容器

    :param value: 字段原始值
    :return: (container, failed)
             不像 JSON 时返回 (None, False)；像 JSON 但解析失败时返回 (None, True)
    """
    if isinstance(value, (dict, list)):
        return value, False
    if not isinstance(value, str):
        return None, False
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return None, False
    try:
        parsed = json.loads(stripped)
    except (ValueError, RecursionError):
        return None, True
    if isinstance(parsed, (dict, list)):
        return parsed, False
    return None, True


def _collect_json_leaves(data, leaves: list, depth: int = 0) -> None:
    """
    递归收集 JSON 容器中的叶子文本

    字符串取原值（跳过空串）；数字、布尔取 JSON 写法；null 跳过
    嵌套超过 JSON_LEAF_MAX_DEPTH 时抛出 JsonTooDeepError，不依赖解释器的递归上限
    """
    if isinstance(data, (dict, list)):
        if depth >= JSON_LEAF_MAX_DEPTH:
            raise JsonTooDeepError()
        items = data.values() if isinstance(data, dict) else data
        for item in items:
            _collect_json_leaves(item, leaves, depth + 1)
    elif isinstance(data, str):
        if data:
            leaves.append(data)
    elif data is not None:
        leaves.append(json.dumps(data))


def _build_text_replacements(text: str, hits: list, handler):
    """
    根据字段脱敏的命中记录，计算原文字段需要执行的替换

    :param text: 原文字段的值
    :param hits: 参与同步的 DesensitizeHit 列表
    :param handler: 字段脱敏使用的 DesensitizeHandler
    :return: (replacements, fail_reason, fail_field)，fail_reason 非空表示需要 fail-closed
    """
    replacements = {}
    for hit in hits:
        if not hit.is_whole:
            # 正则规则：替换实际命中的片段
            _add_replacements(replacements, hit.src, hit.masked)
            continue

        # 整字段规则：整段值能在原文中找到时直接替换
        value_texts = _value_texts(hit)
        if any(_contains_any(text, value_text) for value_text in value_texts):
            for value_text in value_texts:
                _add_replacements(replacements, value_text, hit.masked)
            continue

        # 整段值找不到：只有 JSON 容器才可能以其他格式出现在原文中
        container, failed = _load_json_container(hit.value)
        if failed:
            return {}, FAIL_CLOSED_JSON_PARSE_FAILED, hit.field
        if container is None:
            continue

        leaves = []
        try:
            _collect_json_leaves(container, leaves)
        except JsonTooDeepError:
            return {}, FAIL_CLOSED_JSON_TOO_DEEP, hit.field
        except RecursionError:
            return {}, FAIL_CLOSED_JSON_PARSE_FAILED, hit.field
        found_count = sum(1 for leaf in leaves if _contains_any(text, leaf))
        if not found_count:
            # 字段内容没有出现在原文中，不存在泄露
            continue
        if found_count != len(leaves):
            return {}, FAIL_CLOSED_PARTIAL_LEAF_NOT_FOUND, hit.field

        for leaf in dict.fromkeys(leaves):
            masked_leaf = handler.transform(log=leaf, rules=hit.rules)
            if masked_leaf != leaf:
                _add_replacements(replacements, leaf, masked_leaf)
    return replacements, None, None


def sync_text_fields(log: dict, text_fields: list, hits: list, handler, index_set_id=None) -> dict:
    """
    将其他字段的脱敏结果同步到原文字段，无法确认是否泄露时整体遮罩原文字段（fail-closed）

    - 正则规则：按实际命中的子串替换，不要求原文中出现完整的字段值
    - 整字段规则：整段值能找到时直接替换；值为 JSON 时按叶子替换；
      JSON 解析失败、或只有部分叶子出现在原文中时，原文字段整体替换为 TEXT_FIELD_MASKED_VALUE
    - 替换按原文写法长度从长到短执行，避免短值先替换截断长值

    :param log: expand_nested_data 展开后、已完成字段脱敏的日志（字符串 key）
    :param text_fields: 原文字段名列表
    :param hits: DesensitizeHandler.transform_dict 记录的 DesensitizeHit 列表
    :param handler: 字段脱敏使用的 DesensitizeHandler，用于整字段规则的叶子级回退
    :param index_set_id: 索引集 ID，仅用于 fail-closed 时的日志
    :return: 同步后的日志
    """
    if not log or not text_fields or not hits:
        return log

    sources = [hit for hit in hits if hit.field not in text_fields and hit.src]
    if not sources:
        return log

    for text_field in text_fields:
        text = log.get(text_field)
        if not isinstance(text, str) or not text:
            continue

        replacements, fail_reason, fail_field = _build_text_replacements(text, sources, handler)
        if fail_reason:
            # 只记录字段名与原因，不记录任何日志内容
            logger.warning(
                "[desensitize] text field fail-closed: index_set_id=%s, text_field=%s, source_field=%s, reason=%s",
                index_set_id,
                text_field,
                fail_field,
                fail_reason,
            )
            log[text_field] = TEXT_FIELD_MASKED_VALUE
            continue

        for source in sorted(replacements, key=len, reverse=True):
            text = text.replace(source, replacements[source])
        log[text_field] = text

    return log
