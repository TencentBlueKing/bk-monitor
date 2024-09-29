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
import copy
import functools
from dataclasses import dataclass, field
from typing import Callable, List, Type

from django.utils.translation import ugettext_lazy as _

from apm_web.constants import TopoNodeKind
from apm_web.metric.constants import ErrorMetricCategory, StatisticsMetric
from apm_web.metric_handler import (
    MetricHandler,
    ServiceFlowAvgDuration,
    ServiceFlowCount,
    ServiceFlowDurationBucket,
    ServiceFlowDurationMax,
    ServiceFlowDurationMin,
    ServiceFlowErrorRateCaller,
)
from apm_web.topo.handle import BaseQuery
from apm_web.topo.handle.bar_query import LinkHelper
from apm_web.topo.handle.graph_query import GraphQuery

# 请求数表格列
from apm_web.utils import get_interval_number
from core.unit import load_unit
from monitor_web.models.scene_view import SceneViewModel

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

# 错误率表格列
ERROR_RATE_COLUMNS = [
    {"id": "service", "name": "服务名称", "type": "link"},
    {"id": "other_service", "name": "调用服务", "type": "string"},
    {"id": "error_rate", "name": "错误列", "type": "number", "sortable": "custom"},
    {
        "id": "datapoints",
        "name": "缩略图",
        "type": "datapoints",
    },
]


# 平均耗时表格列
def get_duration_columns(dimension="default"):
    return [
        {"id": "service", "name": "服务名称", "type": "link"},
        {"id": "other_service", "name": "调用服务", "type": "string"},
        {
            "id": "avg_duration",
            "name": "平均耗时" if dimension == "default" else dimension,
            "type": "number",
            "sortable": "custom",
        },
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
    dimension: str = None
    dimension_category: str = None
    filter_dict: dict = field(default_factory=dict)

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

    @classmethod
    def get_filter_dict(cls, service_name, option_kind):
        # 因为全部都是 flow 指标 所以这里直接固定维度
        if option_kind == "caller":
            return {"from_apm_service_name": service_name}
        if option_kind == "callee":
            return {"to_apm_service_name": service_name}
        return {}


class ServiceMetricStatistics(BaseQuery):
    """服务指标统计"""

    template_mapping = {
        StatisticsMetric.REQUEST_COUNT.value: {
            "default": {
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
            }
        },
        StatisticsMetric.ERROR_COUNT_CODE.value: {
            "default": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name", "from_span_error"],
                    ignore_keys=["from_span_error"],
                    metric=ServiceFlowCount,
                    filter_dict={"from_span_error": "true"},
                    columns=ERROR_COUNT_COLUMNS,
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name", "to_span_error"],
                    ignore_keys=["to_span_error"],
                    metric=ServiceFlowCount,
                    filter_dict={"to_span_error": "true"},
                    columns=ERROR_COUNT_COLUMNS,
                ),
            }
        },
        StatisticsMetric.ERROR_COUNT.value: {
            "default": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name", "from_span_error"],
                    ignore_keys=["from_span_error"],
                    metric=ServiceFlowCount,
                    filter_dict={"from_span_error": "true"},
                    columns=ERROR_COUNT_COLUMNS,
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name", "to_span_error"],
                    ignore_keys=["to_span_error"],
                    metric=ServiceFlowCount,
                    filter_dict={"to_span_error": "true"},
                    columns=ERROR_COUNT_COLUMNS,
                ),
            }
        },
        StatisticsMetric.ERROR_RATE.value: {
            "default": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    ignore_keys=["from_span_error", "to_span_error"],
                    metric=ServiceFlowErrorRateCaller,
                    columns=ERROR_RATE_COLUMNS,
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    ignore_keys=["from_span_error", "to_span_error"],
                    metric=ServiceFlowCount,
                    columns=ERROR_RATE_COLUMNS,
                ),
            }
        },
        StatisticsMetric.AVG_DURATION.value: {
            "default": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=ServiceFlowAvgDuration,
                    columns=get_duration_columns(),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=ServiceFlowAvgDuration,
                    columns=get_duration_columns(),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
            "P50": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.5"}]}],
                    ),
                    columns=get_duration_columns("P50"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.5"}]}],
                    ),
                    columns=get_duration_columns("P50"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
            "P95": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
                    ),
                    columns=get_duration_columns("P95"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
                    ),
                    columns=get_duration_columns("P95"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
            "P99": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
                    ),
                    columns=get_duration_columns("P99"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=functools.partial(
                        ServiceFlowDurationBucket,
                        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
                    ),
                    columns=get_duration_columns("P99"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
            "MAX": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=ServiceFlowDurationMax,
                    columns=get_duration_columns("MAX"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=ServiceFlowDurationMax,
                    columns=get_duration_columns("MAX"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
            "MIN": {
                "caller": Template(
                    table_group_by=["from_apm_service_name", "to_apm_service_name"],
                    metric=ServiceFlowDurationMin,
                    columns=get_duration_columns("MIN"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
                "callee": Template(
                    table_group_by=["to_apm_service_name", "from_apm_service_name"],
                    metric=ServiceFlowDurationMin,
                    columns=get_duration_columns("MIN"),
                    unit=functools.partial(Template.unit_avg, unit="µs"),
                ),
            },
        },
    }

    virtual_service_name = _("其他服务")

    @classmethod
    def get_template(cls, metric_name, kind, dimension, service_name=None, dimension_category=None):

        dimension_metric = cls.template_mapping.get(metric_name, {}).get(dimension)
        if not dimension_metric:
            dimension_metric = cls.template_mapping.get(metric_name, {}).get("default")

        if not dimension_metric:
            raise ValueError(f"不支持查询 {metric_name} 指标的 {dimension} 维度下的 {kind} 类型")

        dimension_metric = dimension_metric.get(kind)
        res = copy.deepcopy(dimension_metric)
        res.dimension = dimension
        if service_name:
            res.filter_dict.update(res.get_filter_dict(service_name, kind))
        res.dimension_category = dimension_category
        return res

    def __init__(self, *args, **kwargs):
        super(ServiceMetricStatistics, self).__init__(*args, **kwargs)
        self.graph = GraphQuery(*args, **kwargs).create_graph()
        self.views = SceneViewModel.objects.filter(bk_biz_id=self.bk_biz_id, scene_id="apm_service")

    def list(self, template: Template):
        instance_values_mapping = {}
        if self.data_type == StatisticsMetric.ERROR_RATE.value:
            values_mapping = template.metric(
                self.application,
                self.start_time,
                self.end_time,
                filter_dict=template.filter_dict,
                group_by=template.table_group_by,
                interval=get_interval_number(self.start_time, self.end_time),
            ).get_range_calculate_values_mapping(ignore_keys=template.ignore_keys)
            instance_values_mapping = template.metric(
                self.application,
                self.start_time,
                self.end_time,
                filter_dict=template.filter_dict,
                group_by=template.table_group_by,
                interval=get_interval_number(self.start_time, self.end_time),
            ).get_instance_calculate_values_mapping(ignore_keys=template.ignore_keys)
        elif template.dimension == "default" or self.data_type == StatisticsMetric.AVG_DURATION.value:
            values_mapping = template.metric(
                self.application,
                self.start_time,
                self.end_time,
                filter_dict=template.filter_dict,
                group_by=template.table_group_by,
                interval=get_interval_number(self.start_time, self.end_time),
            ).get_range_values_mapping(ignore_keys=template.ignore_keys)
        elif self.data_type == StatisticsMetric.ERROR_COUNT_CODE.value:
            # 错误数的维度是错误码
            if template.dimension_category not in ErrorMetricCategory.get_dict_choices():
                raise ValueError(f"[指标统计] 查询错误码为: {template.dimension} 时需要指定来源类型 (Http / Rpc)")

            if template.dimension_category == ErrorMetricCategory.HTTP.value:
                if self.params.get("option_kind") == "caller":
                    wheres = [{"key": "from_span_http_status_code", "method": "eq", "value": template.dimension}]
                else:
                    wheres = [{"key": "to_span_http_status_code", "method": "eq", "value": template.dimension}]
            else:
                if self.params.get("option_kind") == "caller":
                    wheres = [{"key": "from_span_grpc_status_code", "method": "eq", "value": template.dimension}]
                else:
                    wheres = [{"key": "to_span_grpc_status_code", "method": "eq", "value": template.dimension}]

            values_mapping = template.metric(
                self.application,
                self.start_time,
                self.end_time,
                filter_dict=template.filter_dict,
                group_by=template.table_group_by,
                where=wheres,
                interval=get_interval_number(self.start_time, self.end_time),
            ).get_range_values_mapping(ignore_keys=template.ignore_keys)
        else:
            raise ValueError(f"不支持查询指标为: {self.data_type} 的 {template.dimension} 维度数据")

        mappings = self.graph.node_mapping
        res = []
        for k, series in values_mapping.items():
            service_1 = k[template.link_service_field_index]
            service_2 = k[template.other_service_field_index]
            service_1_kind = mappings.get(service_1).get("data", {}).get("kind")
            service_2_kind = mappings.get(service_2).get("data", {}).get("kind")

            if service_1_kind == TopoNodeKind.VIRTUAL_SERVICE:
                service_1_url = ""
                service_1_name = self.virtual_service_name
            else:
                service_1_url = LinkHelper.get_service_overview_tab_link(
                    self.bk_biz_id,
                    self.app_name,
                    service_1,
                    self.start_time,
                    self.end_time,
                    views=self.views,
                )
                service_1_name = service_1

            if service_2_kind == TopoNodeKind.VIRTUAL_SERVICE:
                service_2_name = self.virtual_service_name
            else:
                service_2_name = service_2

            if self.data_type != StatisticsMetric.ERROR_RATE.value:
                data_type_value = template.value_convert(series=series)
            else:
                # 如果是错误率图表 需要从实例查询中获取错误率百分比而不是通过计算
                data_type_value = instance_values_mapping.get((service_1_name, service_2_name), {}).get(
                    template.metric.metric_id
                )

            res.append(
                {
                    "service": {
                        "target": "self",
                        "url": service_1_url,
                        "name": service_1_name,
                        "category": mappings.get(service_1).get("data", {}).get("category")
                        if service_1 in mappings
                        else None,
                    },
                    "other_service": {
                        "name": service_2_name,
                        "category": mappings.get(service_2).get("data", {}).get("category")
                        if service_2 in mappings
                        else None,
                    },
                    self.data_type: data_type_value,
                    "datapoints": series,
                }
            )

        return {"data": res, "columns": template.columns}
