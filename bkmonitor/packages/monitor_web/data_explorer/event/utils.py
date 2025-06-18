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
from typing import Any
from collections.abc import Iterable

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.cache import lru_cache_with_ttl
from core.drf_resource import api
from monitor_web.data_explorer.event.constants import (
    DIMENSION_PREFIX,
    EVENT_FIELD_ALIAS,
    INNER_FIELD_TYPE_MAPPINGS,
    EventCategory,
)

logger = logging.getLogger(__name__)


def is_dimensions(field: str) -> bool:
    """判断是否是维度字段"""
    # 如果是内置字段，不需要补充 dimensions.
    return field not in INNER_FIELD_TYPE_MAPPINGS


def format_field(field: str) -> str:
    """
    格式化字段名
    背景：在告警、API 层都将 DIMENSION_PREFIX 隐藏，新版事件检索沿用以保持向前兼容，在部分场景，例如 where 转 query_string，
         需要补充前缀。
    """
    if is_dimensions(field):
        return f"{DIMENSION_PREFIX}{field}"
    return field


def get_q_from_query_config(query_config: dict[str, Any]) -> QueryConfigBuilder:
    return (
        QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
        .table(query_config["table"])
        .time_field("time")
        .group_by(*query_config.get("group_by", []))
        .conditions(query_config.get("where", []))
        .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
        .query_string(query_config.get("query_string") or "")
    )


def get_qs_from_req_data(req_data: dict[str, Any]) -> UnifyQuerySet:
    return (
        UnifyQuerySet()
        # 事件检索场景，不需要 drop 最后一个点
        .time_align(False)
        .scope(bk_biz_id=req_data["bk_biz_id"])
        .start_time(1000 * req_data["start_time"])
        .end_time(1000 * req_data["end_time"])
    )


def get_data_labels_map(bk_biz_id: int, tables: Iterable[str]) -> dict[str, str]:
    # 对 table 进行去重排序，提高缓存命中率
    return _get_data_labels_map(bk_biz_id, tuple(sorted(set(tables))))


@lru_cache_with_ttl(ttl=60 * 20, decision_to_drop_func=lambda v: not v)
def _get_data_labels_map(bk_biz_id: int, tables: tuple[str, ...]) -> dict[str, str]:
    return api.metadata.get_data_labels_map(bk_biz_id=bk_biz_id, table_or_labels=list(tables))


def create_k8s_info(origin_data, fields: list[str]):
    return create_event_info(origin_data, fields, EventCategory.K8S_EVENT.value)


def create_host_info(origin_data, fields: list[str]):
    return create_event_info(origin_data, fields, EventCategory.SYSTEM_EVENT.value)


def create_cicd_info(origin_data, fields: list[str]):
    return create_event_info(origin_data, fields, EventCategory.CICD_EVENT.value)


def create_event_info(origin_data, fields: list[str], data_label: str):
    event_detail: dict[str, Any] = {}
    for field in fields:
        event_display_item: dict[str, Any] = {
            "label": get_field_label(field, data_label),
            "value": origin_data.get(format_field(field), ""),
        }

        # 为空返回 --，以优化前端展示
        event_display_item["alias"] = event_display_item["value"] or "--"
        event_detail[field] = event_display_item
    return event_detail


def get_field_alias(field, label) -> tuple[str, str, int]:
    """
    获取字段别名
    """

    def get_index(_d: dict[str, str], _name: str) -> int:
        try:
            return list(_d.keys()).index(_name)
        except ValueError:
            # 不存在则排到最后
            return len(_d.keys())

    data_label, filed_alias_dict = get_filed_alias_dict(field, label)
    alias = filed_alias_dict.get(field)
    if alias:
        return f"{alias}（{field}）", data_label, get_index(EVENT_FIELD_ALIAS[data_label], field)

    return field, EventCategory.UNKNOWN_EVENT.value, 0


def get_filed_alias_dict(field, label: str) -> tuple[str, dict[str, str]]:
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


class DescendingStr:
    """
    定义降序字符串类，用于支持字符串降序排序
    """

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        """
        降序，取反原来的比较顺序
        """
        return self.value > other.value


def sort_by_fields(data, fields, field_path=None):
    """
    对字典列表按照多个字段进行排序，支持字段名前加"-"表示降序
    支持从任意嵌套路径获取字段值

    :param data: 要排序的数据列表（字典列表）
    :param fields: 排序字段列表，如 ["time", "-event.count"]
    :param field_path: 字段值所在的嵌套路径，如 "origin_data"
    :return: 排序后的字典列表
    """

    def get_nested_value(item, path):
        """从嵌套字典中获取指定路径的值"""
        if not path or item is None:
            return None

        # 分割路径为多个部分
        parts = path.split(".")
        current = item
        for part in parts:
            current = current[part]
        return current

    def get_sort_key(item):
        key_parts = []

        for field in fields:
            # 判断是否降序
            is_descending = field.startswith("-")
            field_name = field[1:] if is_descending else field
            # 获取排序字段所在的字典
            base_data = get_nested_value(item, field_path) if field_path else item
            # 获取字段值
            value = base_data.get(field_name)

            # 处理降序
            if is_descending:
                # 处理数值类型
                if isinstance(value, int | float):
                    key_parts.append(-value)
                else:
                    # 处理字符串类型, 使用自定义类实现降序
                    key_parts.append(DescendingStr(value))
            else:
                key_parts.append(value)

        # 将排序的键组合成一个元组，排序时会按照元组中字段的顺序依次比较
        return tuple(key_parts)

    return sorted(data, key=get_sort_key)
