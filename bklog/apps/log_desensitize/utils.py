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


def _get_ancestor_paths(configured_paths: set) -> set:
    """
    从配置路径集合中提取所有祖先路径。

    使用字符串表示的 dotted 路径。注意：路径字符串中的点同时承担「路径分隔符」
    和「key 名字面量点号」的双重语义，在 ES-flattened 格式的 dotted 键名
    存在歧义（例如 {"a.b": "scalar", "a": {"b": "secret"}}）。
    当前实现采用「最左匹配」策略：优先将点号视为分隔符。
    这是已知限制，详见文档。

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
    - 返回还原元数据，记录每个被展开节点的原始容器类型（完整路径粒度）
    - 对「无法解析 / 超限 / 超深」且存在子路径规则的字段执行 fail-closed（整体遮罩）
    - 深度超限时保留剩余子树，避免无关字段从结果中消失

    路径表示使用 dotted 字符串。点号同时承担路径分隔符和 key 名中点号字符
    的双重语义——这是已知限制（详见文档「点号歧义」章节）。
    ES-flattened 格式的 dotted 键名因与路径表示格式相同，恰好被兼容支持。

    :param data: 原始日志 dict
    :param configured_paths: 已配置脱敏规则的字段路径列表（dotted path）
    :param max_depth: 最大递归深度，超过则停止展开
    :param max_json_bytes: 单个 JSON 字符串最大解析字节数，超过则跳过
    :return: (expanded_dict, restore_metadata)
             expanded_dict: 扁平化后的 dotted-key dict
             restore_metadata: {full_path: {"type": "dict"|"json_string"|"scalar"}}
    """
    try:
        configured_paths = set(configured_paths or [])
        ancestor_paths = _get_ancestor_paths(configured_paths)
        expanded = {}
        restore_metadata = {}

        def _has_rules_at_or_below(path: str) -> bool:
            """判断某路径自身或其子孙路径是否配置了脱敏规则。"""
            if path in configured_paths:
                return True
            prefix = "{}.".format(path)
            return any(cp.startswith(prefix) for cp in configured_paths)

        def _mask(path: str, reason: str):
            """fail-closed：整体遮罩该字段。"""
            logger.warning(
                "path_aware_expand: mask field '%s' due to %s (has subpath rules)",
                path,
                reason,
            )
            expanded[path] = _MASKED_VALUE
            restore_metadata[path] = {"type": "scalar"}

        def _expand(node: dict, prefix: str = "", depth: int = 0):
            for _k, _v in node.items():
                current_path = _k if not prefix else "{}.{}".format(prefix, _k)

                # ------------------------------------------------------------------
                # 展开阶段冲突检测：同一 dotted 路径同时有两个来源
                #（如 dict 递归展开产生 "body.a.b"，而 JSON 中又一个字面 key "a.b"），
                # 这是 dotted string 路径表示的根本限制。
                # 策略：确定性保留先迭代的值，后来者跳过并记录 error。
                # 后续 _build_nested_dict 的冲突检测作为第二层防线。
                # ------------------------------------------------------------------
                if current_path in expanded:
                    logger.error(
                        "_expand: dotted-key conflict at '%s', "
                        "keeping existing, discarding new (key retains first-encountered "
                        "value due to dotted-key ambiguity)",
                        current_path,
                    )
                    continue

                if isinstance(_v, dict):
                    if depth + 1 > max_depth:
                        # 深度超限：保留整棵剩余子树，避免无关字段丢失（P1-1）
                        if _has_rules_at_or_below(current_path):
                            _mask(current_path, "exceeds max_depth")
                        else:
                            expanded[current_path] = _v
                            restore_metadata[current_path] = {"type": "dict"}
                        continue
                    restore_metadata[current_path] = {"type": "dict"}
                    _expand(_v, current_path, depth + 1)

                elif isinstance(_v, list):
                    # 数组作为整体值，不展开元素
                    expanded[current_path] = _v
                    restore_metadata[current_path] = {"type": "scalar"}

                elif isinstance(_v, str) and current_path in ancestor_paths:
                    # 候选 JSON object 字符串（仅对配置路径的祖先字段尝试解析）
                    stripped = _v.strip()
                    if len(_v.encode("utf-8")) > max_json_bytes:
                        # 超限：有子规则则 fail-closed（P0-1），否则保持原值
                        if _has_rules_at_or_below(current_path):
                            _mask(current_path, "exceeds max_json_bytes")
                        else:
                            expanded[current_path] = _v
                            restore_metadata[current_path] = {"type": "scalar"}
                        continue

                    if not (stripped.startswith("{") and stripped.endswith("}")):
                        # 去掉空白后仍非 object 形态，按普通标量处理
                        expanded[current_path] = _v
                        restore_metadata[current_path] = {"type": "scalar"}
                        continue

                    if _estimate_json_depth(stripped) > max_depth:
                        # 嵌套过深：预扫描拦截，避免 json.loads 触发 RecursionError（P0-2）
                        if _has_rules_at_or_below(current_path):
                            _mask(current_path, "JSON nesting exceeds max_depth")
                        else:
                            expanded[current_path] = _v
                            restore_metadata[current_path] = {"type": "scalar"}
                        continue

                    try:
                        parsed = json.loads(stripped)
                    except (json.JSONDecodeError, TypeError, ValueError, RecursionError):
                        # 解析失败：有子规则则 fail-closed，否则保持原值
                        if _has_rules_at_or_below(current_path):
                            _mask(current_path, "JSON parse failure")
                        else:
                            expanded[current_path] = _v
                            restore_metadata[current_path] = {"type": "scalar"}
                        continue

                    if isinstance(parsed, dict):
                        restore_metadata[current_path] = {"type": "json_string"}
                        _expand(parsed, current_path, depth + 1)
                    else:
                        # 解析结果不是 object（如数组、标量），保持原值
                        expanded[current_path] = _v
                        restore_metadata[current_path] = {"type": "scalar"}

                else:
                    # 标量值（str, int, float, bool, None）
                    expanded[current_path] = _v
                    restore_metadata[current_path] = {"type": "scalar"}

        _expand(data)
        return expanded, restore_metadata
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))


def _build_nested_dict(items: dict, prefix: str):
    """
    将带前缀的扁平 key-value 构建为嵌套 dict（相对 prefix）。

    例如: {"player.id": "123", "player.name": "abc"} → {"player": {"id": "123", "name": "abc"}}

    冲突处理：当同一位置既有标量值又需要构建子树时，
    采用「子树优先」策略——不向结果写入任何人工键，被降级的标量值直接丢失
    并记录 error 日志（已知限制）。不再使用 conflict_store 死代码。

    :param items: 以 prefix 为前缀的扁平 key-value
    :param prefix: 当前节点路径
    :return: 嵌套 dict
    """
    nested = {}
    for key, value in items.items():
        if key == prefix:
            continue
        if not key.startswith(prefix + "."):
            continue
        relative = key[len(prefix) + 1:]
        parts = relative.split(".")
        current = nested
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # 冲突：该位置已有标量，无法继续下钻；子树优先，标量丢失
                logger.error(
                    "_build_nested_dict: path conflict at '%s', subtree takes priority, scalar lost",
                    "{}.{}".format(prefix, part),
                )
                current[part] = {}
            current = current[part]
        last = parts[-1]
        if isinstance(current.get(last), dict):
            # 冲突：目标位置已构建子树，写标量会覆盖子树；子树优先，标量丢失
            logger.error(
                "_build_nested_dict: path conflict at '%s', subtree takes priority, scalar lost",
                "{}.{}".format(prefix, last),
            )
        else:
            current[last] = value

    return nested


def restore_by_metadata(expanded_data: dict, restore_metadata: dict) -> dict:
    """
    根据还原元数据将脱敏后的扁平 dict 还原为原始结构。

    与 merge_nested_data 的区别：
    - 以「完整路径」粒度的元数据决定每个节点的容器类型，支持内层 JSON 字符串类型保持（P1-2）
    - 自底向上折叠：先还原最深容器，逐层向上包裹
    - dict 类型 → 构建嵌套 dict
    - json_string 类型 → 构建嵌套 dict 后重新序列化为 JSON 字符串
    - scalar 类型 → 直接赋值
    - 无元数据的带点 key 默认按 dict 折叠（兼容旧行为）

    :param expanded_data: 脱敏后的扁平 dotted-key dict
    :param restore_metadata: path_aware_expand 返回的元数据
    :return: 还原后的 dict，结构与原始输入一致
    """
    try:
        result = dict(expanded_data or {})
        restore_metadata = restore_metadata or {}

        # 1. 收集所有容器节点（dict / json_string），按路径深度从深到浅处理
        container_paths = [
            path
            for path, meta in restore_metadata.items()
            if meta.get("type") in ("dict", "json_string")
        ]
        # 使用点号计数估算深度（已知限制：含点号 key 时精度偏差）。深的优先，
        # 同深度按字典序保证确定性。
        container_paths.sort(key=lambda p: (p.count("."), p), reverse=True)

        for path in container_paths:
            container_type = restore_metadata[path].get("type")
            prefix = path + "."
            descendant_keys = [k for k in list(result.keys()) if k.startswith(prefix)]
            if not descendant_keys:
                continue
            sub_map = {k: result.pop(k) for k in descendant_keys}
            nested = _build_nested_dict(sub_map, path)
            if container_type == "json_string":
                result[path] = json.dumps(nested, ensure_ascii=False)
            else:
                result[path] = nested

        # 2. 兜底：无容器元数据但仍带点的 key，默认按 dict 折叠
        dotted_keys = [k for k in list(result.keys()) if "." in k]
        if dotted_keys:
            groups = {}
            for k in dotted_keys:
                top = k.split(".", 1)[0]
                groups.setdefault(top, {})[k] = result.pop(k)
            for top, sub_map in groups.items():
                if top in result:
                    if isinstance(result[top], dict):
                        # top 已是 dict，将子路径折叠进去，不丢失数据
                        result[top].update(_build_nested_dict(sub_map, top))
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
                    result[top] = _build_nested_dict(sub_map, top)

        return result
    except Exception as e:
        raise DesensitizeDataErrorException(DesensitizeDataErrorException.MESSAGE.format(e=e))
