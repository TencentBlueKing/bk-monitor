# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import time
from typing import Any, Dict, Iterable, List, Tuple
from urllib import parse

from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.cache import lru_cache_with_ttl
from core.drf_resource import api
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


def get_qs_from_req_data(req_data: Dict[str, Any]) -> UnifyQuerySet:
    return (
        UnifyQuerySet()
        # 事件检索场景，不需要 drop 最后一个点
        .time_align(False)
        .scope(bk_biz_id=req_data["bk_biz_id"])
        .start_time(1000 * req_data["start_time"])
        .end_time(1000 * req_data["end_time"])
    )


def get_data_labels_map(bk_biz_id: int, tables: Iterable[str]) -> Dict[str, str]:
    # 对 table 进行去重排序，提高缓存命中率
    return _get_data_labels_map(bk_biz_id, tuple(sorted(set(tables))))


@lru_cache_with_ttl(ttl=60 * 20, decision_to_drop_func=lambda v: not v)
def _get_data_labels_map(bk_biz_id: int, tables: Tuple[str, ...]) -> Dict[str, str]:
    return api.metadata.get_data_labels_map(bk_biz_id=bk_biz_id, table_or_labels=list(tables))


def create_workload_info(origin_data, fields: List[str]):
    return create_event_info(origin_data, fields, EventCategory.K8S_EVENT.value)


def create_host_info(origin_data, fields: List[str]):
    return create_event_info(origin_data, fields, EventCategory.SYSTEM_EVENT.value)


def create_cicd_info(origin_data, fields: List[str]):
    return create_event_info(origin_data, fields, EventCategory.CICD_EVENT.value)


def create_event_info(origin_data, fields: List[str], data_label: str):
    event_detail: Dict[str, Any] = {}
    for field in fields:
        event_display_item: Dict[str, Any] = {"label": get_field_label(field, data_label)}
        if field in INNER_FIELD_TYPE_MAPPINGS:
            event_display_item["value"] = origin_data.get(field, "")
        else:
            event_display_item["value"] = get_dimension(origin_data, field)

        # 为空返回 --，以优化前端展示
        event_display_item["alias"] = event_display_item["value"] or "--"
        event_detail[field] = event_display_item
    return event_detail


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


def get_field_label(field: str, data_label: str = "") -> str:
    # 去掉可能存在 dimensions 前缀
    if field.startswith(DIMENSION_PREFIX):
        field = field[len(DIMENSION_PREFIX) :]

    _, filed_alias_dict = get_filed_alias_dict(field, data_label)
    return filed_alias_dict.get(field, field)


def generate_time_range(timestamp):
    now_ms = 1000 * int(time.time())
    one_hour_ms = 3600 * 1000
    # 没有时间戳，返回近一小时的时间范围
    if not timestamp:
        end_time = now_ms
        start_time = end_time - one_hour_ms
        return start_time, end_time
    # 计算前一个小时和后一个小时（且不超过当前时间）的时间戳（以毫秒为单位）
    try:
        timestamp = int(timestamp)
    except ValueError as exc:
        logger.warning("failed to conversion time, err -> %s", exc)
        raise ValueError(_("类型转换失败: 无法将 '{}' 转换为整数").format(timestamp))
    start_time = timestamp - one_hour_ms
    end_time = timestamp + one_hour_ms

    if end_time > now_ms:
        end_time = 0

    return start_time, end_time
