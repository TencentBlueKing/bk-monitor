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

import datetime
from typing import Any

from apm import types
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import MetricDataSource
from bkmonitor.data_source.utils.apm import (
    APMQueryFilterMixin,
    FilterOperator,
    TraceDatasourceTarget,
    TraceQueryGuard,
)
from bkmonitor.data_source.utils.query import BaseQuery as DataSourceBaseQuery
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import TelemetryDataType
from constants.data_source import DataSourceLabel, DataTypeLabel

__all__ = ["BaseQuery", "FakeQuery", "FilterOperator"]


class BaseQuery(APMQueryFilterMixin, DataSourceBaseQuery):
    USING: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_APM)

    # 时间填充，单位 s
    TIME_PADDING = 5

    # 时间字段精度，用于时间字段查询时做乘法
    TIME_FIELD_ACCURACY = 1000

    # 默认时间字段
    DEFAULT_TIME_FIELD = "end_time"

    # 查询字段映射
    KEY_REPLACE_FIELDS: dict[str, str] = {}

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        self.data_sources: list[TraceDatasourceTarget] = data_sources

    @property
    def bk_biz_id(self) -> int:
        return self.data_sources[0].app.bk_biz_id

    @property
    def app_name(self) -> str:
        return self.data_sources[0].app.app_name

    @property
    def retention(self) -> int:
        retention: int | None = self.data_sources[0].retention
        if retention is None:
            raise ValueError("APM 查询数据源必须设置 retention")
        return retention

    def get_qs(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        using_scope: bool = True,
    ) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(start_time, end_time)
        # Q：为什么设置 time_align=False？
        # A：Tracing 检索场景对实时性要求高，时间对齐会导致结束时间戳前移，此处和事件检索保持一致，默认不对齐时间。
        queryset: UnifyQuerySet = UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False)
        if using_scope:
            # 默认仅查询本业务下的数据
            return queryset.scope(self.bk_biz_id)
        return queryset

    @classmethod
    def get_retention_time_range(
        cls, retention: int, start_time: int | None = None, end_time: int | None = None
    ) -> tuple[int, int]:
        now: int = int(datetime.datetime.now().timestamp())

        retention_seconds: int = int(datetime.timedelta(days=retention).total_seconds())
        # 最早可查询时间
        earliest_start_time: int = now - retention_seconds

        if not end_time:
            # 不传 end_time 代表查询最新数据，通常我们会在页面拿到 TraceID 后便进行查询，
            # 请求时间距离实际存储查询时间可能存在一定延迟，因此需增加一个时间填充，避免查询不到数据。
            end_time = now + cls.TIME_PADDING
        else:
            # 已指定查询时间范围，则需要对 end_time 做限制，避免查询到未来时间的数据。
            end_time = min(now, end_time)

        start_time: int = start_time or earliest_start_time
        if end_time < earliest_start_time:
            # 情况 1 - 查询返回不在有效查询时间内：-<start_time>-----<end_time>-----<earliest_start_time>----<now>--
            start_time = max(end_time - retention_seconds, start_time)
        else:
            # 情况 2 - 查询时间部分或全部在有效查询时间内：-<start_time>---<earliest_start_time>---<end_time>----<now>--
            start_time = max(earliest_start_time, start_time)

        start_time *= cls.TIME_FIELD_ACCURACY
        end_time *= cls.TIME_FIELD_ACCURACY

        return start_time, end_time

    def _get_time_range(self, start_time: int | None = None, end_time: int | None = None) -> tuple[int, int]:
        return self.get_retention_time_range(self.retention, start_time, end_time)

    def build_queries(
        self,
        filters: list[types.Filter] | None = None,
        query_string: str | None = "",
        time_field: str | None = None,
    ) -> list[QueryConfigBuilder]:
        return [
            TraceQueryGuard.get_q([data_source])
            .time_field(time_field or self.DEFAULT_TIME_FIELD)
            .filter(self._build_filters(filters))
            .query_string(query_string or "")
            for data_source in self.data_sources
        ]

    def build_metric_option_queries(
        self,
        filters: list[types.Filter] | None = None,
        query_string: str | None = "",
    ) -> list[QueryConfigBuilder]:
        metric_data_source: MetricDataSource | None = MetricDataSource.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=self.app_name
        ).first()
        if not metric_data_source or not metric_data_source.result_table_id:
            raise ValueError(f"应用 {self.bk_biz_id}:{self.app_name} 未配置 Metric 数据源")

        return [
            QueryConfigBuilder((DataTypeLabel.TIME_SERIES, DataSourceLabel.CUSTOM))
            .table(metric_data_source.result_table_id)
            .filter(self._build_filters(filters))
            .query_string(query_string or "")
        ]

    def _query_metric_option_values(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int,
    ) -> dict[str, list[str]]:
        queryset: UnifyQuerySet = self.get_qs(start_time, end_time).limit(limit)
        option_values: dict[str, list[str]] = {field: [] for field in fields}
        ThreadPool().map_ignore_exception(
            self._collect_metric_option_values,
            [(queries, queryset, field, option_values) for field in fields],
        )
        return option_values

    @classmethod
    def _collect_metric_option_values(
        cls,
        queries: list[QueryConfigBuilder],
        queryset: UnifyQuerySet,
        field: str,
        option_values: dict[str, list[str]],
    ) -> None:
        field_queries: list[QueryConfigBuilder] = [
            query.metric(field="bk_apm_count", method="count").tag_values(field).time_field("time") for query in queries
        ]
        for bucket in cls._add_query(queryset, field_queries):
            if bucket.get("_result_") == 0:
                continue
            option_values[field].append(bucket[field])

    def query_field_topk(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._query_field_topk(self.build_queries(filters, query_string), start_time, end_time, field, limit)

    def query_field_aggregated_value(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        method: str,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ) -> int | float:
        return self._query_field_aggregated_value(
            self.build_queries(filters, query_string), start_time, end_time, field, method
        )

    def query_option_values(
        self,
        datasource_type: str,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int,
        filters: list[types.Filter],
        query_string: str,
    ) -> dict[str, list[str]]:
        if datasource_type == TelemetryDataType.METRIC.value:
            queries: list[QueryConfigBuilder] = self.build_metric_option_queries(filters, query_string)
            return self._query_metric_option_values(queries, start_time, end_time, fields, limit)

        return self._query_option_values(self.build_queries(filters, query_string), start_time, end_time, fields, limit)

    def query_graph_config(self, start_time, end_time, field, filters: list[types.Filter], query_string: str):
        """
        获取查询配置
        """
        return self._query_graph_config(self.build_queries(filters, query_string), start_time, end_time, field)


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
