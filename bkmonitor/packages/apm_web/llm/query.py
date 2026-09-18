"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterator, Mapping
from typing import Any

from django.db.models import Q

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey

from apm_web.handlers.query.span import SpanQuery


class LLMQuery(SpanQuery):
    """查询 LLM Trace 与会话。"""

    # 时序图展示的曲线数上限
    SERIES_LIMIT = 20

    # 按 ID 拉全量 Span 时单次查询的 ID 数；超过后按该大小切片并发请求。
    GROUP_ID_BATCH_SIZE = 30
    GROUP_ID_QUERY_WORKERS = 5

    # 参与求和的每个字段占一个引用别名。
    METRIC_ALIASES: tuple[str, ...] = tuple(f"q{index}" for index in range(8))

    @classmethod
    def _metric_queries(
        cls,
        queries: list[QueryConfigBuilder],
        fields: list[str],
        method: str,
        group_by: list[str],
    ) -> list[QueryConfigBuilder]:
        """一个字段一个引用；应用配置了多个结果表时，每个结果表各出一个。"""
        return [
            query.alias(alias).metric(field=field, method=method, alias=alias).group_by(*group_by)
            for alias, field in zip(cls.METRIC_ALIASES, fields)
            for query in queries
        ]

    @classmethod
    def _sum_expression(cls, fields: list[str]) -> str:
        aliases: tuple[str, ...] = cls.METRIC_ALIASES[: len(fields)]
        if len(aliases) == 1:
            return aliases[0]
        return " + ".join(
            "({} or {})".format(alias, " or ".join(f"{other} * 0" for other in aliases if other != alias))
            for alias in aliases
        )

    def query_field_aggregated_group(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int | None,
        end_time: int | None,
        fields: list[str],
        method: str,
        group_by: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        group_by = group_by or []
        if not group_by and len(fields) == 1:
            # 无维度的单字段聚合直接用标量查询：它额外处理了多结果表下
            # DISTINCT 需枚举合并去重的情况，分组查询替代不了。
            value = self._query_field_aggregated_value(queries, start_time, end_time, fields[0], method)
            return [{"_result_": value or 0}]

        qs = (
            self.get_qs(start_time, end_time)
            .expression(self._sum_expression(fields))
            .time_agg(False)
            .instant()
            .limit(self.QUERY_MAX_LIMIT if group_by else 1)
        )
        return list(self._add_query(qs, self._metric_queries(queries, fields, method, group_by)))

    def query_field_values(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int | None,
        end_time: int | None,
        fields: list[str],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """取回指定字段的原始值，用于存储侧聚合不了、只能本地聚合的场景。

        原始记录按存储结构返回（`attributes.x.y` 会嵌在 attributes 字典里），统一摊平成传入的
        字段名，调用方不必区分扁平键与嵌套路径两种形状。
        """
        records: list[dict[str, Any]] = self._query_list(
            [query.values(*fields) for query in queries], start_time, end_time, 0, limit or self.QUERY_MAX_LIMIT
        )
        return [{field: self._get_field_value(record, field) for field in fields} for record in records]

    def query_field_graph_config(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int | None,
        end_time: int | None,
        fields: list[str],
        method: str,
        interval: int,
        group_by: list[str] | None = None,
    ) -> dict[str, Any]:
        group_by = group_by or []
        expression: str = self._sum_expression(fields)
        config: dict[str, Any] = self._add_query(
            self.get_qs(start_time, end_time)
            .expression(f"topk({self.SERIES_LIMIT}, {expression})" if group_by else expression)
            .time_agg(False),
            # 显式下发聚合周期，不走 grafana 的 auto：它按采集周期取点，时间范围拉长后数据点过密
            [query.interval(interval) for query in self._metric_queries(queries, fields, method, group_by)],
        ).config
        config.update(
            {
                "time_alignment": False,
                "query_method": "query_reference",
                "null_as_zero": True,
                "start_time": config["start_time"] // self.TIME_FIELD_ACCURACY,
                "end_time": config["end_time"] // self.TIME_FIELD_ACCURACY,
            }
        )
        return config

    @staticmethod
    def _get_field_value(record: dict[str, Any], field: str) -> Any:
        """按“扁平键/嵌套路径”提取字段，返回空字符串表示不存在。"""

        def _extract(value: Any, keys: list[str], index: int = 0) -> Any:
            if index >= len(keys):
                return value

            if not isinstance(value, Mapping):
                return ""

            key = keys[index]
            if key in value:
                return _extract(value[key], keys, index + 1)

            remaining_key = ".".join(keys[index:])
            if remaining_key in value:
                return _extract(value[remaining_key], [], len(keys))

            return ""

        if field in record:
            value = record[field]
            if isinstance(value, list):
                return value[0] if value else ""
            return value

        value = _extract(record, field.split("."))
        if isinstance(value, list):
            return value[0] if value else ""
        return value

    def query_group_list(
        self,
        start_time: int | None,
        end_time: int | None,
        group_field: str,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
        extra_filter: Q | None = None,
    ) -> list[Any]:
        builders = self.build_queries(filters, query_string)
        if extra_filter:
            builders = [query.filter(extra_filter) for query in builders]
        queries = [
            query.distinct(group_field).values(group_field).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
            for query in builders
        ]
        records = self._query_list(queries, start_time, end_time, offset, limit)
        result: list[Any] = []
        for record in records:
            value = self._get_field_value(record, group_field)
            if value is not None and value != "":
                result.append(value)
        return result

    def iter_by_group_ids(
        self,
        group_field: str,
        group_ids: list[Any],
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> Iterator[list[dict[str, Any]]]:
        """按 ID 分片拉取 Span，每完成一批就交给调用方。

        全量 `_source` 很大：调用方应在本批算完 compact 结果后丢掉 raw，
        不要先 `extend` 成一张总表。分片仍并发，但生成器按切片顺序产出，
        避免再额外持有一份拼接后的大 list。
        """
        if not group_ids:
            return

        chunks: list[list[Any]] = [
            group_ids[index : index + self.GROUP_ID_BATCH_SIZE]
            for index in range(0, len(group_ids), self.GROUP_ID_BATCH_SIZE)
        ]

        def _query_chunk(chunk: list[Any]) -> list[dict[str, Any]]:
            queries = [
                query.order_by(OtlpKey.START_TIME).filter(**{f"{group_field}__eq": chunk})
                for query in self.build_queries(time_field=OtlpKey.START_TIME)
            ]
            return self._query_list(queries, start_time, end_time, 0, limit)

        if len(chunks) == 1:
            yield _query_chunk(chunks[0])
            return

        worker_count: int = min(self.GROUP_ID_QUERY_WORKERS, len(chunks))
        with ThreadPool(processes=worker_count) as pool:
            # imap 按切片顺序产出；调用方处理完一批后该批才能被回收。
            yield from pool.imap(_query_chunk, chunks)

    def query_by_group_ids(
        self,
        group_field: str,
        group_ids: list[Any],
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> list[dict[str, Any]]:
        """拉取指定 ID 的全部 Span。需要整表时再用；列表接口请走 `iter_by_group_ids`。"""
        spans: list[dict[str, Any]] = []
        for batch in self.iter_by_group_ids(group_field, group_ids, start_time, end_time, limit):
            spans.extend(batch)
        return spans

    def query_group_trace_list(
        self,
        group_field: str,
        group_ids: list[Any],
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


def get_query(data_sources: list[TraceDatasourceTarget]) -> LLMQuery:
    """根据数据源构造 LLM 查询对象。"""

    return LLMQuery(data_sources)
