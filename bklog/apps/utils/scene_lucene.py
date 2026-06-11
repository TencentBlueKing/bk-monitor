# -*- coding: utf-8 -*-
"""
场景化检索的可读 query_string 拼装。

提供给收藏详情、列表、检索历史等多个调用方使用，避免拼装规则散落在
view 层。规则：
- table_id_conditions 仅过滤掉 scene 这个路由维度，其他维度（如 cluster_id）保留拼接
- 过滤掉 addition 中由"场景维度 key"派生的项，避免与 scene_filter_values 重复展示，
  同时兼容修复前持久化的脏 history（addition 中混入了 scene_filter_values 转换项）
"""

from apps.utils.lucene import generate_query_string


def _collect_scene_dimension_keys() -> set:
    """汇总所有场景定义中出现过的维度 key，用于识别 addition 中的场景维度过滤项。"""
    from apps.log_databus.constants import SCENE_SEARCH_DIMENSIONS

    keys = set()
    for dims in SCENE_SEARCH_DIMENSIONS.values():
        for d in dims or []:
            k = d.get("key")
            if k:
                keys.add(k)
    return keys


def format_table_id_conditions(tic) -> str:
    """二维数组（外层 OR、内层 AND）→ Lucene-like 字符串。

    历史预览中跳过 field_name='scene' 这一路由维度（对用户无信息量），
    其他维度（如 cluster_id 等）正常拼接。
    """
    if not tic:
        return ""
    or_groups = []
    for and_group in tic:
        parts = []
        for c in and_group:
            field = c.get("field_name", "")
            if not field or field == "scene":
                continue
            value_str = ",".join(map(str, c.get("value") or []))
            parts.append(f"{field} {c.get('op', 'eq')} {value_str}")
        if parts:
            or_groups.append(" AND ".join(parts))
    return ("(" + " OR ".join(f"({g})" for g in or_groups) + ")") if or_groups else ""


def format_scene_filter_values(filters) -> str:
    if not filters:
        return ""
    parts = [
        f"{f['field']} {f['operator']} {f.get('value', '')}"
        for f in filters
        if f.get("field") and f.get("operator")
    ]
    return ("(" + " AND ".join(parts) + ")") if parts else ""


def build_scene_query_string(params: dict) -> str:
    """场景化检索的可读预览。

    入参 params 可包含：
    - table_id_conditions: 路由条件
    - scene_filter_values: 场景维度筛选（同 addition 结构）
    - keyword/addition/ip_chooser/host_scopes: 标准 Lucene 条件
    """
    scene_keys = _collect_scene_dimension_keys()
    cleaned_params = dict(params)
    cleaned_params["addition"] = [
        a for a in (params.get("addition") or []) if (a.get("field") or "") not in scene_keys
    ]

    pieces = []
    tic = format_table_id_conditions(params.get("table_id_conditions"))
    if tic:
        pieces.append(tic)
    sfv = format_scene_filter_values(params.get("scene_filter_values"))
    if sfv:
        pieces.append(sfv)
    base = generate_query_string(cleaned_params)
    if base and base.strip():
        pieces.append(base)
    return " AND ".join(pieces) if pieces else "*"
