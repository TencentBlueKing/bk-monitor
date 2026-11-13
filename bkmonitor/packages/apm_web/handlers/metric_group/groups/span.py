"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Callable
from functools import partial
from typing import Any

from django.db.models import Q
from opentelemetry.trace import StatusCode

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import CallSide, SpanKind, TraceMetric

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
    ) -> None:
        super().__init__(bk_biz_id, app_name, group_by, filter_dict, **kwargs)
        self.interval: int = interval or self.DEFAULT_INTERVAL
        self.service_name: str | None = service_name
        self.kind: str | None = kind

    class Meta:
        name = define.GroupEnum.SPAN.value

    def handle(self, calculation_type: str, **kwargs: Any) -> list[dict[str, Any]]:
        return self.get_calculation_method(calculation_type)(**kwargs)

    def get_calculation_method(self, calculation_type: str) -> Callable[..., list[dict[str, Any]]]:
        support_calculation_methods = {
            define.CalculationType.REQUEST_TOTAL.value: self._request_total,
            define.CalculationType.EXCEPTION_RATE.value: self._error_rate,
            define.CalculationType.AVG_DURATION.value: self._avg_duration,
        }
        if calculation_type not in support_calculation_methods:
            raise ValueError(f"Unsupported range calculation type -> {calculation_type}")
        return support_calculation_methods[calculation_type]

    def _request_total(self, start_time: int | None = None, end_time: int | None = None) -> list[dict[str, Any]]:
        return list(self._request_total_qs(start_time, end_time))

    def _error_rate(self, start_time: int | None = None, end_time: int | None = None) -> list[dict[str, Any]]:
        return list(self._error_rate_qs(start_time, end_time))

    def _avg_duration(self, start_time: int | None = None, end_time: int | None = None) -> list[dict[str, Any]]:
        return list(self._avg_duration_qs(start_time, end_time))

    def query_config(
        self, calculation_type: str, raw: bool = False, preserve_filter_dict: bool = False, **kwargs
    ) -> dict[str, Any]:
        qs = self._get_qs(calculation_type, kwargs.get("start_time"), kwargs.get("end_time"))
        # 保留精确匹配条件，避免在 Graph 中被解释为全选条件。
        if raw and preserve_filter_dict:
            return qs.config
        return self._export_qs(qs, raw=raw)

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
        return self.metric_helper.time_range_qs(start_time, end_time).scope(self.bk_biz_id)

    def _q(self) -> QueryConfigBuilder:
        q = self.metric_helper.q.group_by(*self.group_by).filter(self._filter_dict_to_q()).interval(self.interval)

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
        total_q = self._q().metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="b")
        # b < bool 0 为有调用的分组补齐缺失的错误次数，零分母不产生有效错误率。
        return self._qs(start_time, end_time).add_query(error_q).add_query(total_q).expression("(a or b < bool 0) / b")

    def _avg_duration_qs(self, start_time: int | None = None, end_time: int | None = None) -> UnifyQuerySet:
        # 累计耗时与调用次数在相同窗口内取增量后相除，保留耗时指标的原始单位。
        # 分母使用累加计数器 bk_apm_total，分子、分母共用分组和过滤条件。
        q = self._q().func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        sum_q = q.metric(field=TraceMetric.BK_APM_DURATION_SUM, method="SUM", alias="a")
        total_q = q.metric(field=TraceMetric.BK_APM_TOTAL, method="SUM", alias="b")
        # 调用次数为零或缺少耗时样本时，平均耗时留空。
        return self._qs(start_time, end_time).add_query(sum_q).add_query(total_q).expression("a / (b != 0)")

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
