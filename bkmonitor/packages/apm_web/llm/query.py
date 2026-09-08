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

from django.db.models import Q

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.handlers.query.span import SpanQuery
from apm_web.llm.constants import CONVERSATION_QUERY_FIELDS


def get_span_field_value(span: dict[str, Any], field: str) -> Any:
    """兼容 UQ 聚合结果和标准化 Span 的字段结构。"""

    if field in span:
        value = span[field]
        if isinstance(value, list):
            return value[0] if value else ""
        return value

    section, separator, name = field.partition(".")
    if separator and section in {OtlpKey.ATTRIBUTES, OtlpKey.RESOURCE}:
        values = span.get(section)
        value = values.get(name, "") if isinstance(values, dict) else ""
    else:
        value = span.get(field, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return value


class LLMQuery(SpanQuery):
    """查询 LLM Trace 与会话。"""

    def _query_group_buckets(
        self,
        start_time: int | None,
        end_time: int | None,
        group_field: str,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
        exclude_fields: tuple[str, ...] = (),
    ) -> list[dict[str, Any]]:
        """按字段聚合分组，并以组内最新 Span 时间倒序返回。"""

        alias = "a"
        group_conditions = [f"_exists_:{group_field}"]
        group_conditions.extend(f"NOT _exists_:{field}" for field in exclude_fields)
        group_query = " AND ".join(f"({condition})" for condition in group_conditions)
        if query_string:
            group_query = f"({query_string}) AND {group_query}"
        queries = [
            query.alias(alias)
            .metric(field=self.DEFAULT_TIME_FIELD, method="MAX", alias=alias)
            .group_by(group_field)
            .order_by("_value desc", f"{group_field} asc")
            for query in self.build_queries(filters, group_query)
        ]
        queryset = self.get_qs(start_time, end_time).expression(alias).time_agg(False).instant().limit(limit)
        return list(self._add_query(queryset, queries))

    def query_group_aggregate_list(
        self,
        start_time: int | None,
        end_time: int | None,
        group_fields: tuple[str, ...],
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ) -> list[str]:
        """合并多个原始字段的分组值，并按组内最新 Span 时间分页。"""

        query_limit = min(offset + limit, self.QUERY_MAX_LIMIT)
        if not group_fields or query_limit <= offset:
            return []

        latest_by_group: dict[str, int | float] = {}
        for index, group_field in enumerate(group_fields):
            records = self._query_group_buckets(
                start_time=start_time,
                end_time=end_time,
                group_field=group_field,
                limit=query_limit,
                filters=filters,
                query_string=query_string,
                exclude_fields=group_fields[:index],
            )
            for record in records:
                group_id = get_span_field_value(record, group_field)
                latest = record.get("_result_")
                if group_id in (None, []) or not str(group_id).strip() or not isinstance(latest, int | float):
                    continue
                group_id = str(group_id)
                latest_by_group[group_id] = max(latest, latest_by_group.get(group_id, latest))

        ordered_group_ids = sorted(latest_by_group, key=lambda group_id: (-latest_by_group[group_id], group_id))
        return ordered_group_ids[offset : offset + limit]

    def query_group_list(
        self,
        start_time: int | None,
        end_time: int | None,
        group_field: str,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ) -> list[str]:
        """使用存储侧折叠查询单个分组字段。"""

        queries = [
            query.distinct(group_field).values(group_field).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
            for query in self.build_queries(filters, query_string)
        ]
        records = self._query_list(queries, start_time, end_time, offset, limit)
        return [str(get_span_field_value(record, group_field)) for record in records]

    def query_by_group_ids(
        self,
        group_field: str,
        group_ids: list[str],
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> list[dict[str, Any]]:
        queries = [
            query.order_by(OtlpKey.START_TIME).filter(**{f"{group_field}__eq": group_ids})
            for query in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        return self._query_list(queries, start_time, end_time, 0, limit)

    def query_group_trace_list(
        self,
        group_field: str,
        group_ids: list[str],
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> list[dict[str, Any]]:
        fields = [group_field]
        if group_field != OtlpKey.TRACE_ID:
            fields.append(OtlpKey.TRACE_ID)
        queries = [
            query.filter(**{f"{group_field}__eq": group_ids}).distinct(OtlpKey.TRACE_ID).values(*fields)
            for query in self.build_queries()
        ]
        return self._query_list(queries, None, None, 0, limit)

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        if field == "keyword":
            keyword_filter = (
                Q(**{f"{OtlpKey.TRACE_ID}__eq": value})
                | Q(**{f"{OtlpKey.SPAN_ID}__eq": value})
                | Q(**{f"{OtlpKey.get_attributes_key('user.id')}__include": value})
            )
            for conversation_field in CONVERSATION_QUERY_FIELDS:
                keyword_filter |= Q(**{f"{conversation_field}__include": value})
            return q & keyword_filter
        return q


def get_query(data_sources: list[TraceDatasourceTarget]) -> LLMQuery:
    """根据数据源构造 LLM 查询对象。"""

    return LLMQuery(data_sources)
