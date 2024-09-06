# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import List, Tuple

from django.utils.functional import classproperty
from django.utils.translation import ugettext_lazy as _
from elasticsearch_dsl import Q, Search
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.constants import (
    METRIC_MAP,
    METRIC_PARAM_MAP,
    METRIC_RATE_TUPLE,
    METRIC_RELATION_MAP,
    METRIC_VALUE_COUNT_TUPLE,
)
from apm_web.handlers.component_handler import ComponentHandler
from constants.apm import OtlpKey
from core.drf_resource import api


class EsOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"


class DbStatisticsHandler:
    @classmethod
    def parse_buckets(cls, buckets: list, metric_list: list):
        """
        指标解析
        :param metric_list: 指标列表
        :param buckets: 指标结果集
        :return:
        """
        res = []
        for bucket in buckets:
            item = bucket.get("key")
            if not item:
                continue
            for metric in metric_list:
                if metric in METRIC_PARAM_MAP:
                    item[metric] = bucket.get(metric, {}).get("count", {}).get("value")
                else:
                    item[metric] = bucket.get(metric, {}).get("value")
            res.append(item)
        return res

    @staticmethod
    def handle_metric(metric_set: set):
        """
        指标补齐，防止xxx成功率，xxx占比计算失败
        :param metric_set: 指标集合
        :return:
        """
        metric_relation_set = set()
        for metric in metric_set:
            if metric in METRIC_RATE_TUPLE:
                metric_relation_set.update(METRIC_RELATION_MAP.get(metric))
        final_metric_set = metric_set.union(metric_relation_set)

        return final_metric_set

    def build_es_dsl(self, metric_set: set, group_by_key: str):
        """
        构建聚和条件
        :param metric_set: 指标集合
        :param group_by_key: 分组字段名称
        :return:
        """

        if metric_set:
            metric_set = self.handle_metric(metric_set)
        metric_aggs = {}
        for metric in metric_set:
            if metric in METRIC_PARAM_MAP:
                _aggs = METRIC_MAP.get(metric)
                _aggs["aggs"]["count"]["value_count"]["field"] = group_by_key
                _aggs.update(METRIC_PARAM_MAP.get(metric))
                metric_aggs[metric] = _aggs
            elif metric in METRIC_MAP:
                _tem = METRIC_MAP.get(metric)
                if metric in METRIC_VALUE_COUNT_TUPLE:
                    _tem[metric]["value_count"]["field"] = group_by_key
                metric_aggs.update(_tem)
        return metric_aggs


class DbQuery:
    def __init__(self):
        self.search_object = Search()

    DEFAULT_SORT_FIELD = "start_time"

    @classproperty
    def operator_mapping(self):
        return {
            EsOperator.EXISTS: lambda q, k, v: q.filter(Q("exists", field=k)),
            EsOperator.NOT_EXISTS: lambda q, k, v: q.filter("bool", must_not=[Q("exists", field=k)]),
            EsOperator.EQUAL: lambda q, k, v: q.filter(Q("terms", **{k: v})),
            EsOperator.NOT_EQUAL: lambda q, k, v: q.filter("bool", must_not=[Q("terms", **{k: v})]),
            EsOperator.BETWEEN: lambda q, k, v: q.filter(Q("range", **{k: {"gte": v[0], "lte": v[1]}})),
            EsOperator.LIKE: lambda q, k, v: q.filter(Q("wildcard", **{k: f'*{v[0]}*'})),
        }

    @classmethod
    def add_filter_params(cls, query, filter_params):
        for i in filter_params:
            query = cls.add_filter_param(query, i)

        return query

    @classmethod
    def add_filter_param(cls, query, filter_param):
        if filter_param["operator"] not in cls.operator_mapping:
            raise ValueError(_("不支持的查询操作符: %s") % (filter_param['operator']))
        return cls.operator_mapping[filter_param["operator"]](query, filter_param["key"], filter_param["value"])

    @classmethod
    def add_time(cls, query, start_time, end_time, time_field=None):
        time_query = {}
        if start_time:
            time_query["gt"] = start_time * 1000000
        if end_time:
            time_query["lte"] = end_time * 1000000

        if not time_field:
            time_field = cls.DEFAULT_SORT_FIELD
        return query.filter(Q("range", **{time_field: time_query}))

    def build_param(self, start_time=None, end_time=None, filter_params=None, es_dsl=None, exclude_field=None) -> dict:
        query = self.search_object
        if es_dsl:
            query = query.update_from_dict(es_dsl)

        if start_time and end_time:
            query = self.add_time(query, start_time, end_time)

        if filter_params:
            query = self.add_filter_params(query, filter_params)

        if exclude_field:
            query = query.source(exclude=exclude_field)

        return query.to_dict()


class DbInstanceHandler:
    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.rule = self.get_rules()

    def get_rules(self):
        """
        获取组件DB的发现规则
        :return:
        """

        rules = api.apm_api.query_discover_rules(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            filters={
                "topo_kind": "component",
                "category_id": "db",
            },
        )

        if not rules:
            raise ValueError(_("拓扑发现规则为空"))

        return rules[0]

    @staticmethod
    def get_topo_instance_key(keys: List[Tuple[str, str]], item):
        instance_keys = []
        for first_key, second_key in keys:
            key = item.get(first_key, item).get(second_key, "")
            instance_keys.append(str(key))
        return ":".join(instance_keys)

    def get_instance(self, item):
        """
        获取DB实例
        :param item: span 数据
        :return:
        """

        instance_keys = [self._get_key_pair(i) for i in self.rule.get("instance_key", "").split(",")]

        return self.get_topo_instance_key(instance_keys, item)

    @staticmethod
    def _get_key_pair(key: str):
        pair = key.split(".", 1)
        if len(pair) == 1:
            return "", pair[0]
        return pair[0], pair[1]


class DbComponentHandler(ComponentHandler):
    exists_component_params_map = {
        "db": {
            "key": OtlpKey.get_attributes_key(SpanAttributes.DB_SYSTEM),
            "op": "exists",
            "value": [""],
            "condition": "and",
        },
        "messaging": {
            "key": OtlpKey.get_attributes_key(SpanAttributes.MESSAGING_SYSTEM),
            "op": "exists",
            "value": [""],
            "condition": "and",
        },
    }

    @classmethod
    def build_db_system_param(cls, category, db_system=None):
        """
        构建 DB 实例查询条件
        :param db_system:
        :param category:
        :return:
        """

        if category not in cls.exists_component_params_map:
            return []

        if not db_system:
            return [cls.exists_component_params_map.get(category)]
        return []
