"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from bkmonitor.utils.cache import lru_cache_with_ttl, using_cache, CacheType
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


# 稳定的元数据，设置一个较长时间的 Redis 缓存，便于共享
@using_cache(CacheType.APM(60 * 60))
def get_cluster_table_map(cluster_ids: tuple[str, ...]) -> dict[str, str]:
    """获取集群 ID 到时间结果表的映射关系"""
    if not cluster_ids:
        return {}

    cluster_infos: list[dict[str, Any]] = api.metadata.list_bcs_cluster_info(cluster_ids=list(cluster_ids))
    cluster_to_data_id: dict[str, int] = {
        cluster_info["cluster_id"]: cluster_info["k8s_event_data_id"] for cluster_info in cluster_infos
    }
    # 业务场景不会超过一页，使用 single 接口避免多次请求
    event_groups: list[dict[str, Any]] = api.metadata.single_query_event_group(
        bk_data_ids=list(cluster_to_data_id.values())
    )
    data_id_table_map: dict[int, str] = {
        event_group["bk_data_id"]: event_group["table_id"] for event_group in event_groups
    }

    cluster_table_map: dict[str, str] = {}
    for cluster_id in cluster_to_data_id:
        table: str | None = data_id_table_map.get(cluster_to_data_id.get(cluster_id))
        if table:
            cluster_table_map[cluster_id] = table

    return cluster_table_map


def get_data_labels_map(bk_biz_id: int, tables: Iterable[str]) -> dict[str, str]:
    """
    获取结果表到数据标签的映射关系
    :param bk_biz_id: 业务 ID
    :param tables: 结果表
    :return:
    """
    if not tables:
        # 为空时提前返回，减少无效 IO。
        return {}

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


def sort_fields(records, fields, extractor=None):
    """
    对字典列表按照多个字段进行排序，支持字段名后加"desc"表示降序
    支持使用自定义提取器获取字段值

    :param records: 要排序的数据列表（字典列表）
    :param fields: 排序字段列表，如 ["time", "event.count desc"]
    :param extractor: 字段提取函数，用于从记录中提取基础数据字典
    :return: 排序后的字典列表
    """

    def get_sort_key(item):
        # 提取比较的字典数据
        base_data = extractor(item) if extractor else item
        keys = []
        for field in fields:
            # 解析字段和排序顺序
            if len(field.split()) == 1:
                field, order = field, "asc"
            else:
                field, order = field.split(maxsplit=1)

            value = base_data.get(field)
            # 用元组来控制 None 的排序顺序，None->(1,)，正常值：(0, value)，确保 None 在最后
            if value is None:
                keys.append((1,))
                continue

            # 升序处理
            if order != "desc":
                keys.append((0, value))
                continue

            # 降序处理
            if isinstance(value, int | float):
                keys.append((0, -value))
            else:
                keys.append((0, DescendingStr(value)))

        return tuple(keys)

    return sorted(records, key=get_sort_key)
