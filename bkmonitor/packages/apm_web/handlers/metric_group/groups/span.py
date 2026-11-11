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
from typing import Any

from django.db.models import Q
from opentelemetry.trace import StatusCode

from apm_web.calculation import ErrorRateCalculation
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
        q = self._q().interval(self.interval)
        qs = UnifyQuerySet().scope(self.bk_biz_id)

        if calculation_type == define.CalculationType.AVG_DURATION.value:
            # 使用 QuerySet 读取平均耗时，保留 UQ 返回的原始数值精度。
            start_ms, end_ms = UnifyQuery.process_time_range(start_time * 1000, end_time * 1000)
            # QuerySet 按传入的结束时间去掉末点。原平均耗时查询去掉的是对齐到步长后的结束点。
            aligned_end_ms = time_interval_align(end_ms // 1000, self.interval) * 1000
            qs = self._avg_duration_qs(qs, q, expression="(a or vector(0)) / b").start_time(start_ms).end_time(end_ms)
            points_by_group = defaultdict(list)
            for point in qs:
                if point["_time_"] == aligned_end_ms:
                    continue
                key = tuple(point.get(field) for field in self.group_by)
                points_by_group[key].append([point["_result_"], point["_time_"]])
            return [
                {"dimensions": dict(zip(self.group_by, key)), "datapoints": points}
                for key, points in points_by_group.items()
            ]

        if calculation_type == define.CalculationType.EXCEPTION_RATE.value:
            # 按状态码汇总调用次数后计算错误率，有调用但无错误的时间点返回 0。
            q = q.group_by("status_code")
        elif calculation_type != define.CalculationType.REQUEST_TOTAL.value:
            raise ValueError(f"Unsupported range calculation type -> {calculation_type}")

        # Graph 会移除 where 中的全选条件。保留 filter_dict 可精确匹配与全选标记同名的服务。
        config = self._request_total_qs(qs, q).config
        series = resource.grafana.graph_unify_query.query_with_metric_info(
            {**config, "start_time": start_time, "end_time": end_time}, metric_infos=metric_infos
        )["series"]
        if calculation_type == define.CalculationType.REQUEST_TOTAL.value:
            return series

        series_by_group = defaultdict(list)
        for item in series:
            key = tuple(item["dimensions"].get(field) for field in self.group_by)
            series_by_group[key].append(item)
        return [
            {
                "dimensions": dict(zip(self.group_by, key)),
                "datapoints": ErrorRateCalculation.range_cal({"series": items})["series"][0]["datapoints"],
            }
            for key, items in series_by_group.items()
        ]

    def query_config(self, calculation_type: str, raw: bool = False, **kwargs) -> dict[str, Any]:
        return self._export_qs(self._get_qs(calculation_type), raw=raw)

    def _get_qs(self, calculation_type: str) -> UnifyQuerySet:
        support_get_qs_methods: dict[str, Callable[[], UnifyQuerySet]] = {
            define.CalculationType.REQUEST_TOTAL.value: lambda: self._request_total_qs(self._qs(), self._q()),
            define.CalculationType.ERROR_COUNT.value: self._error_count_qs,
            define.CalculationType.EXCEPTION_RATE.value: self._error_rate_qs,
            define.CalculationType.AVG_DURATION.value: lambda: self._avg_duration_qs(self._qs(), self._q()),
            define.CalculationType.P50_DURATION.value: lambda: self._histogram_quantile_duration_qs(0.5),
            define.CalculationType.P95_DURATION.value: lambda: self._histogram_quantile_duration_qs(0.95),
            define.CalculationType.P99_DURATION.value: lambda: self._histogram_quantile_duration_qs(0.99),
        }
        if calculation_type not in support_get_qs_methods:
            raise ValueError(f"Unsupported calculation type -> {calculation_type}")
        return support_get_qs_methods[calculation_type]()

    def _qs(self) -> UnifyQuerySet:
        return self.metric_helper.time_range_qs()

    def _q(self) -> QueryConfigBuilder:
        q = (
            self.metric_helper.q.group_by(*self.group_by)
            .filter(self._filter_dict_to_q())
            .time_field(self.metric_helper.TIME_FIELD)
        )

        if self.service_name:
            q = q.filter(Q(service_name__eq=self.service_name))

        if self.kind == CallSide.CALLER.value:
            q = q.filter(Q(kind=SpanKind.calling_kinds()))
        elif self.kind == CallSide.CALLEE.value:
            q = q.filter(Q(kind=SpanKind.called_kinds()))

        return q

    @staticmethod
    def _request_total_qs(qs: UnifyQuerySet, q: QueryConfigBuilder) -> UnifyQuerySet:
        return qs.add_query(q.metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="a")).expression("a")

    def _error_count_q(self) -> QueryConfigBuilder:
        return (
            self._q()
            .alias("a")
            .metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="a")
            .filter(Q(status_code__eq=StatusCode.ERROR.value))
        )

    def _error_count_qs(self) -> UnifyQuerySet:
        return self._qs().add_query(self._error_count_q()).expression("a")

    def _error_rate_qs(self) -> UnifyQuerySet:
        error_q: QueryConfigBuilder = self._error_count_q()
        total_q: QueryConfigBuilder = self._q().metric(field="bk_apm_count", method="SUM", alias="b")
        return self._qs().add_query(error_q).add_query(total_q).expression("a / b")

    def _avg_duration_qs(self, qs: UnifyQuerySet, q: QueryConfigBuilder, *, expression: str = "a / b") -> UnifyQuerySet:
        # 累计耗时和调用计数共用分组、过滤条件与增量窗口，分母取 bk_apm_total 的计数器增量。
        q = q.func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        sum_q = q.metric(field=TraceMetric.BK_APM_DURATION_SUM, method="SUM", alias="a")
        total_q = q.metric(field=TraceMetric.BK_APM_TOTAL, method="SUM", alias="b")
        return qs.add_query(sum_q).add_query(total_q).expression(expression)

    def _histogram_quantile_duration_qs(self, scalar: float) -> UnifyQuerySet:
        q: QueryConfigBuilder = (
            self._q()
            .alias("a")
            .metric(field=TraceMetric.BK_APM_DURATION_BUCKET, method="SUM", alias="a")
            .group_by("le")
            .func(_id="rate", params=[{"id": "window", "value": f"{self.interval}s"}])
            .func(_id="histogram_quantile", params=[{"id": "scalar", "value": scalar}])
        )
        return self._qs().add_query(q).expression("a")
