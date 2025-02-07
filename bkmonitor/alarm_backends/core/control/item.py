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

import logging
from collections import defaultdict
from typing import List

from django.conf import settings
from django.db.models.sql import AND, OR
from django.utils.functional import cached_property

from alarm_backends.core.control.mixins import CheckMixin, DetectMixin, DoubleCheckMixin
from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.strategy.new_strategy import get_metric_id
from bkmonitor.utils.range import load_condition_instance
from bkmonitor.utils.range.target import TargetCondition
from constants.strategy import AGG_METHOD_REAL_TIME

logger = logging.getLogger("core.control")


def gen_condition_matcher(agg_condition):
    or_cond = []
    and_cond = []
    for cond in agg_condition:
        t = {"field": cond["key"], "method": cond["method"], "value": cond["value"]}
        connector = cond.get("condition")
        if connector:
            if connector.upper() == AND:
                and_cond.append(t)
            elif connector.upper() == OR:
                or_cond.append(and_cond)
                and_cond = [t]
            else:
                raise Exception("Unsupported connector(%s)" % connector)
        else:
            and_cond = [t]

    if and_cond:
        or_cond.append(and_cond)

    return load_condition_instance(or_cond)


class Item(DetectMixin, CheckMixin, DoubleCheckMixin):
    def __init__(self, item_config, strategy):
        self.id = item_config.get("id")
        self.name = item_config.get("name")

        self.expression = item_config.get("expression")
        self.functions = item_config.get("functions")
        self.metric_ids = set()
        self.data_source_types = set()
        self.data_source_labels = set()
        self.data_type_labels = set()
        self.units = set()
        self.data_sources = []
        self.algorithms = item_config.get("algorithms", [])
        self.algorithm_connectors = defaultdict(
            lambda: "and",
            {detect["level"]: detect["connector"] or "and" for detect in strategy.config.get("detects", [])},
        )
        self.query_configs = item_config.get("query_configs", [])
        self.no_data_config = item_config.get("no_data_config", {})
        self.target = item_config.get("target", [[]])

        self.item_config = item_config
        self.strategy = strategy

        for query_config in self.query_configs:
            query_config["target"] = self.target
            self.data_source_labels.add(query_config["data_source_label"])
            self.data_type_labels.add(query_config["data_type_label"])
            self.data_source_types.add((query_config["data_source_label"], query_config["data_type_label"]))
            self.metric_ids.add(get_metric_id(**query_config))
            if query_config.get("unit"):
                self.units.add(query_config["unit"])
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            self.data_sources.append(
                data_source_class.init_by_query_config(
                    query_config=query_config,
                    name=self.name,
                    bk_biz_id=self.strategy.bk_biz_id,
                )
            )

        self.unit = list(self.units)[0] if self.units else ""

        self.query = UnifyQuery(
            bk_biz_id=self.strategy.bk_biz_id,
            data_sources=self.data_sources,
            expression=self.expression,
            functions=self.functions,
        )

    def query_record(self, start_time: int, end_time: int) -> List:
        records = self.query.query_data(start_time * 1000, end_time * 1000)
        for record in records:
            record["_time_"] //= 1000
        return records

    @cached_property
    def target_condition_obj(self):
        if not self.target or not self.target[0]:
            return
        return TargetCondition(self.target)

    @cached_property
    def agg_condition_obj(self):
        query_config = self.query_configs[0]
        agg_condition = query_config.get("agg_condition", [])
        if not agg_condition:
            return

        # 实时监控，需要将agg_condition转换成监控目标
        if query_config.get("agg_method", "") != AGG_METHOD_REAL_TIME:
            if not self.data_sources:
                return
            for condition in agg_condition:
                # 无高级条件的配置，数据已经通过查询进行了过滤，因此不需要再次匹配。
                if condition["method"] in self.data_sources[0].ADVANCE_CONDITION_METHOD:
                    break
            else:
                return

        # 忽略第一个condition避免解析错误
        if "condition" in agg_condition[0]:
            del agg_condition[0]["condition"]

        return gen_condition_matcher(agg_condition)

    @cached_property
    def origin_agg_condition_obj(self):
        query_config = self.query_configs[0]
        agg_condition = query_config.get("agg_condition", [])
        if not agg_condition:
            return

        # 实时监控，需要将agg_condition转换成监控目标
        if query_config.get("agg_method", "") != AGG_METHOD_REAL_TIME and not self.data_sources:
            return

        # 忽略第一个condition避免解析错误
        if "condition" in agg_condition[0]:
            del agg_condition[0]["condition"]

        return gen_condition_matcher(agg_condition)

    @cached_property
    def agg_methods(self) -> List[str]:
        """聚合方法列表"""
        methods = []
        for query_config in self.query_configs:
            methods.append(query_config.get("agg_method"))

        return methods

    @cached_property
    def algorithm_types(self) -> List[str]:
        """检测算法列表"""
        types = []
        for algorithm_type in self.algorithms:
            types.append(algorithm_type.get("type"))

        return list(set(types))

    @cached_property
    def extra_agg_condition_obj(self):
        for data_source in self.data_sources:
            if getattr(data_source, "_is_system_disk", lambda: False)():
                and_cond = []
                for file_type in settings.FILE_SYSTEM_TYPE_IGNORE:
                    t = {"field": settings.FILE_SYSTEM_TYPE_FIELD_NAME, "method": "neq", "value": file_type}
                    and_cond.append(t)
                return load_condition_instance([and_cond])

            if getattr(data_source, "_is_system_net", lambda: False)():
                and_cond = []
                for condition in settings.ETH_FILTER_CONDITION_LIST:
                    t = {
                        "field": settings.SYSTEM_NET_GROUP_FIELD_NAME,
                        "method": "neq",
                        "value": condition["sql_statement"],
                    }
                    and_cond.append(t)
                return load_condition_instance([and_cond])

    def is_range_match(self, dimensions):
        # 1. 匹配监控目标
        is_match = True
        target_condition_obj = self.target_condition_obj
        if target_condition_obj:
            is_match = target_condition_obj.is_match(dimensions)

        # 2. 匹配监控条件(即where条件)
        agg_condition_target_obj = self.agg_condition_obj
        if agg_condition_target_obj:
            is_match = is_match and agg_condition_target_obj.is_match(dimensions)

        # 3. 匹配额外的内置监控条件(针对磁盘、网络做的特殊处理)
        extra_agg_condition_target_obj = self.extra_agg_condition_obj
        if extra_agg_condition_target_obj:
            is_match = is_match and extra_agg_condition_target_obj.is_match(dimensions)

        return is_match

    @cached_property
    def use_aiops_sdk(self):
        for query_config in self.query_configs:
            if query_config.get("intelligent_detect") and query_config["intelligent_detect"].get("use_sdk", False):
                return True

        return False
