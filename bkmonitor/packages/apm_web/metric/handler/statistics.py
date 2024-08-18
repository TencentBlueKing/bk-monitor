# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import functools
from dataclasses import dataclass, field
from typing import Callable, List, Type

from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.constants import StatisticsMetric
from apm_web.metric_handler import (
    MetricHandler,
    ServiceFlowAvgDuration,
    ServiceFlowCount,
)
from apm_web.topo.handle import BaseQuery
from apm_web.topo.handle.graph_query import GraphQuery

# 请求数表格列
from core.unit import load_unit

REQUEST_COUNT_COLUMNS = [
    {"id": "service", "name": "服务名称", "type": "link"},
    {"id": "other_service", "name": "调用服务", "type": "string"},
    {"id": "request_count", "name": "调用数", "type": "number", "sortable": "custom"},
    {
        "id": "datapoints",
        "name": "缩略图",
        "type": "datapoints",
    },
]

# 错误数表格列
ERROR_COUNT_COLUMNS = [
    {"id": "service", "name": "服务名称", "type": "link"},
    {"id": "other_service", "name": "调用服务", "type": "string"},
    {"id": "error_count", "name": "错误数", "type": "number", "sortable": "custom"},
    {
        "id": "datapoints",
        "name": "缩略图",
        "type": "datapoints",
    },
]

# 平均耗时表格列
AVG_DURATION_COLUMNS = [
    {"id": "service", "name": "服务名称", "type": "link"},
    {"id": "other_service", "name": "调用服务", "type": "string"},
    {"id": "avg_duration", "name": "平均耗时", "type": "number", "sortable": "custom"},
    {
        "id": "datapoints",
        "name": "缩略图",
        "type": "datapoints",
    },
]


@dataclass
class Template:
    table_group_by: List[str]
    metric: [Type[MetricHandler], functools.partial]
    columns: List[dict]
    ignore_keys: List[str] = field(default_factory=list)
    link_service_field_index: int = 0
    other_service_field_index: int = 1
    unit: Callable = None

    @classmethod
    def key_convert(cls, key_values):
        return {i: key_values[index] for index, i in enumerate(cls.table_group_by)}

    def __post_init__(self):
        if not self.unit:
            self.unit = functools.partial(self.unit_sum, unit="origin")

    @classmethod
    def unit_sum(cls, series, unit):
        if unit == "origin":
            return sum(i[0] for i in series if i[0])
        return load_unit(unit).auto_convert(sum(i[0] for i in series if i[0]), decimal=2)

    @classmethod
    def unit_avg(cls, series, unit):
        if unit == "origin":
            return sum(i[0] for i in series if i[0]) / len(series)
        return load_unit(unit).auto_convert(sum(i[0] for i in series if i[0]) / len(series), decimal=2)

    def value_convert(self, series):
        return self.unit(series)


class ServiceMetricStatistics(BaseQuery):
    """服务指标统计"""

    template_mapping = {
        StatisticsMetric.REQUEST_COUNT.value: {
            "caller": Template(
                table_group_by=["from_apm_service_name", "to_apm_service_name"],
                metric=ServiceFlowCount,
                columns=REQUEST_COUNT_COLUMNS,
            ),
            "callee": Template(
                table_group_by=["to_apm_service_name", "from_apm_service_name"],
                metric=ServiceFlowCount,
                columns=REQUEST_COUNT_COLUMNS,
            ),
        },
        StatisticsMetric.ERROR_COUNT.value: {
            "caller": Template(
                table_group_by=["from_apm_service_name", "to_apm_service_name", "from_span_error"],
                ignore_keys=["from_span_error"],
                metric=functools.partial(
                    ServiceFlowCount, where=[{"key": "from_span_error", "method": "eq", "value": ["true"]}]
                ),
                columns=ERROR_COUNT_COLUMNS,
            ),
            "callee": Template(
                table_group_by=["to_apm_service_name", "from_apm_service_name", "to_span_error"],
                ignore_keys=["to_span_error"],
                metric=functools.partial(
                    ServiceFlowCount, where=[{"key": "to_span_error", "method": "eq", "value": ["true"]}]
                ),
                columns=ERROR_COUNT_COLUMNS,
            ),
        },
        StatisticsMetric.AVG_DURATION.value: {
            "caller": Template(
                table_group_by=["from_apm_service_name", "to_apm_service_name"],
                metric=ServiceFlowAvgDuration,
                columns=AVG_DURATION_COLUMNS,
                unit=functools.partial(Template.unit_avg, unit="µs"),
            ),
            "callee": Template(
                table_group_by=["from_apm_service_name", "to_apm_service_name"],
                metric=ServiceFlowAvgDuration,
                columns=AVG_DURATION_COLUMNS,
                unit=functools.partial(Template.unit_avg, unit="µs"),
            ),
        },
    }

    @classmethod
    def get_template(cls, metric_name, kind):
        t = cls.template_mapping.get(metric_name, {}).get(kind)
        if not t:
            raise ValueError(f"不支持查询 {metric_name} 指标的 {kind} 类型")

        return t

    def __init__(self, *args, **kwargs):
        super(ServiceMetricStatistics, self).__init__(*args, **kwargs)
        self.graph = GraphQuery(*args, **kwargs).create_graph()

    def convert_to_condition(self, service_name):
        return {"service_name": service_name} if service_name else {}

    def list(self, template: Template):

        values_mapping = template.metric(
            self.application,
            self.start_time,
            self.end_time,
            filter_dict=self.filter_params,
            group_by=template.table_group_by,
        ).get_range_values_mapping(ignore_keys=template.ignore_keys)

        mappings = self.graph.node_mapping
        res = []
        for k, series in values_mapping.items():
            service_1 = k[template.link_service_field_index]
            service_2 = k[template.other_service_field_index]
            res.append(
                {
                    "service": {
                        "target": "self",
                        "url": ServiceHandler.build_url(self.app_name, service_1),
                        "name": service_1,
                        "category": mappings.get(service_1).get("data", {}).get("category")
                        if service_1 in mappings
                        else None,
                    },
                    "other_service": {
                        "name": service_2,
                        "category": mappings.get(service_2).get("data", {}).get("category")
                        if service_2 in mappings
                        else None,
                    },
                    self.data_type: template.value_convert(series=series),
                    "datapoints": series,
                }
            )

        return {"data": res, "columns": template.columns}
