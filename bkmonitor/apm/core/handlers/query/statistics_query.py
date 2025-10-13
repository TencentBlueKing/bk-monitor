"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import hashlib
import json
import logging
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from opentelemetry.trace import StatusCode

from apm import types
from apm.constants import DISCOVER_BATCH_SIZE
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.core.handlers.query.base import BaseQuery, LogicSupportOperator
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.core.handlers.query.define import QueryStatisticsMode
from apm.core.handlers.query.span_query import SpanQuery
from apm.core.handlers.query.trace_query import TraceQuery
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey

logger = logging.getLogger("apm")

AFTER_CACHE_KEY_EXPIRE = 60 * 60 * 24 * 1


class Deque:
    def __init__(self, params_md5):
        deque_key = f"monitor:apm:statistics:deque:{params_md5}"
        self.cache_key = deque_key
        self.redis_client = ApmCacheHandler.get_redis_client()

    @property
    def length(self):
        if not self.redis_client.exists(self.cache_key):
            return 0

        return self.redis_client.llen(self.cache_key)

    def extend(self, item_list):
        json_list = [json.dumps(i) for i in item_list]
        self.redis_client.rpush(self.cache_key, *json_list)
        # 续期
        self.redis_client.expire(self.cache_key, AFTER_CACHE_KEY_EXPIRE)

    def popleft(self):
        """删除并返回队列头部元素"""
        item = self.redis_client.lpop(self.cache_key)
        if item:
            return ApmCacheHandler.decode_redis_value(item)
        return None

    def pop_data(self, limit):
        list_data = []
        if self.length == 0:
            return list_data

        for _i in range(limit):
            item = self.redis_client.lpop(self.cache_key)
            if item:
                list_data.append(item)

        decoded_data = []
        for i in list_data:
            decoded_value = ApmCacheHandler.decode_redis_value(i)
            decoded_data.append(json.loads(decoded_value))

        return decoded_data


class StatisticsQuery(BaseQuery):
    """TODO(crayon)：StatisticsQuery 已无页面功能引用，待删除。"""

    LOGIC_FILTER_ALLOW_KEYS = ["root_span", "root_service_span"]
    LOGIC_FILTER_KEY_MAPPING = {
        "root_span": {"span_name": "root_span_name", "service_name": "root_span_service", "kind": "root_span_kind"},
        "root_service_span": {
            "span_name": "root_service_span_name",
            "service_name": "root_service",
            "kind": "root_service_kind",
        },
    }
    LOGIC_FILTER_KEY_ID_MAPPING = {"root_span": "root_span_id", "root_service_span": "root_service_span_id"}

    # 当每批超过1000条数据时 需要进行并发查询
    SPLIT_SPAN_COUNT_SIZE_LIMIT = 1000
    # 需要将总数量切分几段出来
    SPLIT_SPAN_BATCH_SIZE = 5

    GROUP_MODE_KEY_MAPPING = {
        QueryStatisticsMode.SPAN_NAME: "span_name",
        QueryStatisticsMode.SERVICE: "resource.service.name",
    }

    GROUP_FIELD_CONFIG = {
        QueryStatisticsMode.SPAN_NAME: [
            {"field": "span_name", "display": "span_name"},
            {"field": "resource.service.name", "display": "service_name"},
            {"field": "kind", "display": "kind"},
        ],
        QueryStatisticsMode.SERVICE: [
            {"field": "resource.service.name", "display": "service_name"},
            {"field": "kind", "display": "kind"},
        ],
    }

    def __init__(self, trace_query: TraceQuery, span_query: SpanQuery):
        self.trace_query: TraceQuery = trace_query
        self.span_query: SpanQuery = span_query
        super().__init__(self.span_query.bk_biz_id, self.span_query.app_name, self.span_query.retention)

    def query_statistics(
        self,
        query_mode: str,
        start_time: int | None,
        end_time: int | None,
        limit: int,
        offset: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
        sort: list[str] | None = None,
    ):
        logic_fields, filters = self._parse_filters(filters)
        q: QueryConfigBuilder = self.q.filter(self._build_filters(filters)).order_by(
            *(sort or [f"{self.DEFAULT_TIME_FIELD} desc"])
        )
        if query_string:
            q = q.query_string(query_string)

        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time).limit(limit)

        k = f"{query_mode}:{queryset.query.start_time}{queryset.query.end_time}{limit}{filters}"
        params_key = str(hashlib.md5(k.encode()).hexdigest())
        queryset: UnifyQuerySet = queryset.after(self._get_after_key_param(offset, params_key))
        return self._query_data(query_mode, q, queryset, offset, params_key, logic_fields)

    def _query_data(
        self,
        query_mode: str,
        q: QueryConfigBuilder,
        queryset: UnifyQuerySet,
        offset: int,
        params_key: str,
        logic_fields: list[str],
    ):
        #  满足任一条件直接分组获取指标数据：不包含根 span、服务入口 span；查询统计视角为 service
        if not logic_fields or query_mode == QueryStatisticsMode.SERVICE:
            return self._query_metric_data(query_mode, q, queryset, offset, params_key)

        # step1 获取分组信息
        groups: list[dict[str, Any]] = self._query_groups(query_mode, q, queryset)
        # step2 获取 specific_span_ids
        specific_span_ids = self._batch_query_specific_span_ids(
            queryset.query.start_time, queryset.query.end_time, groups, logic_fields
        )
        # step3 从 span 中获取数据
        if not specific_span_ids:
            return []

        q: QueryConfigBuilder = q.filter(span_id__eq=specific_span_ids)
        return self._query_metric_data(query_mode, q, queryset, offset, params_key)

    def _query_groups(self, query_mode: str, q: QueryConfigBuilder, queryset: UnifyQuerySet) -> list[dict[str, Any]]:
        group_fields: list[str] = []
        field__display_map: dict[str, str] = {}
        for info in self.GROUP_FIELD_CONFIG[query_mode]:
            group_fields.append(info["field"])
            field__display_map[info["field"]] = info["display"]

        group_fields: list[str] = [info["field"] for info in self.GROUP_FIELD_CONFIG[query_mode]]
        # 这里的 count 仅仅是因为聚合需要传一个 metric，没有特殊含义
        q: QueryConfigBuilder = q.metric(field=group_fields[0], method="count").group_by(*group_fields)

        groups: list[dict[str, Any]] = []
        for bucket in queryset.add_query(q):
            groups.append({field__display_map[field]: bucket[field] for field in group_fields})
        return groups

    def _query_metric_data(
        self,
        query_mode: str,
        q: QueryConfigBuilder,
        queryset: UnifyQuerySet,
        offset: int,
        params_key: str,
    ) -> list[dict[str, Any]]:
        group_fields: list[str] = []
        field_display_map: dict[str, str] = {}
        for info in self.GROUP_FIELD_CONFIG[query_mode]:
            group_fields.append(info["field"])
            field_display_map[info["field"]] = info["display"]

        q: QueryConfigBuilder = q.group_by(*group_fields)
        histogram_q: QueryConfigBuilder = (
            q.metric(field=self.GROUP_MODE_KEY_MAPPING[query_mode], method="count", alias="span_count")
            .metric(field=OtlpKey.ELAPSED_TIME, method="avg", alias="avg_duration")
            .metric(field=OtlpKey.ELAPSED_TIME, method="cp50", alias="p50_duration")
            .metric(field=OtlpKey.ELAPSED_TIME, method="cp90", alias="p90_duration")
        )

        groups_filter: Q = Q()
        after_key: dict[str, Any] | None = {}
        group_bucket_map: dict[tuple, dict[str, Any]] = {}
        for bucket in queryset.add_query(histogram_q):
            group_values: list[str] = []
            group_filter_params: dict[str, Any] = {}
            for group_field in group_fields:
                group_values.append(bucket[group_field])
                group_filter_params[f"{group_field}__eq"] = bucket[group_field]

                # 字段翻译
                bucket[field_display_map[group_field]] = bucket.pop(group_field)

            bucket["source"] = "opentelemetry"
            bucket["error_count"] = bucket["error_rate"] = 0
            for decimal_field in ["avg_duration", "p50_duration", "p90_duration"]:
                bucket[decimal_field] = round(bucket[decimal_field], 2)

            after_key = bucket.pop("_after_key_", None)
            group_bucket_map[tuple(group_values)] = bucket
            groups_filter = groups_filter | Q(**group_filter_params)

        if not group_bucket_map:
            return []

        if after_key:
            redis_cli = ApmCacheHandler.get_redis_client()
            cache_key: str = f"{params_key}:{offset + queryset.query.high_mark}"
            redis_cli.set(cache_key, json.dumps(after_key), AFTER_CACHE_KEY_EXPIRE)
            logger.info("[StatisticsQuery] set cache: cache_key -> %s, after_key -> %s", cache_key, after_key)

        error_q: QueryConfigBuilder = (
            q.filter(groups_filter)
            .filter(**{f"{OtlpKey.STATUS_CODE}__eq": StatusCode.ERROR.value})
            .metric(field=OtlpKey.STATUS_CODE, method="count", alias="error_count")
        )
        for err_bucket in queryset.add_query(error_q).after({}):
            group: tuple = tuple([err_bucket[field] for field in group_fields])
            bucket: dict[str, Any] | None = group_bucket_map.get(group)
            if not bucket:
                logger.info("StatisticsQuery: %s, %s", err_bucket, group_bucket_map)
                logger.warning(
                    "[StatisticsQuery] _query_metric_data failed to add error_count, group -> %s not found", group
                )
                continue

            bucket["error_count"] = err_bucket["error_count"]
            bucket["error_rate"] = round(err_bucket["error_count"] / bucket["span_count"], 2)

        return list(group_bucket_map.values())

    @classmethod
    def _get_after_key_param(cls, offset: int, params_key: str) -> dict[str, Any]:
        after_key = None
        if offset != 0:
            redis_cli = ApmCacheHandler.get_redis_client()
            cache_key: str = f"{params_key}:{offset}"
            if not redis_cli.exists(cache_key):
                logger.warning("[StatisticsQuery] lost cache_key -> %s", cache_key)
                raise ValueError(_("参数丢失 需要重新从第一页获取"))
            cache_value = redis_cli.get(cache_key)
            if cache_value:
                after_key = json.loads(ApmCacheHandler.decode_redis_value(cache_value))

        return after_key or {}

    def _query_specific_span_ids(
        self, start_time: int, end_time: int, logic_field: str, groups: list[dict[str, Any]]
    ) -> list[str]:
        groups_filter: Q = Q()
        logic_span_map = self.LOGIC_FILTER_KEY_MAPPING[logic_field]
        for group in groups:
            groups_filter_params: dict[str, Any] = {
                f"{logic_span_map[field]}__eq": value for field, value in group.items()
            }
            groups_filter: Q = groups_filter | Q(**groups_filter_params)

        span_id_field: str = self.LOGIC_FILTER_KEY_ID_MAPPING[logic_field]
        q: QueryConfigBuilder = (
            self.trace_query.q.filter(groups_filter).filter(self.trace_query.build_app_filter()).values(span_id_field)
        )
        queryset: UnifyQuerySet = (
            UnifyQuerySet()
            .scope(self.bk_biz_id)
            .add_query(q)
            .start_time(start_time)
            .end_time(end_time)
            .limit(DISCOVER_BATCH_SIZE)
        )

        specific_span_ids: set[str] = set()
        for trace_info in queryset:
            specific_span_ids.add(trace_info[span_id_field])

        return list(specific_span_ids)

    def _batch_query_specific_span_ids(
        self, start_time: int, end_time: int, groups: list[dict[str, Any]], logic_fields: list[str]
    ):
        specific_span_ids: set[str] = set()
        params_list = [(start_time, end_time, logic_field, groups) for logic_field in logic_fields]
        for partial_span_ids in ThreadPool().map_ignore_exception(self._query_specific_span_ids, params_list):
            specific_span_ids |= set(partial_span_ids)

        return list(specific_span_ids)

    def _parse_filters(self, filters: list[types.Filter] | None = None) -> tuple[list[str], list[types.Filter]]:
        """分离 filters 中可能保存特殊逻辑的查询"""
        if not filters:
            return [], []

        logic_fields: list[str] = []
        normal_filters: list[types.Filter] = []
        for item in filters:
            if item["operator"] == LogicSupportOperator.LOGIC:
                # 对于统计，只有根 Span、服务入口 Span 需要走特殊逻辑
                if item["key"] not in self.LOGIC_FILTER_ALLOW_KEYS:
                    raise ValueError(_("不支持的过滤KEY: %s").format(item["key"]))
                logic_fields.append(item["key"])
            else:
                normal_filters.append(item)

        return logic_fields, normal_filters
