"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from collections.abc import Callable
from functools import partial
from typing import Any

from django.db.models import Q
from opentelemetry.trace import StatusCode

from bkmonitor.data_source import UnifyQuery
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.time_tools import time_interval_align
from constants.apm import CallSide, SpanKind, TraceMetric
from core.drf_resource import resource

from .. import base, define


class SpanMetricGroup(base.BaseMetricGroup):
    DEFAULT_INTERVAL = 120

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: list[str] | None = None,
        filter_dict: dict[str, Any] | None = None,
        interval: int | None = None,
        service_name: str | None = None,
        kind: str | None = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, group_by, filter_dict, **kwargs)
        self.interval: int = interval or self.DEFAULT_INTERVAL
        self.service_name: str | None = service_name
        self.kind: str | None = kind

    class Meta:
        name = define.GroupEnum.SPAN.value

    def handle(
        self,
        calculation_type: str,
        *,
        start_time: int,
        end_time: int,
        metric_infos: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        return self.get_calculation_method(calculation_type)(
            start_time=start_time, end_time=end_time, metric_infos=metric_infos, **kwargs
        )

    def get_calculation_method(self, calculation_type: str) -> Callable[..., list[dict[str, Any]]]:
        support_calculation_methods = {
            define.CalculationType.REQUEST_TOTAL.value: self._request_total,
            define.CalculationType.EXCEPTION_RATE.value: self._error_rate,
            define.CalculationType.AVG_DURATION.value: self._avg_duration,
        }
        if calculation_type not in support_calculation_methods:
            raise ValueError(f"Unsupported range calculation type -> {calculation_type}")
        return support_calculation_methods[calculation_type]

    def _request_total(
        self, start_time: int, end_time: int, metric_infos: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return self._query_graph_series(self._request_total_qs(start_time, end_time), metric_infos=metric_infos)

    def _error_rate(
        self, start_time: int, end_time: int, metric_infos: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return self._query_graph_series(
            self._error_rate_qs(start_time, end_time), metric_infos=metric_infos, include_null_points=False
        )

    def _avg_duration(self, start_time: int, end_time: int, **kwargs: Any) -> list[dict[str, Any]]:
        return self._query_series(self._avg_duration_qs(start_time, end_time))

    def _query_graph_series(
        self, qs: UnifyQuerySet, *, metric_infos: list[dict[str, Any]] | None, include_null_points: bool = True
    ) -> list[dict[str, Any]]:
        # Graph 会移除 where 中的全选条件。保留 filter_dict 可精确匹配与全选标记同名的服务。
        config = qs.config
        series = resource.grafana.graph_unify_query.query_with_metric_info(
            {**config, "start_time": config["start_time"] // 1000, "end_time": config["end_time"] // 1000},
            metric_infos=metric_infos,
        )["series"]
        if not include_null_points:
            # 列表自行补点，避免 Graph 的占位点改变原有空桶时间戳。
            for item in series:
                item["datapoints"] = [point for point in item["datapoints"] if point[0] is not None]
        return series

    def _query_series(self, qs: UnifyQuerySet) -> list[dict[str, Any]]:
        """将 QuerySet 记录转换为趋势序列，保留 UQ 原始数值精度。"""
        points_by_group = defaultdict(list)
        for point in qs:
            key = tuple(point.get(field) for field in self.group_by)
            points_by_group[key].append([point["_result_"], point["_time_"]])
        return [
            {"dimensions": dict(zip(self.group_by, key)), "datapoints": points}
            for key, points in points_by_group.items()
        ]

    def query_config(self, calculation_type: str, raw: bool = False, **kwargs: Any) -> dict[str, Any]:
        return self._export_qs(
            self._get_qs(calculation_type, kwargs.get("start_time"), kwargs.get("end_time")), raw=raw
        )

    def _get_qs(
        self, calculation_type: str, start_time: int | None = None, end_time: int | None = None
    ) -> UnifyQuerySet:
        support_get_qs_methods: dict[str, Callable[..., UnifyQuerySet]] = {
            define.CalculationType.REQUEST_TOTAL.value: self._request_total_qs,
            define.CalculationType.ERROR_COUNT.value: self._error_count_qs,
            define.CalculationType.EXCEPTION_RATE.value: self._error_rate_qs,
            define.CalculationType.AVG_DURATION.value: self._avg_duration_qs,
            define.CalculationType.P50_DURATION.value: partial(self._histogram_quantile_duration_qs, 0.5),
            define.CalculationType.P95_DURATION.value: partial(self._histogram_quantile_duration_qs, 0.95),
            define.CalculationType.P99_DURATION.value: partial(self._histogram_quantile_duration_qs, 0.99),
        }
        if calculation_type not in support_get_qs_methods:
            raise ValueError(f"Unsupported calculation type -> {calculation_type}")
        return support_get_qs_methods[calculation_type](start_time, end_time)

    def _qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        if start_time is None or end_time is None:
            return self.metric_helper.time_range_qs(start_time, end_time).scope(self.bk_biz_id)
        return UnifyQuerySet().scope(self.bk_biz_id).start_time(start_time * 1000).end_time(end_time * 1000)

    def _q(self) -> QueryConfigBuilder:
        q = (
            self.metric_helper.q.group_by(*self.group_by)
            .filter(self._filter_dict_to_q())
            .time_field(self.metric_helper.TIME_FIELD)
            .interval(self.interval)
        )

        if self.service_name:
            q = q.filter(Q(service_name__eq=self.service_name))

        if self.kind == CallSide.CALLER.value:
            q = q.filter(Q(kind=SpanKind.calling_kinds()))
        elif self.kind == CallSide.CALLEE.value:
            q = q.filter(Q(kind=SpanKind.called_kinds()))

        return q

    def _request_total_qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        q = self._q().metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="a")
        return self._qs(start_time, end_time).add_query(q).expression("a")

    def _error_count_q(self) -> QueryConfigBuilder:
        return (
            self._q()
            .alias("a")
            .metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="a")
            .filter(Q(status_code__eq=StatusCode.ERROR.value))
        )

    def _error_count_qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        return self._qs(start_time, end_time).add_query(self._error_count_q()).expression("a")

    def _error_rate_qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        error_q = self._error_count_q()
        # 缺少状态码的调用不计入分母；UQ 将空标签视为缺失标签。
        total_q = (
            self._q().metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="b").filter(Q(status_code__neq=""))
        )
        # 按分母维度补齐无错误的零值，分母为零或缺失时仍不返回有效点。
        return self._qs(start_time, end_time).add_query(error_q).add_query(total_q).expression("(a or b < bool 0) / b")

    def _avg_duration_qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        qs = self._qs(start_time, end_time)
        start_ms, end_ms = UnifyQuery.process_time_range(qs.query.start_time, qs.query.end_time)
        # 先对齐结束时间，由 QuerySet 公共查询层剔除末点；0 仍保留原有默认时间处理。
        aligned_end_ms = time_interval_align(end_ms // 1000, self.interval) * 1000
        qs = qs.start_time(start_ms).end_time(aligned_end_ms or end_ms)
        # 累计耗时和调用计数共用分组、过滤条件与增量窗口，分母取 bk_apm_total 的计数器增量。
        q = self._q().func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        sum_q = q.metric(field=TraceMetric.BK_APM_DURATION_SUM, method="SUM", alias="a")
        total_q = q.metric(field=TraceMetric.BK_APM_TOTAL, method="SUM", alias="b")
        # 零分母保留无有效数据语义；vector(0) 仅兼容无分组查询，缺少服务耗时样本不补 0。
        return qs.add_query(sum_q).add_query(total_q).expression("(a or vector(0)) / (b != 0)")

    def _histogram_quantile_duration_qs(
        self, scalar: float, start_time: int | None = None, end_time: int | None = None
    ) -> UnifyQuerySet:
        q: QueryConfigBuilder = (
            self._q()
            .alias("a")
            .metric(field=TraceMetric.BK_APM_DURATION_BUCKET, method="SUM", alias="a")
            .group_by("le")
            .func(_id="rate", params=[{"id": "window", "value": f"{self.interval}s"}])
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": scalar}])
        )
        return self._qs(start_time, end_time).add_query(q).expression("a")
