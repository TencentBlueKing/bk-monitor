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
from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.trace import SpanAttributes
from apm_web.handlers.component_handler import ComponentHandler
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import OtlpKey
from constants.data_source import DataTypeLabel, DataSourceLabel
from core.drf_resource import api


class FilterOperator:
    """检索支持的操作符"""

    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"


class DbQuery:
    _OPERATOR_MAPPING: dict[str, Callable[[Q, str, list], Q]] = {
        FilterOperator.EXISTS: lambda q, k, v: q & Q(**{f"{k}__exists": [""]}),
        FilterOperator.NOT_EXISTS: lambda q, k, v: q & Q(**{f"{k}__nexists": [""]}),
        FilterOperator.EQUAL: lambda q, k, v: q & Q(**{f"{k}__eq": v}),
        FilterOperator.NOT_EQUAL: lambda q, k, v: q & Q(**{f"{k}__neq": v}),
        FilterOperator.BETWEEN: lambda q, k, v: q & Q(**{f"{k}__gte": v[0], f"{k}__lte": v[1]}),
        FilterOperator.LIKE: lambda q, k, v: q & Q(**{f"{k}__wildcard": f"*{v[0]}*"}),
    }

    @classmethod
    def get_q(
        cls,
        table_id: str,
    ) -> QueryConfigBuilder:
        return (
            QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table(table_id).time_field(OtlpKey.END_TIME)
        )

    @classmethod
    def get_qs(cls, bk_biz_id: int, start_time: int, end_time: int) -> UnifyQuerySet:
        return (
            UnifyQuerySet().scope(bk_biz_id).time_align(False).start_time(start_time * 1000).end_time(end_time * 1000)
        )

    @classmethod
    def build_filter_params(cls, filter_params: list[dict[str, Any]]) -> Q:
        """根据过滤参数构建查询条件"""
        q: Q = Q()
        for filter_param in filter_params:
            if filter_param["operator"] not in cls._OPERATOR_MAPPING:
                raise ValueError(_("不支持的查询操作符: %s") % (filter_param["operator"]))
            q = cls._OPERATOR_MAPPING[filter_param["operator"]](q, filter_param["key"], filter_param["value"])
        return q


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
    def get_topo_instance_key(keys: list[tuple[str, str]], item):
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
