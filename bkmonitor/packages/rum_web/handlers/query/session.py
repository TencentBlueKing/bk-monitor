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
from semconv.rum.session import SessionSpec


class SessionQuery(BaseFallbackRumQuery):
    MODE = "session"
    SPEC = SessionSpec
    ANALYSIS_PHASE = "start"

    COUNT_FIELD_NAMES = (*BaseFallbackRumQuery.COUNT_FIELD_NAMES, "view_count")

    def _add_summary_tasks(self, ids: list[str], q: QueryConfigBuilder, tasks: SummaryTasks) -> None:
        view_q = q.filter(**{"attributes.span_type__eq": [RumSpanType.VIEW.value]})
        tasks.append(self._build_metric_task(ids, view_q, "view_count", "attributes.view.id", "distinct"))
        for field_name, sort in (("enter_url_template", "start_time"), ("exit_url_template", "start_time desc")):
            tasks.append(
                self._build_record_task(ids, view_q.order_by(sort), {field_name: "attributes.view.url_template"})
            )
