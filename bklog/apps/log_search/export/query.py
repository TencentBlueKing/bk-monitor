"""分片查询的时间范围与整包排序契约。"""

import copy
from datetime import datetime, timezone

from apps.api import UnifyQueryApi
from apps.log_search.constants import DorisFieldTypeEnum, ExportSearchType
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_unifyquery.handler.mapping import UnifyQueryMappingHandler


def snapshot_time_fields(handler, search_type):
    """按 query_list 顺序冻结真实时间字段；不能使用占位的 query.time_field。"""
    if search_type == ExportSearchType.SCENE:
        fields = [{"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"}]
    else:
        fields = [
            dict(zip(("name", "type", "unit"), UnifyQueryHandler.init_time_field(info["index_set_id"])))
            for info in handler.index_info_list
        ]
    for query, field in zip(handler.base_dict.get("query_list", []), fields):
        if field["type"] not in ("date", "date_nanos"):
            continue
        # 与路由注册一致：逻辑 date 使用毫秒，即使物理字段为 long，或配置未保存单位。
        if field["type"] == "date":
            field["unit"] = "millisecond"
        # Handler 的逻辑 date 可能实际是 long/date/date_nanos。复用 UQ 的 field_map 入口，
        # 在创建时确定字面量格式；否则 date_nanos 的数字转日期可能受 UQ 本地时区影响。
        params = {
            key: handler.base_dict[key]
            for key in ("bk_biz_id", "space_uid", "start_time", "end_time")
            if key in handler.base_dict
        }
        params.update({key: query[key] for key in ("data_source", "table_id", "table_id_conditions") if key in query})
        result = UnifyQueryApi.query_field_map(params)
        raw = result.get("data") or result.get("fields") or {}
        if isinstance(raw, list):
            physical_type = next(
                (item.get("field_type") for item in raw if item.get("field_name") == field["name"]), None
            )
        else:
            info = raw.get(field["name"], {})
            physical_type = info.get("type") or info.get("field_type")
        # Doris/BKDATA 可能返回原生 BIGINT、datetime(3)；复用现有映射，不把类型白名单局限为 ES。
        physical_type = physical_type.strip().lower() if isinstance(physical_type, str) else ""
        physical_type = DorisFieldTypeEnum.get_es_field_type({"field_type": physical_type})
        if physical_type not in ("long", "date", "date_nanos"):
            raise ValueError(f"无法确认导出时间字段 {field['name']} 的实际类型")
        field["type"] = UnifyQueryMappingHandler.normalize_dt_event_timestamp_field_type(field["name"], physical_type)
    return fields


def time_order(job):
    """只有每一路的真实时间字段都是主排序，才可以按时间拼接分片。"""
    order = job.base_dict.get("order_by", [])
    queries = job.base_dict.get("query_list", [])
    if not order or not queries:
        return None
    first = order[0]
    fields = job.search_params.get("export_time_fields")
    names = [field["name"] for field in fields] if fields else [q.get("field_name") for q in queries]
    if fields and len({(field["type"], field["unit"]) for field in fields}) > 1:
        # 不同单位的同名数值字段在 UQ 的全局排序中不具备可直接拼接的数值顺序。
        return None
    if not all(name == first.removeprefix("-") for name in names):
        return None
    return "desc" if first.startswith("-") else "asc"


def _time_value(milliseconds, field):
    if field["type"] == "date_nanos":
        seconds, remainder = divmod(milliseconds, 1000)
        return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + f".{remainder:03d}000000Z"
    if field["type"] == "date":
        # UQ 使用 epoch_millis，保留现有 date 查询的字面量格式。
        return str(milliseconds)
    unit = field["unit"]
    if unit == "second":
        # 整数秒时间字段：gte/lt 都向上取整，子秒边界不会重复命中同一秒。
        return str(-(-milliseconds // 1000))
    return str(milliseconds * {"millisecond": 1, "microsecond": 1000, "nanosecond": 1_000_000}[unit])


def apply_time_range(params, fields, start, end):
    """保留毫秒包络，再用真实字段的标准 gte/lt 条件精确表达 [start, end)。

    UQ 顶层时间过滤是闭区间，减 1ms 会漏微秒日志；改传微秒又影响混合 date 路由。
    每一路独立添加边界，统计、采样与实际拉取使用完全相同的范围。
    """
    params.update(start_time=str(start), end_time=str(end))
    queries = params.get("query_list", [])
    if len(queries) != len(fields):
        raise ValueError("导出时间字段快照与查询路由不匹配")
    for query, field in zip(queries, fields):
        bounds = [
            {"field_name": field["name"], "op": op, "value": [_time_value(value, field)]}
            for op, value in (("gte", start), ("lt", end))
        ]
        conditions = query.get("conditions") or {}
        original = conditions.get("field_list", [])
        operators = conditions.get("condition_list", [])
        if len(operators) != max(0, len(original) - 1) or any(op not in ("and", "or") for op in operators):
            raise ValueError("导出查询条件结构不合法")
        # 原条件是 OR 分隔的 AND 组；给每组加边界，不能仅在末尾追加 AND。
        groups = [[]]
        for index, item in enumerate(original):
            if index and operators[index - 1] == "or":
                groups.append([])
            groups[-1].append(item)
        result_fields, result_operators = [], []
        for group in groups:
            if result_fields:
                result_operators.append("or")
            combined = group + copy.deepcopy(bounds)
            result_fields.extend(combined)
            result_operators.extend(["and"] * (len(combined) - 1))
        query["conditions"] = {"field_list": result_fields, "condition_list": result_operators}
