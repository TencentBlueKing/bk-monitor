import logging
import time
from typing import Any, Dict, List, Tuple
from urllib import parse
from metadata.models import ResultTable
from django.db.models import Q
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from packages.monitor_web.data_explorer.event.constants import (
    DIMENSION_PREFIX,
    EVENT_FIELD_ALIAS,
    INNER_FIELD_TYPE_MAPPINGS,
    EventCategory,
)

logger = logging.getLogger(__name__)


def generate_file_download_response(file_content: str, file_name: str) -> HttpResponse:
    """生成一个带有文件内容和文件名的 HTTP 响应"""
    # 对文件名进行 URL 编码
    file_name = parse.quote(file_name, encoding="utf8")
    file_name = parse.unquote(file_name, encoding="ISO8859_1")
    response = HttpResponse(file_content)
    response["Content-Type"] = "application/x-msdownload"
    response["Content-Disposition"] = f'attachment; filename="{parse.quote(file_name, encoding="utf8")}"'
    return response


def get_q_from_query_config(query_config: Dict[str, Any]) -> QueryConfigBuilder:
    return (
        QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
        .table(query_config["table"])
        .time_field("time")
        .group_by(*query_config.get("group_by", []))
        .conditions(query_config.get("where", []))
        .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
        .query_string(query_config.get("query_string") or "")
    )


def get_data_labels_map(bk_biz_id: int, tables: List[str]) -> Dict[str, str]:
    data_labels_map = {}
    data_labels_queryset = (
        ResultTable.objects.filter(bk_biz_id__in=[0, bk_biz_id])
        .filter(Q(table_id__in=tables) | Q(data_label__in=tables))
        .values("table_id", "data_label")
    )
    for item in data_labels_queryset:
        data_labels_map[item["table_id"]] = item["data_label"]
        data_labels_map[item["data_label"]] = item["data_label"]
    return data_labels_map


def create_workload_info(origin_data, fields: []):
    return create_event_info(origin_data, fields, EventCategory.K8S_EVENT.value)


def create_host_info(origin_data, fields: []):
    return create_event_info(origin_data, fields, EventCategory.SYSTEM_EVENT.value)


def create_event_info(origin_data, fields: [], event_type):
    event_info = {}
    for field in fields:
        if field in INNER_FIELD_TYPE_MAPPINGS:
            event_info[field] = {"label": get_field_label(field, event_type), "value": origin_data.get(field, "")}
            continue
        event_info[field] = {"label": get_field_label(field, event_type), "value": get_dimension(origin_data, field)}
    return event_info


def get_dimension(origin_data: Dict[str, Any], field: str):
    return origin_data.get(f"{DIMENSION_PREFIX}{field}", "")


def get_field_alias(field, label) -> Tuple[str, str, int]:
    """
    获取字段别名
    """

    def get_index(_d: Dict[str, str], _name: str) -> int:
        try:
            return list(_d.keys()).index(_name)
        except ValueError:
            # 不存在则排到最后
            return len(_d.keys())

    data_label, filed_alias_dict = get_filed_alias_dict(field, label)
    alias = filed_alias_dict.get(field)
    if alias:
        return "{}（{}）".format(alias, field), data_label, get_index(EVENT_FIELD_ALIAS[data_label], field)

    return field, EventCategory.UNKNOWN_EVENT.value, 0


def get_filed_alias_dict(field, label: str) -> Tuple[str, Dict[str, str]]:
    if EVENT_FIELD_ALIAS[EventCategory.COMMON.value].get(field):
        data_label: str = EventCategory.COMMON.value
    else:
        data_label: str = label
    return data_label, EVENT_FIELD_ALIAS.get(data_label, {})


def get_field_label(field: str, data_label: str) -> str:
    _, filed_alias_dict = get_filed_alias_dict(field, data_label)
    return filed_alias_dict.get(f"{DIMENSION_PREFIX}{field}", field)


def generate_time_range(timestamp):
    one_hour_ms = 3600 * 1000
    # 没有时间戳，返回近一小时的时间范围
    if not timestamp:
        end_time = 1000 * int(time.time())
        start_time = end_time - one_hour_ms
        return start_time, end_time
    # 计算前一个小时和后一个小时的时间戳（以毫秒为单位）
    try:
        timestamp = int(timestamp)
    except ValueError as exc:
        logger.warning("failed to conversion time, err -> %s", exc)
        raise ValueError(_(f"类型转换失败: 无法将 '{timestamp}' 转换为整数"))
    start_time = timestamp - one_hour_ms
    end_time = timestamp + one_hour_ms
    return start_time, end_time
