"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from collections.abc import Callable

from django.db.models import Q
from opentelemetry.trace import StatusCode

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import SpanKind, CallSide, TraceMetric

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

    def handle(self, calculation_type: str, **kwargs) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_config(self, calculation_type: str, raw: bool = False, **kwargs) -> dict[str, Any]:
        return self._export_qs(self._get_qs(calculation_type), raw=raw)

    def _get_qs(self, calculation_type: str) -> UnifyQuerySet:
        support_get_qs_methods: dict[str, Callable[[], UnifyQuerySet]] = {
            define.CalculationType.REQUEST_TOTAL.value: self._request_total_qs,
            define.CalculationType.ERROR_COUNT.value: self._error_count_qs,
            define.CalculationType.EXCEPTION_RATE.value: self._error_rate_qs,
            define.CalculationType.AVG_DURATION.value: self._avg_duration_qs,
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

    def _request_total_qs(self) -> UnifyQuerySet:
        return (
            self._qs()
            .add_query(self._q().metric(field=TraceMetric.BK_APM_COUNT, method="SUM", alias="a"))
            .expression("a")
        )

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

    def _avg_duration_qs(self) -> UnifyQuerySet:
        sum_q: QueryConfigBuilder = (
            self._q()
            .metric(field=TraceMetric.BK_APM_DURATION_SUM, method="SUM", alias="a")
            .func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        )
        total_q: QueryConfigBuilder = (
            self._q()
            .metric(field=TraceMetric.BK_APM_TOTAL, method="SUM", alias="b")
            .func(_id="increase", params=[{"id": "window", "value": f"{self.interval}s"}])
        )
        return self._qs().add_query(sum_q).add_query(total_q).expression("a / b")

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
