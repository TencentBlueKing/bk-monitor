"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import replace
from functools import partial
from typing import Any

from bkmonitor.data_source.format import flatten_dict_data
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget, TraceQueryGuard
from bkmonitor.utils.thread_backend import ThreadPool
from constants.otel_query import AggregatedMethod
from rum_web.constants import RumQueryMode
from rum_web.handlers.builder.utils import get_safe_number
from rum_web.handlers.query.base import BaseRumQuery, equal_filter
from semconv.constants import SpanStatusCode
from semconv.rum.common import COUNT_FIELDS
from semconv.rum.constants import FrustrationType, ResourceType, RumSpanType, SessionPhase, ViewPhase

Record = dict[str, Any]
Summaries = dict[str, Record]
SummaryTask = Callable[[], Summaries]
SummaryTasks = list[SummaryTask]


class BaseFallbackRumQuery(BaseRumQuery, ABC):
    """Session / View 的折叠查询与补查，任务直接返回按 ID 组织的回填值。"""

    DEFAULT_SORT = ["-start_time"]
    ANALYSIS_PHASE: str
    SNAPSHOT_SORT: tuple[str, ...] = ("-end_time",)
    SPAN_COUNT_FIELDS: dict[str, str] = {
        RumSpanType.ERROR.value: "error_count",
        RumSpanType.ACTION.value: "action_count",
        RumSpanType.LONG_TASK.value: "long_task_count",
    }
    COUNT_FIELD_NAMES: tuple[str, ...] = tuple(field.field_name for field in COUNT_FIELDS)

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__([*data_sources])
        self.span_query = BaseRumQuery([*data_sources])
        self.use_precomputed = bool(data_sources) and all(
            target.get_level_table_ids(self.MODE) for target in data_sources
        )
        self.level_query = (
            BaseRumQuery(
                [
                    replace(target, table_id=table)
                    for target in data_sources
                    for table in target.get_level_table_ids(self.MODE)
                ]
            )
            if self.use_precomputed
            else None
        )
        if self.level_query is not None:
            self.level_query.DEFAULT_TIME_FIELD = "start_time"

    def get_queries(
        self, filters: list[types.Filter] | None = None, query_string: str = ""
    ) -> list[QueryConfigBuilder]:
        if self.level_query is not None:
            return self.level_query.get_queries(filters, query_string)
        return self.span_query.get_queries(
            [
                *(filters or []),
                equal_filter("attributes.span_type", [self.MODE]),
                *self._identity_filters(),
                equal_filter(f"attributes.{self.MODE}.phase", [self.ANALYSIS_PHASE]),
            ],
            query_string,
        )

    @property
    def raw_query(self) -> BaseRumQuery:
        return self.span_query

    def query_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int,
        filters: list[types.Filter],
        query_string: str,
    ) -> dict[str, list[str]]:
        if self.level_query is not None:
            return self.level_query.query_option_values(start_time, end_time, fields, limit, filters, query_string)
        # 候选值与列表使用相同范围，避免仅在开始阶段缺失的字段无法筛选。
        return self.span_query.query_option_values(
            start_time, end_time, fields, limit, [*filters, *self._identity_filters()], query_string
        )

    def query_list(
        self,
        start_time: int | None,
        end_time: int | None,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        sort = sort or self.DEFAULT_SORT
        if self.level_query is not None:
            return self.level_query.query_list(start_time, end_time, offset, limit, filters, query_string, sort)
        records = self.span_query.query_group_list(
            start_time,
            end_time,
            self.group_field,
            offset,
            limit,
            [*(filters or []), *self._identity_filters()],
            query_string,
            sort,
        )

        if not records:
            return []
        ids: list[str] = list(dict.fromkeys(record_id for record_id, _ in self._group_records(records)))
        return self.fill_records(records, self.query_summaries(ids))

    @property
    def group_field(self) -> str:
        return self.RECORD_ID_FIELD

    def _identity_filters(self) -> list[types.Filter]:
        return [
            {"key": self.group_field, "value": [""], "operator": FilterOperator.NOT_EQUAL},
        ]

    def query_summaries(self, ids: list[str]) -> Summaries:
        """按当前页 ID 补查保留期数据，不继承列表筛选。"""
        if not ids:
            return {}
        q = self._get_q(self.span_query.DEFAULT_TIME_FIELD).filter(**{self.group_field: ids})
        tasks = self._build_summary_tasks(ids, q)
        self._add_summary_tasks(ids, q, tasks)
        return self._collect_summaries(ids, tasks)

    @abstractmethod
    def _add_summary_tasks(self, ids: list[str], q: QueryConfigBuilder, tasks: SummaryTasks) -> None:
        """追加层级专属补查任务。"""
        ...

    def _build_summary_tasks(self, ids: list[str], q: QueryConfigBuilder) -> SummaryTasks:
        request_q = q.filter(
            **{
                "attributes.span_type": [RumSpanType.RESOURCE.value],
                "attributes.resource.type": [ResourceType.XHR.value, ResourceType.FETCH.value],
            }
        )
        return [
            self._build_metric_task(ids, q, "start_time", "start_time", AggregatedMethod.MIN.value),
            self._build_metric_task(ids, q, "end_time", "end_time", AggregatedMethod.MAX.value),
            self._build_metric_task(ids, q, "trace_count", "links.trace_id", AggregatedMethod.COUNT.value),
            partial(self._query_span_counts, ids, q),
            # 数组只用于筛选，对匹配的 Action 记录计数。
            self._build_metric_task(
                ids,
                q.filter(
                    **{
                        "attributes.span_type": [RumSpanType.ACTION.value],
                        "attributes.action.frustration.type": [kind.value for kind in FrustrationType],
                    }
                ),
                "frustration_count",
                "_index",
                AggregatedMethod.COUNT.value,
            ),
            self._build_metric_task(ids, request_q, "request_count", "_index", AggregatedMethod.COUNT.value),
            self._build_metric_task(
                ids,
                request_q.filter(**{"status.code": [SpanStatusCode.ERROR.value]}),
                "request_error_count",
                "_index",
                AggregatedMethod.COUNT.value,
            ),
            partial(self._query_snapshot, ids, q),
        ]

    def _build_metric_task(
        self, ids: list[str], q: QueryConfigBuilder, target_field: str, field: str, method: str
    ) -> SummaryTask:
        def query() -> Summaries:
            records = self._query_metric_records(q, field, method, len(ids))
            return self._project_records(records, ids, {target_field: "_result_"})

        return query

    def _build_record_task(self, ids: list[str], q: QueryConfigBuilder, fields: dict[str, str]) -> SummaryTask:
        def query() -> Summaries:
            records = self._query_group_list(self._get_summary_queries(q), None, None, self.group_field, limit=len(ids))
            return self._project_records(records, ids, fields)

        return query

    def _get_summary_queries(self, q: QueryConfigBuilder) -> list[QueryConfigBuilder]:
        """为补查模板绑定原始表，并保留各数据源的应用隔离条件。"""
        return [TraceQueryGuard.apply_q(q.table(target.table_id), [target]) for target in self.span_query.data_sources]

    def _query_metric_records(
        self,
        q: QueryConfigBuilder,
        field: str,
        method: str,
        limit: int,
        group_by: list[str] | None = None,
    ) -> list[Record]:
        result = self._statistics(
            self._get_summary_queries(q),
            None,
            None,
            field,
            method,
            "0",
            ["0"],
            group_by=group_by or [self.group_field],
        )
        return [{**row["dimensions"], "_result_": row["0"]} for row in result["data"]][:limit]

    def _query_snapshot(self, ids: list[str], q: QueryConfigBuilder) -> Summaries:
        q = q.filter(**{"attributes.span_type": [self.MODE]}).order_by(
            *self.process_sort_fields(list(self.SNAPSHOT_SORT))
        )
        records = self._query_group_list(self._get_summary_queries(q), None, None, self.group_field, limit=len(ids))
        return {record_id: {"snapshot": record} for record_id, record in self._group_records(records, ids)}

    def _query_span_counts(self, ids: list[str], q: QueryConfigBuilder) -> Summaries:
        records = self._query_metric_records(
            q.filter(**{"attributes.span_type": list(self.SPAN_COUNT_FIELDS)}),
            "_index",
            AggregatedMethod.COUNT.value,
            len(ids) * len(self.SPAN_COUNT_FIELDS),
            group_by=[self.group_field, "attributes.span_type"],
        )
        result: Summaries = {}
        for record_id, record in self._group_records(records, ids):
            span_type = record.get("attributes.span_type")
            if not isinstance(span_type, str):
                continue
            count_field = self.SPAN_COUNT_FIELDS.get(span_type)
            if count_field is not None:
                result.setdefault(record_id, {})[count_field] = record.get("_result_")
        return result

    def _group_records(self, records: list[Record], ids: list[str] | None = None) -> Iterator[tuple[str, Record]]:
        allowed_ids = set(ids) if ids is not None else None
        for record in records:
            flat: Record = flatten_dict_data(record)
            record_id = flat.get(self.group_field)
            if not isinstance(record_id, str) or not record_id:
                continue
            if allowed_ids is None or record_id in allowed_ids:
                yield record_id, flat

    def _project_records(self, records: list[Record], ids: list[str], fields: dict[str, str]) -> Summaries:
        return {
            record_id: {target: record.get(source) for target, source in fields.items()}
            for record_id, record in self._group_records(records, ids)
        }

    @staticmethod
    def _collect_summaries(ids: list[str], tasks: SummaryTasks) -> Summaries:
        summaries: Summaries = {record_id: {} for record_id in ids}
        with ThreadPool(processes=6) as pool:
            for result in pool.imap(lambda task: task(), tasks):
                for record_id, values in result.items():
                    summary = summaries.get(record_id)
                    if summary is not None:
                        summary.update(values)
        return summaries

    def fill_records(self, records: list[Record], summaries: Summaries) -> list[Record]:
        """按折叠分页顺序回填，缺失指标保留 None，成功查询无计数桶时为零。"""
        result: list[Record] = []
        for record in records:
            flat: Record = flatten_dict_data(record)
            record_id = flat.get(self.group_field)
            summary = summaries.get(record_id, {}) if isinstance(record_id, str) else {}
            snapshot_value = summary.get("snapshot")
            snapshot: Record = snapshot_value if isinstance(snapshot_value, dict) else {}
            row: Record = {
                field.field_name: flat.get(field.field_name, snapshot.get(field.field_name))
                if field.is_real
                else summary.get(field.field_name)
                for field in self.SPEC.fields()
            }
            for field_name in self.COUNT_FIELD_NAMES:
                row[field_name] = summary.get(field_name, 0)
            row.update(self._lifecycle_values(summary, snapshot))
            result.append(row)
        return result

    def _lifecycle_values(self, summary: Record, snapshot: Record) -> Record:
        start_time = get_safe_number(summary.get("start_time"), None)
        end_time = get_safe_number(summary.get("end_time"), None)
        phase_value = snapshot.get(f"attributes.{self.MODE}.phase")
        phase = phase_value if isinstance(phase_value, str) else None
        end_phase = SessionPhase.END.value if self.MODE == RumQueryMode.SESSION.value else ViewPhase.END.value
        # 没有预计算窗口时，不推测超时关闭。
        return {
            "duration": max(0, end_time - start_time) if start_time is not None and end_time is not None else None,
            "is_active": phase != end_phase if phase else None,
            "close_reason": "normal" if phase == end_phase else None,
            "close_time": snapshot.get("end_time") if phase == end_phase else None,
        }
