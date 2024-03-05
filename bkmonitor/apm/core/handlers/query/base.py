# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from django.utils.functional import classproperty
from django.utils.translation import ugettext_lazy as _
from elasticsearch_dsl import A, Q


class EsOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"


class LogicSupportOperator:
    # 走特殊逻辑可以使用的操作符
    LOGIC = "logic"


class EsQueryBuilderMixin:
    DEFAULT_SORT_FIELD = None

    # 字段候选值最多获取500个
    OPTION_VALUES_MAX_SIZE = 500

    # 时间字段精 用于时间字段查询时做乘法
    TIME_FIELD_ACCURACY = 1000000

    @classproperty
    def operator_mapping(self):
        return {
            EsOperator.EXISTS: lambda q, k, v: q.query("bool", filter=[Q("exists", field=k)]),
            EsOperator.NOT_EXISTS: lambda q, k, v: q.query("bool", must_not=[Q("exists", field=k)]),
            EsOperator.EQUAL: lambda q, k, v: q.query("bool", filter=[Q("terms", **{k: v})]),
            EsOperator.NOT_EQUAL: lambda q, k, v: q.query("bool", must_not=[Q("terms", **{k: v})]),
            EsOperator.BETWEEN: lambda q, k, v: q.query("bool", filter=[Q("range", **{k: {"gte": v[0], "lte": v[1]}})]),
            EsOperator.LIKE: lambda q, k, v: q.query("bool", filter=[Q("wildcard", **{k: f'*{v[0]}*'})]),
            LogicSupportOperator.LOGIC: lambda q, k, v: self._add_logic_filter(q, k, v),
        }

    @classmethod
    def add_time(cls, query, start_time=None, end_time=None, time_field=None):
        if not start_time and not end_time:
            return query

        time_query = {}
        if start_time:
            time_query["gt"] = start_time * cls.TIME_FIELD_ACCURACY
        if end_time:
            time_query["lte"] = end_time * cls.TIME_FIELD_ACCURACY

        if not time_field:
            time_field = cls.DEFAULT_SORT_FIELD
        return query.query(
            "bool",
            filter=[Q("range", **{time_field: time_query})],
        )

    @classmethod
    def add_sort(cls, query, sort_field=None):

        if "sort" in query.to_dict():
            return query

        if not sort_field:
            return query.sort(f"-{cls.DEFAULT_SORT_FIELD}")

        return query.sort(sort_field)

    @classmethod
    def add_filter_params(cls, query, filter_params):

        for i in filter_params:
            query = cls.add_filter_param(query, i)

        return query

    @classmethod
    def add_filter_param(cls, query, filter_param):

        if filter_param["operator"] not in cls.operator_mapping:
            raise ValueError(_("不支持的查询操作符: %s") % (filter_param['operator']))

        key = cls._translate_key(filter_param["key"])
        return cls.operator_mapping[filter_param["operator"]](query, key, filter_param["value"])

    @classmethod
    def _add_logic_filter(cls, query, key, value):
        """生成特殊处理的Filters参数"""
        return query

    @classmethod
    def _translate_key(cls, key):
        return key

    @classmethod
    def distinct_fields(cls, query, field):

        query = query.extra(collapse={"field": field}, track_total_hits=True)
        cls.add_total_size(query, field)
        return query

    @classmethod
    def add_total_size(cls, query, field):
        query.aggs.bucket("total_size", A("cardinality", field=field))

    @classmethod
    def add_filter(cls, query, key, value):
        return query.query("bool", filter=[Q("term", **{key: value})])

    @classmethod
    def _query_option_values(cls, query, fields):

        for i in fields:
            query.aggs.bucket(f"{i}_values", A("terms", field=i, size=cls.OPTION_VALUES_MAX_SIZE))

        query = query.extra(size=0)
        response = query.execute()

        res = {}
        for field in fields:
            values = getattr(response.aggregations, f"{field}_values")
            res[field] = [i["key"] for i in values.buckets]

        return res


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
