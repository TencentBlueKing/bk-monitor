"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import partial

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from rum_web.constants import RumQueryMode
from rum_web.handlers.builder.utils import get_safe_number
from rum_web.handlers.query.fallback import BaseFallbackRumQuery, Summaries, SummaryTasks
from semconv.rum.constants import RumSpanType, ViewPhase, VitalMetric
from semconv.rum.view import ViewSpec


class ViewQuery(BaseFallbackRumQuery):
    MODE = RumQueryMode.VIEW.value
    RECORD_ID_FIELD = "attributes.view.id"
    SPEC = ViewSpec
    ANALYSIS_PHASE = ViewPhase.START.value
    SNAPSHOT_SORT = ("-attributes.view.version", "-end_time")

    def _add_summary_tasks(self, ids: list[str], q: QueryConfigBuilder, tasks: SummaryTasks) -> None:
        tasks.append(partial(self._query_vitals, ids, q))

    def _query_vitals(self, ids: list[str], q: QueryConfigBuilder) -> Summaries:
        metrics: tuple[str, ...] = (
            VitalMetric.CLS.value,
            VitalMetric.LCP.value,
            VitalMetric.FCP.value,
            VitalMetric.INP.value,
            VitalMetric.TTFB.value,
        )
        q = q.filter(**{"attributes.span_type": [RumSpanType.VITAL.value]}).order_by("end_time desc")
        vital_q = q.filter(
            **{"attributes.vital.metric": [alias for metric in metrics for alias in (metric, metric.upper())]}
        ).values(self.group_field, "attributes.vital.metric", "attributes.vital.value", "end_time")
        records = self._query_list(self._get_summary_queries(vital_q), None, None, 0, self.QUERY_MAX_LIMIT)
        result: Summaries = {}
        for record_id, record in sorted(
            self._group_records(records, ids), key=lambda item: get_safe_number(item[1].get("end_time")), reverse=True
        ):
            metric = record.get("attributes.vital.metric")
            if not isinstance(metric, str) or metric.lower() not in metrics:
                continue
            result.setdefault(record_id, {}).setdefault(
                f"web_vitals.{metric.lower()}", record.get("attributes.vital.value")
            )
        return result
