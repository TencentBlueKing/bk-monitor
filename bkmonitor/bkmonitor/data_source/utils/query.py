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
from django.utils.functional import classproperty
from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions
from bkmonitor.data_source.utils import types

from constants.data_source import OperatorGroupRelation


class FilterOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"
    NOT_LIKE = "not_like"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"

    UNIFY_QUERY_OPERATOR_MAPPING = {
        EXISTS: "exists",
        NOT_EXISTS: "nexists",
        EQUAL: "eq",
        NOT_EQUAL: "neq",
        LIKE: "include",
        NOT_LIKE: "exclude",
        GT: "gt",
        LT: "lt",
        GTE: "gte",
        LTE: "lte",
    }

    UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING = {
        LIKE: "wildcard",
        NOT_LIKE: "nwildcard",
    }

    @classproperty
    def operator_handler_mapping(cls) -> dict[str, Callable[[QueryConfigBuilder, str, types.FilterValue], Q]]:
        return {
            cls.BETWEEN: cls._between_operator_handler,
            cls.EXISTS: cls._existence_operator_handler,
            cls.NOT_EXISTS: cls._existence_operator_handler,
        }

    @classmethod
    def _between_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        return q & Q(**{f"{field}__gte": value[0], f"{field}__lt": value[1]})

    @classmethod
    def _default_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        # 字段不等于 "" 的情况下，需要过滤出字段存在的情况
        if operator == FilterOperator.NOT_EQUAL and "" in value:
            q &= Q(**{f"{field}__{FilterOperator.EXISTS}": [""]})

        # 操作符映射，如果是通配符查询的话需要映射到特定操作符
        if operator in cls.UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING and options.get("is_wildcard"):
            operator = cls.UNIFY_QUERY_WILDCARD_OPERATOR_MAPPING[operator]
        else:
            operator = cls.UNIFY_QUERY_OPERATOR_MAPPING[operator]

        # 处理组间关系查询
        if options.get("group_relation") == OperatorGroupRelation.AND:
            result_q = Q()
            for v in value:
                result_q &= Q(**{f"{field}__{operator}": v})
        else:
            result_q = Q(**{f"{field}__{operator}": value})

        return q & result_q

    @classmethod
    def _existence_operator_handler(
        cls, q: Q, operator: str, field: str, value: types.FilterValue, options: dict[str, Any]
    ) -> Q:
        """
        处理存在性相关操作符 (exists/not exists)
        """
        operator = cls.UNIFY_QUERY_OPERATOR_MAPPING[operator]
        return q & Q(**{f"{field}__{operator}": [""]})

    @classmethod
    def get_handler(cls, operator: str) -> Callable[[Q, str, str, types.FilterValue, dict[str, Any]], Q]:
        if operator in cls.UNIFY_QUERY_OPERATOR_MAPPING or operator in cls.operator_handler_mapping:
            return cls.operator_handler_mapping.get(operator, cls._default_operator_handler)
        raise ValueError(_(f"不支持的查询操作符: {operator}"))


class LogicSupportOperator:
    # 走特殊逻辑可以使用的操作符
    LOGIC = "logic"


class BaseQuery:
    DEFAULT_TIME_FIELD = "time"
    DEFAULT_SORT = ["time"]

    # 查询字段映射
    KEY_REPLACE_FIELDS: dict[str, str] = {}

    @classmethod
    def get_q_from_query_config(cls, query_config: dict[str, Any]) -> QueryConfigBuilder:
        return (
            QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
            .table(query_config["table"])
            .time_field(cls.DEFAULT_TIME_FIELD)
            .group_by(*query_config.get("group_by", []))
            .conditions(query_config.get("where", []))
            .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
            .query_string(query_config.get("query_string") or "")
        )

    @classmethod
    def _translate_field(cls, field: str) -> str:
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        return q

    @classmethod
    def _build_filters(cls, filters: list[types.Filter] | None) -> Q:
        if not filters:
            return Q()

        q: Q = Q()
        for f in filters:
            operator = f["operator"]
            key = cls._translate_field(f["key"])
            # 更新 q，叠加查询条件
            if operator == LogicSupportOperator.LOGIC:
                q = cls._add_logic_filter(q, key, f["value"])
            else:
                q = FilterOperator.get_handler(operator)(q, operator, key, f["value"], f.get("options", {}))
        return q

    @classmethod
    def build_query_q(cls, q: QueryConfigBuilder, filters: list[types.Filter] | None, query_string: str = ""):
        return q.filter(cls._build_filters(filters)).query_string(query_string)

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
        for q in q_list:
            qs = qs.add_query(q)
        return qs

    @classmethod
    def _to_milliseconds(cls, ts: int) -> int:
        return ts * 1000 if len(str(ts)) == 10 else ts

    def _get_time_range(self, start_time: int, end_time: int) -> tuple[int, int]:
        return self._to_milliseconds(start_time), self._to_milliseconds(end_time)

    def time_range_queryset(self, start_time: int, end_time: int) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False)

    def _query_list(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        qs = self.time_range_queryset(start_time, end_time).offset(offset).limit(limit)
        return list(self._add_query(qs, queries))

    def _query_total(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
    ) -> int:
        alias = "a"
        queries = [q.alias(alias).metric(field="_index", method="COUNT", alias=alias) for q in queries]
        qs = self.time_range_queryset(start_time, end_time).time_agg(False).instant().limit(1)
        return list(self._add_query(qs, queries))[0]["_result_"]

    def _query_field_topk(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        need_empty: bool = False,
    ) -> list[dict[str, Any]]:
        alias: str = "a"
        queries = [
            q.metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
            .group_by(field)
            .order_by("_value desc")
            for q in queries
        ]
        qs = self.time_range_queryset(start_time, end_time).expression(alias).time_agg(False).instant().limit(limit)
        return list(self._add_query(qs, queries))
