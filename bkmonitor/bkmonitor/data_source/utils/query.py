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

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.utils.base import get_bar_interval_number
from bkmonitor.utils.thread_backend import ThreadPool


class BaseQuery:
    USING: tuple[str, str]
    DEFAULT_TIME_FIELD = "time"
    DEFAULT_SORT = ["time"]

    # 枚举查询上限
    QUERY_MAX_LIMIT = 10000

    # 查询字段映射
    KEY_REPLACE_FIELDS: dict[str, str] = {}

    def _get_q(self, time_field: str | None = None) -> QueryConfigBuilder:
        """构建基础查询配置，指定数据源类型和时间字段。

        :param time_field: 时间字段名，默认使用 DEFAULT_TIME_FIELD
        :return: QueryConfigBuilder 实例
        """
        return QueryConfigBuilder(self.USING).time_field(time_field or self.DEFAULT_TIME_FIELD)

    def get_qs(self, start_time: int, end_time: int) -> UnifyQuerySet:
        """构建基础查询集，设置时间范围并关闭时间对齐。

        :param start_time: 开始时间（秒级或毫秒级时间戳）
        :param end_time: 结束时间（秒级或毫秒级时间戳）
        :return: UnifyQuerySet 实例
        """
        start_time, end_time = self._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False)

    @classmethod
    def get_q_from_query_config(cls, query_config: dict[str, Any]) -> QueryConfigBuilder:
        """从查询配置字典构建 QueryConfigBuilder。

        :param query_config: 查询配置字典，包含 data_type_label、data_source_label、table、
                             group_by、where、filter_dict、query_string 等字段
        :return: QueryConfigBuilder 实例
        """
        return (
            QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
            .table(query_config["table"])
            .time_field(query_config.get("time_field") or cls.DEFAULT_TIME_FIELD)
            .group_by(*query_config.get("group_by", []))
            .conditions(query_config.get("where", []))
            .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
            .query_string(query_config.get("query_string") or "")
        )

    @classmethod
    def _translate_field(cls, field: str) -> str:
        """将字段名按 KEY_REPLACE_FIELDS 映射转换，无映射则返回原字段名。

        :param field: 原始字段名
        :return: 转换后的字段名
        """
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def process_sort_fields(cls, fields):
        """
        预处理排序字段列表，调整字段排序格式

        :param fields: 原始排序字段列表，如 ["-time", "name"]
        :return: 处理后的排序字段列表，如 ["time desc", "name"]
        """
        processed_fields = []
        for field in fields:
            # 提取字段名（去掉可能的 "-" 前缀）
            is_descending = field.startswith("-")
            field = field[1:] if is_descending else field

            # 保留原始排序方向
            if is_descending:
                processed_fields.append(f"{field} desc")
            else:
                processed_fields.append(field)
        return processed_fields

    @classmethod
    def _add_query(cls, qs: UnifyQuerySet, q_list: list[QueryConfigBuilder]) -> UnifyQuerySet:
        """将多个查询配置依次添加到查询集中。

        :param qs: 基础查询集
        :param q_list: 待添加的 QueryConfigBuilder 列表
        :return: 添加所有查询后的 UnifyQuerySet
        """
        for q in q_list:
            qs = qs.add_query(q)
        return qs

    @classmethod
    def _to_milliseconds(cls, ts: int) -> int:
        """将秒级时间戳转换为毫秒级，毫秒级时间戳直接返回。

        :param ts: 时间戳（10 位为秒级，13 位为毫秒级）
        :return: 毫秒级时间戳
        """
        return ts * 1000 if len(str(ts)) == 10 else ts

    def _get_time_range(self, start_time: int, end_time: int) -> tuple[int, int]:
        """将开始和结束时间统一转换为毫秒级时间戳。

        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :return: (毫秒级开始时间, 毫秒级结束时间)
        """
        return self._to_milliseconds(start_time), self._to_milliseconds(end_time)

    def _query_list(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """分页查询原始记录列表。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param offset: 分页偏移量，默认 0
        :param limit: 每页返回条数，默认 20
        :return: 记录列表
        """
        qs = self.get_qs(start_time, end_time).offset(offset).limit(limit)
        return list(self._add_query(qs, queries))

    def _query_total(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
    ) -> int:
        """查询记录总数（COUNT）。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :return: 记录总数
        """
        return self._query_field_aggregated_value(queries, start_time, end_time, "_index", "count")

    def _query_field_topk(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        need_empty: bool = False,
    ) -> list[dict[str, Any]]:
        """查询指定字段出现次数最多的 Top-K 值。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param field: 目标字段名
        :param limit: 返回 Top-K 数量，默认 5
        :param need_empty: 为 True 时统计含空值的记录数（使用 _index 计数），默认 False
        :return: 按出现次数降序排列的记录列表，每条记录包含字段值和计数
        """
        alias: str = "a"
        query_limit = limit * 2 + 10
        queries = [
            q.alias(alias)
            .metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
            .group_by(field)
            .order_by("_value desc")
            for q in queries
        ]
        qs = (
            self.get_qs(start_time, end_time)
            .expression(alias)
            .time_agg(False)
            .instant()
            .limit(min(query_limit, self.QUERY_MAX_LIMIT))
        )
        records = list(self._add_query(qs, queries))
        return sorted(records, key=lambda item: item["_result_"], reverse=True)[:limit]

    def _query_option_values(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int = 20,
    ) -> dict[str, list[str]]:
        """并发查询多个字段的可选枚举值。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param fields: 需要枚举可选值的字段列表
        :param limit: 每个字段最多返回的枚举值数量，默认 20
        :return: 字段名到枚举值列表的映射字典
        """
        query_limit = limit * 2 + 10
        qs = (
            self.get_qs(start_time, end_time)
            .expression("a")
            .time_agg(False)
            .instant()
            .limit(min(query_limit, self.QUERY_MAX_LIMIT))
        )
        option_values: dict[str, list[str]] = {field: [] for field in fields}
        ThreadPool().map_ignore_exception(
            self._collect_option_values, [(queries, qs, field, option_values) for field in fields]
        )
        return {field: values[:limit] for field, values in option_values.items()}

    @classmethod
    def _collect_option_values(
        cls, queries: list[QueryConfigBuilder], queryset: UnifyQuerySet, field: str, option_values: dict[str, list[str]]
    ):
        """收集单个字段的枚举值，过滤掉计数为 0 的桶，结果写入 option_values。

        :param queries: 查询配置列表
        :param queryset: 基础查询集（已设置时间范围和分页）
        :param field: 目标字段名
        :param option_values: 结果收集字典，key 为字段名，value 为枚举值列表（原地修改）
        """
        alias = "a"
        queries = [
            q.alias(alias).metric(field=field, method="COUNT", alias=alias).group_by(field).order_by("_value desc")
            for q in queries
        ]
        records = sorted(
            cls._add_query(queryset, queries),
            key=lambda item: item["_result_"],
            reverse=True,
        )
        for bucket in records:
            if bucket["_result_"] == 0:
                continue
            option_values[field].append(bucket[field])

    def _query_graph_config(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 20,
        enable_topk=False,
    ):
        """构建图表配置，按字段分组统计时序数据。

        :param queries: 查询配置列表
        :param start_time: 开始时间戳
        :param end_time: 结束时间戳
        :param field: 分组统计的目标字段名
        :param limit: 最多展示的分组数量，默认 20
        :param enable_topk: 为 True 时使用 topk 表达式过滤，默认 False
        :return: 图表查询配置对象
        """
        alias = "a"
        queries = [
            q.alias(alias)
            .interval(get_bar_interval_number(start_time, end_time))
            .metric(field=field, method="COUNT", alias=alias)
            .group_by(field)
            for q in queries
        ]
        return self._add_query(
            self.get_qs(start_time, end_time)
            .expression(f"topk({limit}, {alias})" if enable_topk else alias)
            .time_agg(False)
            .instant(),
            queries,
        ).config

    def _query_field_aggregated_value(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        method: str,
    ) -> int | float:
        """
        查询字段聚合值。

        - 所有 RT 的 reference 和 metric alias 统一设为 "a"
        - expression 规则：max/min 使用 max(a)/min(a)，其余使用 "a"
        - distinct 保留多 RT 枚举合并去重方式，不直接合并各 RT 的 distinct 标量
        """
        method = method.lower()
        if method == "distinct":
            return self._query_field_distinct_value(queries, start_time, end_time, field)

        alias = "a"
        queries = [q.alias(alias).metric(field=field, method=method, alias=alias) for q in queries]
        qs = (
            self.get_qs(start_time, end_time)
            .expression(f"{method}(a)" if method in {"max", "min"} else "a")
            .time_agg(False)
            .instant()
            .limit(1)
        )
        return list(self._add_query(qs, queries))[0]["_result_"]

    def _query_field_distinct_value(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
    ) -> int:
        """
        查询字段去重数量。

        通过枚举所有值后合并去重计算，而非直接合并各 RT 的 distinct 标量，
        避免多 RT 场景下重叠值被重复计数。
        """
        alias = "a"
        # 单 RT 直接使用存储侧 distinct
        base_qs = self.get_qs(start_time, end_time).expression(alias).time_agg(False).instant()
        if len(queries) == 1:
            queries = [q.alias(alias).metric(field=field, method="distinct", alias=alias) for q in queries]
            return list(self._add_query(base_qs, queries).limit(1))[0]["_result_"]

        # 多 RT 需要枚举后合并去重
        queries = [
            q.alias(alias).metric(field=field, method="COUNT", alias=alias).group_by(field).order_by("_value desc")
            for q in queries
        ]
        distinct_values: set[Any] = set()
        for record in self._add_query(base_qs.limit(self.QUERY_MAX_LIMIT), queries):
            if record.get("_result_", 0) == 0:
                continue
            distinct_values.add(record.get(field))
        return len(distinct_values)
