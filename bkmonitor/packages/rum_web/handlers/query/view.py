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
from rum_web.handlers.query.fallback import BaseFallbackRumQuery, Record, Summaries, SummaryTasks
from semconv.rum.constants import RumSpanType, ViewPhase, VitalMetric
from semconv.rum.view import ViewSpec


class ViewQuery(BaseFallbackRumQuery):
    MODE: str = RumQueryMode.VIEW.value
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
        ).values(
            self.group_field,
            "attributes.vital.id",
            "attributes.vital.version",
            "attributes.vital.metric",
            "attributes.vital.value",
            "end_time",
        )
        records = self._query_list(self._get_summary_queries(vital_q), None, None, 0, self.QUERY_MAX_LIMIT)
        # 版本只在同一指标 ID 内比较，无版本时按结束时间选择。
        snapshots: dict[tuple[str, str, str], tuple[int | float, int | float, Record]] = {}
        for record_id, record in self._group_records(records, ids):
            metric = record.get("attributes.vital.metric")
            if not isinstance(metric, str) or metric.lower() not in metrics:
                continue
            vital_id = record.get("attributes.vital.id")
            if not isinstance(vital_id, str):
                vital_id = ""
            version = get_safe_number(record.get("attributes.vital.version")) if vital_id else 0
            end_time = get_safe_number(record.get("end_time"))
            key = (record_id, metric.lower(), vital_id)
            previous = snapshots.get(key)
            if previous is None or (version, end_time) > previous[:2]:
                snapshots[key] = (version, end_time, record)

        # 同一 View 的同名指标可以有多个 ID，继续按结束时间回填最新值。
        result: Summaries = {}
        for (record_id, metric, _), (_, _, record) in sorted(
            snapshots.items(), key=lambda item: item[1][1], reverse=True
        ):
            result.setdefault(record_id, {}).setdefault(f"web_vitals.{metric}", record.get("attributes.vital.value"))
        return result
