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

from apps.log_desensitize.exceptions import DesensitizeDataErrorException

logger = logging.getLogger(__name__)

# 默认最大递归深度
_DEFAULT_MAX_DEPTH = 10
# 默认单个 JSON 字符串最大解析字节数
_DEFAULT_MAX_JSON_BYTES = 65536


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


def merge_nested_data(data: dict):
    """
    将data中的object类型字段合并{"aaa.aa": 1, "aaa.bb": 2} -> {"aaa": {"aa": 1, "bb": 2}}
    """
    try:
        merged_data = {}
        for key, value in data.items():
            keys = key.split('.')
            current = merged_data
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value

        return merged_data
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _get_ancestor_paths(configured_paths: set) -> set:
    """
    从配置路径集合中提取所有祖先路径。

    例如: {"body.player.id"} → {"body", "body.player"}

    :param configured_paths: 配置路径集合
    :return: 祖先路径集合
    """

    ancestors = set()
    for path in configured_paths:
        parts = path.split(".")
        for i in range(1, len(parts)):
            ancestors.add(".".join(parts[:i]))
    return ancestors


def path_aware_expand(
    data: dict,
    configured_paths: list,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_json_bytes: int = _DEFAULT_MAX_JSON_BYTES,
):
    """
    路径感知展开：根据已配置字段的祖先路径，解析必要的 JSON object 字符串，
    生成 dotted-key 视图供 transform_dict 匹配。

    与 expand_nested_data 的区别：
    - 仅对配置路径的祖先字段尝试 JSON object 字符串解析（非全量扫描）
    - 返回还原元数据，记录每个顶层字段的原始容器类型

    :param data: 原始日志 dict
    :param configured_paths: 已配置脱敏规则的字段路径列表（dotted path）
    :param max_depth: 最大递归深度，超过则停止展开
    :param max_json_bytes: 单个 JSON 字符串最大解析字节数，超过则跳过
    :return: (expanded_dict, restore_metadata)
             expanded_dict: 扁平化后的 dotted-key dict
             restore_metadata: {top_level_key: {"type": "dict"|"json_string"|"scalar"}}
    """
    try:
        ancestor_paths = (
            _get_ancestor_paths(set(configured_paths)) if configured_paths else set()
        )
        expanded = {}
        restore_metadata = {}

        def _try_parse_json(current_path: str, value: str):
            """
            判断是否应该尝试解析该路径的 JSON 字符串。
            仅当路径在祖先路径集合中、未超过大小限制、且形似 JSON object 时返回 True。
            """
            if current_path not in ancestor_paths:
                return False
            if len(value.encode("utf-8")) > max_json_bytes:
                logger.warning(
                    "path_aware_expand: JSON string at path '%s' exceeds max_bytes=%d, skipping",
                    current_path,
                    max_json_bytes,
                )
                return False
            if not (value.startswith("{") and value.endswith("}")):
                return False
            return True

        def _expand(_data: dict, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            for _k, _v in _data.items():
                current_path = _k if not prefix else "{}.{}".format(prefix, _k)

                if isinstance(_v, dict):
                    if not prefix:
                        restore_metadata[_k] = {"type": "dict"}
                    _expand(_v, current_path, depth + 1)

                elif _try_parse_json(current_path, _v):
                    try:
                        parsed = json.loads(_v)
                        if isinstance(parsed, dict):
                            if not prefix:
                                restore_metadata[_k] = {"type": "json_string"}
                            _expand(parsed, current_path, depth + 1)
                        else:
                            # 解析结果不是 object（如数组、标量），保持原值
                            expanded[current_path] = _v
                    except (json.JSONDecodeError, TypeError, ValueError):
                        expanded[current_path] = _v

                elif isinstance(_v, list):
                    # 数组作为整体值，不展开元素
                    expanded[current_path] = _v
                    if not prefix:
                        restore_metadata[_k] = {"type": "scalar"}

                else:
                    # 标量值（str, int, float, bool, None）
                    expanded[current_path] = _v
                    if not prefix:
                        restore_metadata[_k] = {"type": "scalar"}

        _expand(data)
        return expanded, restore_metadata
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _build_nested_dict(items: dict, prefix: str):
    """
    将带前缀的扁平 key-value 构建为嵌套 dict。

    例如: {"player.id": "123", "player.name": "abc"} → {"player": {"id": "123", "name": "abc"}}
    如果 prefix 本身是标量值（无子路径），直接返回该值。
    """
    for key, value in items.items():
        if key == prefix:
            # 顶层 key 本身就是标量值，无子路径
            return value

    nested = {}
    for key, value in items.items():
        relative = key[len(prefix) + 1:]
        parts = relative.split(".")
        current = nested
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    return nested


def restore_by_metadata(expanded_data: dict, restore_metadata: dict) -> dict:
    """
    根据还原元数据将脱敏后的扁平 dict 还原为原始结构。

    与 merge_nested_data 的区别：
    - 根据元数据中记录的容器类型决定还原方式
    - dict 类型 → 构建嵌套 dict
    - json_string 类型 → 构建嵌套 dict 后重新序列化为 JSON 字符串
    - scalar 类型 → 直接赋值

    :param expanded_data: 脱敏后的扁平 dotted-key dict
    :param restore_metadata: path_aware_expand 返回的元数据
    :return: 还原后的 dict，结构与原始输入一致
    """
    try:
        # 收集所有顶层 key
        top_level_keys = set()
        for key in expanded_data:
            top_level_keys.add(key.split(".", 1)[0])

        result = {}
        for top_key in top_level_keys:
            meta = restore_metadata.get(top_key, {"type": "dict"})
            container_type = meta.get("type", "dict")

            # 获取该顶层 key 下的所有展开字段
            sub_items = {
                k: v
                for k, v in expanded_data.items()
                if k == top_key or k.startswith("{}.".format(top_key))
            }

            if container_type == "json_string":
                # 构建嵌套 dict 后序列化为 JSON 字符串
                nested = _build_nested_dict(sub_items, top_key)
                result[top_key] = json.dumps(nested, ensure_ascii=False)
            elif container_type == "scalar":
                # 标量值直接赋值
                result[top_key] = sub_items.get(top_key)
            else:
                # dict 类型：构建嵌套结构
                result[top_key] = _build_nested_dict(sub_items, top_key)

        return result
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))
