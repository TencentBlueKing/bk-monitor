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
from semconv.rum.constants import RumSpanType, SessionPhase
from semconv.rum.session import SessionSpec


class SessionQuery(BaseFallbackRumQuery):
    MODE = RumQueryMode.SESSION.value
    RECORD_ID_FIELD = "attributes.session.id"
    SPEC = SessionSpec
    ANALYSIS_PHASE = SessionPhase.START.value

    COUNT_FIELD_NAMES = (*BaseFallbackRumQuery.COUNT_FIELD_NAMES, "view_count")

    def _add_summary_tasks(self, ids: list[str], q: QueryConfigBuilder, tasks: SummaryTasks) -> None:
        tasks.append(partial(self._query_views, ids, q))

    def _query_views(self, ids: list[str], q: QueryConfigBuilder) -> Summaries:
        q = (
            q.filter(**{"attributes.span_type": [RumSpanType.VIEW.value]})
            .values(self.group_field, "attributes.view.id", "attributes.view.url_template", "start_time")
            .order_by("start_time")
        )
        records = self._query_list(self._get_summary_queries(q), None, None, 0, self.QUERY_MAX_LIMIT)
        result: Summaries = {}
        view_ids: dict[str, set[str]] = {}
        for record_id, record in sorted(
            self._group_records(records, ids), key=lambda item: get_safe_number(item[1].get("start_time"))
        ):
            summary: Record = result.setdefault(record_id, {})
            session_view_ids: set[str] = view_ids.setdefault(record_id, set())
            view_id = record.get("attributes.view.id")
            if isinstance(view_id, str):
                session_view_ids.add(view_id)
            summary["view_count"] = len(session_view_ids)
            summary.setdefault("enter_url_template", record.get("attributes.view.url_template"))
            summary["exit_url_template"] = record.get("attributes.view.url_template")
        return result
