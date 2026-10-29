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
# fail-closed 整体遮罩字符串（当字段超限/超深/解析失败且存在子路径规则时使用）
_MASKED_VALUE = "***MASKED***"


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

    冲突处理：当同一位置既有标量值又需要构建子树时，子树优先，标量丢失并记录 error。
    被丢弃的标量值在 error 日志中包含 key 名，便于运维排查数据完整性问题。
    """
    try:
        merged_data = {}
        for key, value in data.items():
            keys = key.split(".")
            current = merged_data
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                elif not isinstance(current[k], dict):
                    # 冲突：该位置已有标量，子树优先
                    logger.error(
                        "merge_nested_data: path conflict at key '%s' "
                        "(scalar '%s' discarded, subtree takes priority)",
                        key,
                        current[k],
                    )
                    current[k] = {}
                current = current[k]
            # 写入最终值时也检测冲突
            last = keys[-1]
            if isinstance(current.get(last), dict):
                logger.error(
                    "merge_nested_data: path conflict at key '%s' "
                    "(scalar value discarded, subtree takes priority)",
                    key,
                )
            else:
                current[last] = value

        return merged_data
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _get_sensitive_top_fields(field_configs: list, text_fields_field_configs: list, text_fields: list) -> set:
    """从脱敏配置中提取需要遮罩的顶层字段名集合。

    将嵌套路径（如 body.player.id）的顶层前缀（body）纳入遮罩范围，
    保留时间戳、索引 ID 等元数据字段不受影响。

    :param field_configs: 结构化字段配置列表，每项含 field_name 键
    :param text_fields_field_configs: 原文字段配置列表
    :param text_fields: 原文字段名列表
    :return: 需要遮罩的顶层字段名集合
    """
    sensitive = {fc["field_name"].split(".")[0] for fc in (field_configs or [])}
    sensitive.update(fc["field_name"].split(".")[0] for fc in (text_fields_field_configs or []))
    sensitive.update(text_fields or [])
    return sensitive


def _mask_sensitive_fields(log: dict, sensitive_fields: set) -> dict:
    """对日志中属于敏感字段的键替换为遮罩值，保留其他字段。

    兼容两种 key 格式：
    - tuple（path token）：取 tuple[0]（顶层字段名）与 sensitive_fields 比较
    - string（原始格式）：直接匹配或取第一段（dotted key）

    :param log: 日志 dict（key 为 Tuple[str, ...] 或 str）
    :param sensitive_fields: 需要遮罩的顶层字段名集合（string）
    :return: 遮罩后的日志 dict
    """
    def _should_mask(key) -> bool:
        if isinstance(key, tuple):
            return key[0] in sensitive_fields
        # string key（兼容 merge_nested_data 失败时的原始格式）
        if key in sensitive_fields:
            return True
        return "." in key and key.split(".")[0] in sensitive_fields

    return {k: (_MASKED_VALUE if _should_mask(k) else v) for k, v in log.items()}


def _is_fail_closed(log: dict, restore_metadata: dict) -> bool:
    """检测 path_aware_expand 结果中是否存在 fail-closed 遮罩字段。

    必须在 transform_dict 之前调用：transform_dict 可能修改 _MASKED_VALUE
    值（如 mask_shield 算子将其变为 "*******ED***"），导致后续检测失效。

    :param log: path_aware_expand 返回的展开 dict
    :param restore_metadata: path_aware_expand 返回的元数据
    :return: 是否存在 fail-closed 遮罩
    """
    return any(
        log.get(path) == _MASKED_VALUE
        for path in restore_metadata
    )


def _estimate_json_depth(s: str) -> int:
    """
    通过扫描花括号估算 JSON 字符串的嵌套深度，不做完整解析，O(n) 单次扫描。

    作用范围：仅在确认字段为候选 JSON object 字符串、且未超过 max_json_bytes 后调用，
    用于在 json.loads 之前预判嵌套深度，避免极深 JSON 触发 Python 的 RecursionError。

    正确处理字符串内的引号转义（含连续反斜杠），避免把字符串值中的 { } 计入深度。

    :param s: 已验证形似 object 的 JSON 字符串（可含首尾空白）
    :return: 估算的最大嵌套深度
    """
    max_depth = 0
    current_depth = 0
    in_string = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            current_depth += 1
            if current_depth > max_depth:
                max_depth = current_depth
        elif ch == "}":
            # 防御非配对花括号（如 "}{"）导致的负深度
            current_depth = max(0, current_depth - 1)
    return max_depth


def _get_ancestor_tuples(configured_paths: set) -> set:
    """
    从配置路径集合中提取所有祖先路径的 tuple 表示。

    使用 path token（tuple）表示，彻底消除 dotted string 的点号歧义。

    例如: {"body.player.id"} → {("body",), ("body", "player")}

    :param configured_paths: 配置路径集合（dotted string）
    :return: 祖先路径的 tuple 集合
    """

    ancestors = set()
    for path in configured_paths:
        parts = path.split(".")
        for i in range(1, len(parts)):
            ancestors.add(tuple(parts[:i]))
    return ancestors


def path_aware_expand(
    data: dict,
    configured_paths: list,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_json_bytes: int = _DEFAULT_MAX_JSON_BYTES,
):
    """
    路径感知展开：根据已配置字段的祖先路径，解析必要的 JSON object 字符串，
    生成 path-token（tuple）视图供 transform_dict 匹配。

    与 expand_nested_data 的区别：
    - 仅对配置路径的祖先字段尝试 JSON object 字符串解析（非全量扫描）
    - 返回还原元数据，记录每个被展开节点的原始容器类型
    - 对「无法解析 / 超限 / 超深」且存在子路径规则的字段执行 fail-closed（整体遮罩）
    - 深度超限时保留剩余子树，避免无关字段从结果中消失

    路径表示使用 tuple（path token），每个元素是一个完整的路径段，
    彻底消除 dotted string 的点号歧义。

    ES-flattened 兼容：顶层 key（depth=0）中的点号视为路径分隔符（ES 打平结果），
    嵌套层（depth>0）和 JSON 解析结果中的 key 不 split（点号是字面量）。

    :param data: 原始日志 dict
    :param configured_paths: 已配置脱敏规则的字段路径列表（dotted path）
    :param max_depth: 最大递归深度，超过则停止展开
    :param max_json_bytes: 单个 JSON 字符串最大解析字节数，超过则跳过
    :return: (expanded_dict, restore_metadata)
             expanded_dict: Dict[Tuple[str, ...], Any]
             restore_metadata: Dict[Tuple[str, ...], dict]
    """
    try:
        configured_paths = set(configured_paths or [])
        configured_tuples = {tuple(cp.split(".")) for cp in configured_paths}
        ancestor_tuples = _get_ancestor_tuples(configured_paths)
        expanded: dict = {}
        restore_metadata: dict = {}

        def _has_rules_at_or_below(path_tuple: tuple) -> bool:
            """判断某路径自身或其子孙路径是否配置了脱敏规则。"""
            if path_tuple in configured_tuples:
                return True
            return any(
                len(ct) > len(path_tuple)
                and ct[:len(path_tuple)] == path_tuple
                for ct in configured_tuples
            )

        def _mask(path_tuple: tuple, reason: str):
            """fail-closed：整体遮罩该字段。"""
            logger.warning(
                "path_aware_expand: mask field '%s' due to %s (has subpath rules)",
                ".".join(path_tuple),
                reason,
            )
            expanded[path_tuple] = _MASKED_VALUE
            restore_metadata[path_tuple] = {"type": "scalar"}

        def _expand(node: dict, prefix_tuple: tuple = (), depth: int = 0, from_json: bool = False):
            """
            递归展开 dict 为扁平 path-token 视图。

            :param node: 当前层 dict
            :param prefix_tuple: 当前层的 path token 前缀
            :param depth: 当前递归深度
            :param from_json: 当前 node 是否来源于 JSON 字符串解析结果
            """
            for _k, _v in node.items():
                # ------------------------------------------------------------------
                # 路径分段：顶层 key（depth=0）且非 JSON 来源时，点号视为分隔符
                # ES-flattened 格式（如 "__ext_json.deployment.pod.name"）需要 split
                # 嵌套层（depth>0）和 JSON 解析结果中，key 中的点号是字面量
                # ------------------------------------------------------------------
                if depth == 0 and not from_json and "." in _k:
                    segment = tuple(_k.split("."))
                else:
                    segment = (_k,)
                current_tuple = prefix_tuple + segment

                # ------------------------------------------------------------------
                # 字面点号 key 内嵌 JSON 绕过检查
                # 当 key 含点号且 split 解释命中配置路径时：
                # - 值是非空 JSON dict → 内部字段无法被配置路径命中 → fail-closed
                # - 值是普通标量 → 保留（配置匹配的是嵌套 dict 路径，字面 key 是不同字段）
                # ------------------------------------------------------------------
                if "." in _k and not (depth == 0 and not from_json):
                    split_tuple = prefix_tuple + tuple(_k.split("."))
                    if _has_rules_at_or_below(split_tuple):
                        if isinstance(_v, str):
                            stripped = _v.strip()
                            if stripped.startswith("{") and stripped.endswith("}"):
                                try:
                                    parsed_check = json.loads(stripped)
                                    if isinstance(parsed_check, dict) and parsed_check:
                                        logger.warning(
                                            "path_aware_expand: literal dotted-key '%s' has "
                                            "config rules under split interpretation, "
                                            "fail-closed masking",
                                            ".".join(current_tuple),
                                        )
                                        expanded[current_tuple] = _MASKED_VALUE
                                        restore_metadata[current_tuple] = {"type": "scalar"}
                                        continue
                                except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
                                    pass

                # ------------------------------------------------------------------
                # 冲突检测（tuple 比较，无歧义；理论上不会触发，保留作为安全网）
                # ------------------------------------------------------------------
                if current_tuple in expanded:
                    logger.warning(
                        "path_aware_expand: path-token conflict at %s, fail-closed masking",
                        current_tuple,
                    )
                    expanded[current_tuple] = _MASKED_VALUE
                    restore_metadata[current_tuple] = {"type": "scalar"}
                    continue

                if isinstance(_v, dict):
                    if depth + 1 > max_depth:
                        if _has_rules_at_or_below(current_tuple):
                            _mask(current_tuple, "exceeds max_depth")
                        else:
                            expanded[current_tuple] = _v
                            restore_metadata[current_tuple] = {"type": "dict"}
                        continue
                    restore_metadata[current_tuple] = {"type": "dict"}
                    _expand(_v, current_tuple, depth + 1, from_json)

                elif isinstance(_v, list):
                    expanded[current_tuple] = _v
                    restore_metadata[current_tuple] = {"type": "scalar"}

                elif isinstance(_v, str) and current_tuple in ancestor_tuples:
                    stripped = _v.strip()
                    if len(_v.encode("utf-8")) > max_json_bytes:
                        if _has_rules_at_or_below(current_tuple):
                            _mask(current_tuple, "exceeds max_json_bytes")
                        else:
                            expanded[current_tuple] = _v
                            restore_metadata[current_tuple] = {"type": "scalar"}
                        continue

                    if not (stripped.startswith("{") and stripped.endswith("}")):
                        expanded[current_tuple] = _v
                        restore_metadata[current_tuple] = {"type": "scalar"}
                        continue

                    if _estimate_json_depth(stripped) > max_depth:
                        if _has_rules_at_or_below(current_tuple):
                            _mask(current_tuple, "JSON nesting exceeds max_depth")
                        else:
                            expanded[current_tuple] = _v
                            restore_metadata[current_tuple] = {"type": "scalar"}
                        continue

                    try:
                        parsed = json.loads(stripped)
                    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
                        if _has_rules_at_or_below(current_tuple):
                            _mask(current_tuple, "JSON parse failure")
                        else:
                            expanded[current_tuple] = _v
                            restore_metadata[current_tuple] = {"type": "scalar"}
                        continue

                    if isinstance(parsed, dict):
                        restore_metadata[current_tuple] = {"type": "json_string"}
                        _expand(parsed, current_tuple, depth + 1, from_json=True)
                    else:
                        expanded[current_tuple] = _v
                        restore_metadata[current_tuple] = {"type": "scalar"}

                else:
                    expanded[current_tuple] = _v
                    restore_metadata[current_tuple] = {"type": "scalar"}

        _expand(data)
        return expanded, restore_metadata
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _extract_value_by_path(data: dict, dotted_path: str):
    """从嵌套 dict / JSON 字符串中按 dotted path 提取原始值。

    用于 fail-closed 场景下从原始日志中恢复原始值，
    以便 text_fields 原文替换能获得正确的原始文本。

    当路径段的值为 JSON 字符串时自动解析（轻量模式），
    但不触发 fail-closed 遮罩逻辑。

    :param data: 原始日志 dict（未膨胀或膨胀前的副本）
    :param dotted_path: 点号分隔的路径（如 "body.player.id"）
    :return: 原始值，提取失败时返回 None
    """
    parts = dotted_path.split(".")
    current = data
    try:
        for part in parts:
            if isinstance(current, str):
                current = json.loads(current)
            current = current[part]
        return current
    except (KeyError, json.JSONDecodeError, TypeError, IndexError, RecursionError):
        return None


def _build_nested_dict(items: dict, prefix_tuple: tuple):
    """
    将 path-token key 的扁平 dict 构建为嵌套 dict（相对 prefix_tuple）。

    例如: {("player", "id"): "123", ("player", "name"): "abc"} → {"player": {"id": "123", "name": "abc"}}

    使用 path token 直接导航，无需从 metadata 读取 segments。
    tuple key 本身就是无歧义的路径表示，不会产生点号 split 问题。

    冲突处理：fail-closed——当同一位置既有标量值又需要构建子树时，
    将冲突位置整体遮罩为 ``***MASKED***``，不按输入顺序丢弃任何一方。

    :param items: 以 prefix_tuple 为前缀的扁平 key-value（key 为 tuple）
    :param prefix_tuple: 当前节点路径（tuple）
    :return: 嵌套 dict
    """
    prefix_len = len(prefix_tuple)
    nested = {}
    for key_tuple, value in items.items():
        if key_tuple == prefix_tuple:
            continue
        if len(key_tuple) <= prefix_len:
            continue
        if key_tuple[:prefix_len] != prefix_tuple:
            continue
        # 相对于 prefix 的剩余分段
        relative_segments = key_tuple[prefix_len:]
        current = nested
        conflicted = False
        for part in relative_segments[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # fail-closed：标量-子树冲突，整体遮罩
                logger.warning(
                    "_build_nested_dict: path conflict at '%s', fail-closed masking",
                    ".".join(key_tuple),
                )
                current[part] = _MASKED_VALUE
                conflicted = True
                break
            current = current[part]
        if conflicted:
            continue
        last = relative_segments[-1]
        if isinstance(current.get(last), dict):
            # fail-closed：子树-标量冲突，整体遮罩
            logger.warning(
                "_build_nested_dict: path conflict at '%s', fail-closed masking",
                ".".join(key_tuple),
            )
            current[last] = _MASKED_VALUE
        else:
            current[last] = value

    return nested


def restore_by_metadata(expanded_data: dict, restore_metadata: dict) -> dict:
    """
    根据还原元数据将脱敏后的扁平 path-token dict 还原为原始结构。

    与 merge_nested_data 的区别：
    - key 为 tuple（path token），无需从 metadata 读取 segments
    - 以「完整路径」粒度的元数据决定每个节点的容器类型，支持内层 JSON 字符串类型保持
    - 自底向上折叠：先还原最深容器，逐层向上包裹
    - dict 类型 → 构建嵌套 dict
    - json_string 类型 → 构建嵌套 dict 后重新序列化为 JSON 字符串
    - scalar 类型 → 直接赋值
    - 无元数据的多段 tuple key 默认按 dict 折叠（兼容旧行为）

    :param expanded_data: 脱敏后的扁平 path-token dict（key 为 Tuple[str, ...]）
    :param restore_metadata: path_aware_expand 返回的元数据（key 为 Tuple[str, ...]）
    :return: 还原后的 dict，结构与原始输入一致
    """
    try:
        result = dict(expanded_data or {})
        restore_metadata = restore_metadata or {}

        # 根据 tuple 前缀判断 key 是否为 ancestor 的后代
        def _is_descendant(key_tuple: tuple, ancestor_tuple: tuple) -> bool:
            """判断 key_tuple 是否为 ancestor_tuple 的后代（任意深度）。"""
            return len(key_tuple) > len(ancestor_tuple) and key_tuple[:len(ancestor_tuple)] == ancestor_tuple

        # 1. 收集所有容器节点（dict / json_string），按路径深度从深到浅处理
        container_paths = [
            path
            for path, meta in restore_metadata.items()
            if meta.get("type") in ("dict", "json_string")
        ]
        # 使用 tuple 长度作为深度。深的优先，同深度按字典序保证确定性。
        container_paths.sort(
            key=lambda p: (len(p), p),
            reverse=True,
        )

        for path in container_paths:
            container_type = restore_metadata[path].get("type")
            # 收集后代（基于 tuple 前缀判断）
            descendant_keys = [
                k for k in list(result.keys())
                if _is_descendant(k, path)
            ]
            if not descendant_keys:
                continue
            sub_map = {k: result.pop(k) for k in descendant_keys}
            nested = _build_nested_dict(sub_map, path)
            if container_type == "json_string":
                result[path] = json.dumps(nested, ensure_ascii=False)
            else:
                result[path] = nested

        # 2. 兜底：所有多段 tuple key（未被容器折叠的），按 top-level 分组折叠为嵌套 dict
        multi_seg_keys = [k for k in list(result.keys()) if isinstance(k, tuple) and len(k) > 1]
        if multi_seg_keys:
            groups = {}
            for k in multi_seg_keys:
                top = k[0]
                groups.setdefault(top, {})[k] = result.pop(k)
            for top, sub_map in groups.items():
                top_tuple = (top,)
                if top_tuple in result:
                    if isinstance(result[top_tuple], dict):
                        # top 已是 dict，将子路径折叠进去
                        result[top_tuple].update(_build_nested_dict(sub_map, top_tuple))
                    else:
                        # top 是标量，无法合并子路径；记录 warning，将子路径放回 result
                        logger.warning(
                            "restore_by_metadata: fallback merge skipped for '%s' "
                            "(scalar value), restoring %d descendant keys",
                            top,
                            len(sub_map),
                        )
                        for k, v in sub_map.items():
                            result[k] = v
                else:
                    result[top_tuple] = _build_nested_dict(sub_map, top_tuple)

        # 3. 还原为原始结构：将 tuple key 转为 string key
        # 内部处理用 tuple 消除歧义，最终还原为用户原始数据的 key 格式
        return {k if isinstance(k, str) else ".".join(k): v for k, v in result.items()}
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))
