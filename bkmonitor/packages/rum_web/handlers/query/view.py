"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from rum_web.handlers.query.fallback import BaseFallbackRumQuery, SummaryTasks
from semconv.rum.constants import RumSpanType
from semconv.rum.view import ViewSpec


class ViewQuery(BaseFallbackRumQuery):
    MODE = "view"
    SPEC = ViewSpec
    ANALYSIS_PHASE = "update"
    SNAPSHOT_SORT = ("-attributes.view.version", "-end_time")

    def _add_summary_tasks(self, ids: list[str], q: QueryConfigBuilder, tasks: SummaryTasks) -> None:
        for metric in ("cls", "lcp", "fcp", "inp", "ttfb"):
            tasks.append(
                self._build_record_task(
                    ids,
                    q.filter(
                        **{
                            "attributes.span_type__eq": [RumSpanType.VITAL.value],
                            "attributes.vital.metric__eq": [metric, metric.upper()],
                        }
                    ).order_by("end_time desc"),
                    {f"web_vitals.{metric}": "attributes.vital.value"},
                )
            )
