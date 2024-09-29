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
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Type, Union

from django.utils.translation import ugettext_lazy as _

from apm_web.constants import AlertLevel, Apdex, TopoNodeKind, TopoVirtualServiceKind
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric_handler import (
    ApdexInstance,
    MetricHandler,
    ServiceFlowAvgDuration,
    ServiceFlowCount,
    ServiceFlowDurationBucket,
    ServiceFlowDurationMax,
    ServiceFlowDurationMin,
    ServiceFlowErrorRateCaller,
)
from apm_web.topo.constants import (
    BarChartDataType,
    GraphPluginType,
    GraphViewType,
    TopoEdgeDataType,
)
from apm_web.topo.handle.bar_query import LinkHelper
from apm_web.utils import merge_dicts
from constants.apm import OtlpKey
from core.drf_resource import api
from core.unit import load_unit
from fta_web.alert.handlers.alert import AlertQueryHandler
from monitor_web.models.scene_view import SceneViewModel


@dataclass
class Plugin:
    """节点&边插件"""

    id: str
    type: GraphPluginType

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


@dataclass
class PrePlugin(Plugin):
    """前置插件 (通常用来获取指标数据)"""

    metric: Type[MetricHandler] = None
    _runtime: dict = field(default_factory=dict)
    is_common: bool = False

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        raise NotImplementedError

    @classmethod
    def diff(cls, attrs, other_attrs):
        """获取对比信息"""

        base_count = attrs.get(f"_{cls.id}", attrs.get(cls.id))
        other_count = other_attrs.get(f"_{cls.id}", other_attrs.get(cls.id))

        return {
            cls.id: [
                {
                    "id": cls.id,
                    "name": BarChartDataType.get_choice_label(cls.id),
                    "base": base_count,
                    "diff": other_count,
                }
            ]
        }


@dataclass
class PostPlugin(Plugin):
    """后置插件"""

    _runtime: dict = field(default_factory=dict)

    def process(self, *args, **kwargs):
        raise NotImplementedError


class ValuesPluginMixin:
    def get_increase_values_mapping(self, **kwargs) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        params = {
            "application": self._runtime["application"],
            "start_time": self._runtime["start_time"],
            "end_time": self._runtime["end_time"],
            **kwargs,
        }

        if self.type == GraphPluginType.ENDPOINT:
            params = self.add_endpoint_query(params, self._runtime["endpoint_names"])

        m = self.metric(**params)
        response = m.get_instance_values_mapping(ignore_keys=self._ignore_keys())
        res = defaultdict(lambda: defaultdict(int))
        for k, v in response.items():
            for i in k:
                res[(i,)][self.id] += v[m.metric_id]
        return dict(res)

    def get_instance_values_mapping(self, **kwargs) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        params = {
            "application": self._runtime["application"],
            "start_time": self._runtime["start_time"],
            "end_time": self._runtime["end_time"],
            **kwargs,
        }

        if self.type == GraphPluginType.ENDPOINT:
            params = self.add_endpoint_query(params, self._runtime["endpoint_names"])

        metric = self.metric(**params)
        mappings = metric.get_instance_values_mapping(ignore_keys=self._ignore_keys())
        res = {}
        for k, v in mappings.items():
            # 还需要保存原始值 以便后面插件进行处理
            res[k] = {self.id: self._to_value(v[metric.metric_id]), f"_{self.id}": v[metric.metric_id]}

        return res

    def get_instance_calculate_values_mapping(self, **kwargs):
        params = {
            "application": self._runtime["application"],
            "start_time": self._runtime["start_time"],
            "end_time": self._runtime["end_time"],
            **kwargs,
        }

        if self.type == GraphPluginType.ENDPOINT:
            params = self.add_endpoint_query(params, self._runtime["endpoint_names"])

        metric = self.metric(**params)
        mappings = metric.get_instance_calculate_values_mapping(ignore_keys=self._ignore_keys())
        res = {}
        for k, v in mappings.items():
            res[k] = {self.id: self._to_value(v[metric.metric_id]), f"_{self.id}": v[metric]}

        return res

    def _to_value(self, value):
        """value 转换"""
        return value

    @classmethod
    def _ignore_keys(cls):
        return []

    def add_endpoint_query(self, params, endpoint_names):
        if "service_name" not in self._runtime or "endpoint_names" not in self._runtime:
            raise ValueError("查询接口指标时需要指定服务名称、接口名称")
        if any(i.get("condition") == "or" for i in params.get("where", [])):
            raise ValueError("当前接口查询包含 or 条件 会导致查询结果错误")

        return params


class SimpleMetricInstanceValuesMixin(PrePlugin, ValuesPluginMixin):
    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


class DurationUnitMixin:
    def __post_init__(self):
        self.converter = load_unit("µs")

    def _to_value(self, value):
        return "".join([str(i) for i in self.converter.auto_convert(decimal=2, value=value)]) if value else None


class PluginProvider:
    @dataclass
    class Container:
        _plugins: List = field(default_factory=list)

        def __iter__(self):
            pure_res = []
            keys = []
            for i in self._plugins:
                key = (i.id, i.type)
                if key in keys:
                    continue
                keys.append(key)
                pure_res.append(i)
            yield from pure_res

        def __add__(self, other: "PluginProvider.Container"):
            self._plugins.extend(other._plugins)
            return self

    common_mappings = defaultdict(list)
    mappings = defaultdict(dict)

    post_mappings = defaultdict(list)

    @classmethod
    def pre_plugin(cls, plugin: PrePlugin):
        if plugin.is_common:
            cls.common_mappings[plugin.type].append(plugin)
        else:
            cls.mappings[plugin.type][plugin.id] = plugin
        return plugin

    @classmethod
    def post_plugin(cls, plugin: PostPlugin):
        cls.post_mappings[plugin.type].append(plugin)
        return plugin

    @classmethod
    def node_plugins(cls, node_data_type, runtime):
        common_plugin_instances = [i(_runtime=runtime) for i in cls.common_mappings[GraphPluginType.NODE]]
        plugin_instance = cls.mappings[GraphPluginType.NODE][node_data_type](_runtime=runtime)
        return cls.Container(_plugins=common_plugin_instances + [plugin_instance])

    @classmethod
    def edge_plugins(cls, edge_data_type, runtime):
        common_plugin_instances = [i(_runtime=runtime) for i in cls.common_mappings[GraphPluginType.EDGE]]
        plugin_instance = cls.mappings[GraphPluginType.EDGE][edge_data_type](_runtime=runtime)
        return cls.Container(_plugins=common_plugin_instances + [plugin_instance])

    @classmethod
    def endpoint_plugins(cls, runtime):
        # 接口的插件是固定的
        common_plugin_instances = [i(_runtime=runtime) for i in cls.common_mappings[GraphPluginType.ENDPOINT]]
        plugin_instances = [i(_runtime=runtime) for i in cls.mappings[GraphPluginType.ENDPOINT].values()]
        return cls.Container(_plugins=common_plugin_instances + plugin_instances)

    @classmethod
    def get_node_plugin(cls, node_data_type, runtime):
        return cls.mappings[GraphPluginType.NODE][node_data_type](_runtime=runtime)

    @classmethod
    def list_endpoint_post_plugin(cls, runtime):
        return cls.Container(_plugins=[i(_runtime=runtime) for i in cls.post_mappings[GraphPluginType.ENDPOINT_UI]])


@PluginProvider.pre_plugin
@dataclass
class EdgeRequestCount(PrePlugin, ValuesPluginMixin):
    """节点间线条请求量"""

    id: str = TopoEdgeDataType.REQUEST_COUNT.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowCount,
        group_by=[
            "from_apm_service_name",
            "to_apm_service_name",
        ],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class EdgeAvgDuration(DurationUnitMixin, ValuesPluginMixin, PrePlugin):
    id: str = TopoEdgeDataType.DURATION_AVG.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowAvgDuration,
        group_by=["from_apm_service_name", "to_apm_service_name"],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class EdgeDurationP50(DurationUnitMixin, ValuesPluginMixin, PrePlugin):
    id: str = TopoEdgeDataType.DURATION_P50.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name", "to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.50"}]}],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class EdgeDurationP95(DurationUnitMixin, ValuesPluginMixin, PrePlugin):
    id: str = TopoEdgeDataType.DURATION_P95.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name", "to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class EdgeDurationP99(DurationUnitMixin, ValuesPluginMixin, PrePlugin):
    id: str = TopoEdgeDataType.DURATION_P99.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name", "to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class EdgeErrorCount(PrePlugin, ValuesPluginMixin):
    """边错误数"""

    id: str = TopoEdgeDataType.ERROR_COUNT.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping(
            group_by=["from_apm_service_name", "to_apm_service_name"],
            where=[
                {"key": "from_span_error", "method": "eq", "value": ["true"]},
                {"condition": "or", "key": "to_span_error", "method": "eq", "value": ["true"]},
            ],
        )


@PluginProvider.pre_plugin
@dataclass
class EdgeErrorRate(PrePlugin, ValuesPluginMixin):
    """边错误率"""

    id: str = TopoEdgeDataType.ERROR_RATE.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowErrorRateCaller, group_by=["from_apm_service_name", "to_apm_service_name"]
    )

    def __post_init__(self):
        self.converter = load_unit("percent")

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_calculate_values_mapping()

    def _to_value(self, value):
        return (
            "".join([str(i) for i in self.converter.auto_convert(decimal=2, value=value * 100)])
            if value is not None
            else None
        )

    @classmethod
    def _ignore_keys(cls):
        return ["from_span_error", "to_span_error"]


@PluginProvider.pre_plugin
@dataclass
class NodeRequestCount(PrePlugin, ValuesPluginMixin):
    """节点总请求量"""

    id: str = BarChartDataType.REQUEST_COUNT.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowCount,
        group_by=["from_apm_service_name", "to_apm_service_name"],
    )
    is_common: bool = True

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_increase_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class NodeRequestCountCaller(PrePlugin, ValuesPluginMixin):
    """节点/接口 主调请求量"""

    id: str = BarChartDataType.REQUEST_COUNT_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowCount,
        group_by=["from_apm_service_name"],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_increase_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class NodeRequestCountCallee(PrePlugin, ValuesPluginMixin):
    """节点被调请求量"""

    id: str = BarChartDataType.REQUEST_COUNT_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(ServiceFlowCount, group_by=["to_apm_service_name"])

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_increase_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class NodeAvgDurationCaller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["from_apm_service_name"])


@PluginProvider.pre_plugin
@dataclass
class NodeAvgDurationCallee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["to_apm_service_name"])


@PluginProvider.pre_plugin  # noqa
@dataclass
class NodeDurationMaxCaller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调响应耗时 MAX"""

    id: str = BarChartDataType.DURATION_MAX_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationMax,
        group_by=["from_apm_service_name"],
    )


@PluginProvider.pre_plugin
@dataclass
class NodeDurationMaxCallee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调响应耗时 MAX"""

    id: str = BarChartDataType.DURATION_MAX_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationMax,
        group_by=["to_apm_service_name"],
    )


@PluginProvider.pre_plugin
@dataclass
class NodeDurationMinCaller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调响应耗时 MIN"""

    id: str = BarChartDataType.DURATION_MIN_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationMin,
        group_by=["from_apm_service_name"],
    )


@PluginProvider.pre_plugin
@dataclass
class NodeDurationMinCallee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调响应耗时 MIN"""

    id: str = BarChartDataType.DURATION_MIN_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationMin,
        group_by=["to_apm_service_name"],
    )

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP50Caller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调响应耗时 P50"""

    id: str = BarChartDataType.DURATION_P50_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.5"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP50Callee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调响应耗时 P50"""

    id: str = BarChartDataType.DURATION_P50_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.5"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP95Caller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调响应耗时 P95"""

    id: str = BarChartDataType.DURATION_P95_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP95Callee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调响应耗时 P95"""

    id: str = BarChartDataType.DURATION_P95_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP99Caller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点主调响应耗时 P99"""

    id: str = BarChartDataType.DURATION_P99_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeDurationP99Callee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """节点被调响应耗时 P99"""

    id: str = BarChartDataType.DURATION_P99_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
    )

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class NodeErrorRateCaller(PrePlugin, ValuesPluginMixin):
    """节点主调错误率"""

    id: str = BarChartDataType.ErrorRateCaller.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        total_mapping = self.get_instance_values_mapping(group_by=["from_apm_service_name"])
        caller_error_mapping = self.get_instance_values_mapping(
            group_by=["from_apm_service_name"], where=[{"key": "from_span_error", "method": "eq", "value": ["true"]}]
        )
        res = {}
        for node, attr in total_mapping.items():
            total_count = attr[self.id]
            caller_count = caller_error_mapping.get(node, {}).get(self.id, 0)

            res[node] = {self.id: round((caller_count / total_count), 6) if total_count else None}

        return res


@PluginProvider.pre_plugin
@dataclass
class NodeErrorRateCallee(PrePlugin, ValuesPluginMixin):
    """节点被调错误率"""

    id: str = BarChartDataType.ErrorRateCallee.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        total_mapping = self.get_instance_values_mapping(group_by=["to_apm_service_name"])
        callee_error_mapping = self.get_instance_values_mapping(
            group_by=["to_apm_service_name"], where=[{"key": "to_span_error", "method": "eq", "value": ["true"]}]
        )
        res = {}
        for node, attr in total_mapping.items():
            total_count = attr[self.id]
            callee_count = callee_error_mapping.get(node, {}).get(self.id, 0)

            res[node] = {self.id: round((callee_count / total_count) if total_count else None, 6)}

        return res


@PluginProvider.pre_plugin
@dataclass
class NodeErrorRateFull(PrePlugin, ValuesPluginMixin):
    """节点总错误率(主调+被调)"""

    id: str = BarChartDataType.ErrorRate.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        total_mapping = self.get_increase_values_mapping(group_by=["from_apm_service_name", "to_apm_service_name"])
        error_mapping = self.get_total_error_count_mapping()

        res = {}
        for node, attr in total_mapping.items():
            total_count = attr[self.id]
            error_count = error_mapping.get(node, {}).get(self.id, 0)

            res[node] = {self.id: round((error_count / total_count) if total_count else None, 6)}

        return res

    def get_total_error_count_mapping(self):
        values_mapping = self.metric(
            **self._runtime,
            **{
                "group_by": ["from_apm_service_name", "to_apm_service_name", "from_span_error", "to_span_error"],
                "where": [
                    {"key": "from_span_error", "method": "eq", "value": ["true"]},
                    {"condition": "or", "key": "to_span_error", "method": "eq", "value": ["true"]},
                ],
            },
        ).get_instance_values_mapping()
        res = defaultdict(lambda: defaultdict(int))
        for k, attrs in values_mapping.items():
            if k[3] == "true":
                res[(k[1],)][self.id] += attrs[self.metric.metric_id]
            if k[2] == "true":
                res[(k[0],)][self.id] += attrs[self.metric.metric_id]
        return res


@PluginProvider.pre_plugin
@dataclass
class NodeErrorCountCaller(PrePlugin, ValuesPluginMixin):
    """节点主调错误数量 (不区分错误码)"""

    id: str = BarChartDataType.ERROR_COUNT_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping(
            group_by=["from_apm_service_name"], where=[{"key": "from_span_error", "method": "eq", "value": ["true"]}]
        )


@PluginProvider.pre_plugin
@dataclass
class NodeErrorCountCallee(PrePlugin, ValuesPluginMixin):
    """节点被调错误数量 (不区分错误码)"""

    id: str = BarChartDataType.ERROR_COUNT_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping(
            group_by=["to_apm_service_name"], where=[{"key": "to_span_error", "method": "eq", "value": ["true"]}]
        )


class ErrorCountStatusCodeMixin(PrePlugin, ValuesPluginMixin):
    status_code_key = "error_status_code_"

    def _install(self, mode):
        if mode == "caller":
            group_key = "from_apm_service_name"
            group_http_key = "from_span_http_status_code"
            group_grpc_key = "from_span_grpc_status_code"
            where_key = "from_span_error"
        else:
            group_key = "to_apm_service_name"
            group_http_key = "to_span_http_status_code"
            group_grpc_key = "to_span_grpc_status_code"
            where_key = "to_span_error"

        res = defaultdict(lambda: defaultdict(int))

        # Step1: 查询总错误数
        values_mapping = self.metric(
            **self._runtime,
            **{"group_by": [group_key], "where": [{"key": where_key, "method": "eq", "value": ["true"]}]},
        ).get_instance_values_mapping()
        for k, attrs in values_mapping.items():
            res[k]["error_count"] += attrs[self.metric.metric_id]

        # Step2: 查询 HTTP 错误数 根据状态码分类
        res = merge_dicts(res, self.get_status_code_mapping(group_http_key, group_key, where_key, "http"))
        # Step3: 查询 GRPC 错误数 根据状态码分类
        res = merge_dicts(res, self.get_status_code_mapping(group_grpc_key, group_key, where_key, "grpc"))

        return res

    def get_status_code_mapping(self, group_specific_key, group_key, where_key, metric_key):
        res = defaultdict(lambda: defaultdict(int))
        values_mapping = self.metric(
            **self._runtime,
            **{
                "group_by": [group_key, group_specific_key],
                "where": [
                    {"key": where_key, "method": "eq", "value": ["true"]},
                    {"key": group_specific_key, "method": "neq", "value": [""]},
                ],
            },
        ).get_instance_values_mapping()
        for k, attrs in values_mapping.items():
            service_name = k[0]
            res[(service_name,)][f"{self.status_code_key}{metric_key}_{k[1]}"] += attrs[self.metric.metric_id]

        return res

    @classmethod
    def diff(cls, attrs, other_attrs):
        # 处理 Http 状态码
        http_status_code_items_1 = {k for k in attrs if k.startswith(f"{cls.status_code_key}http_")}
        http_status_code_items_2 = {k for k in other_attrs if k.startswith(f"{cls.status_code_key}http_")}
        http_status_code_resp = []
        for k in set(http_status_code_items_1) | set(http_status_code_items_2):
            status_code = k.split(f"{cls.status_code_key}http_")[-1]
            http_status_code_resp.append(
                {
                    "id": f"http_{status_code}",
                    "name": _("错误数(HTTP: ") + status_code + ")",
                    "base": attrs.get(k),
                    "diff": other_attrs.get(k),
                }
            )

        # 处理 Grpc 状态码
        grpc_status_code_items_1 = {k for k in attrs if k.startswith(f"{cls.status_code_key}grpc_")}
        grpc_status_code_items_2 = {k for k in other_attrs if k.startswith(f"{cls.status_code_key}grpc_")}
        grpc_status_code_resp = []
        for k in set(grpc_status_code_items_1) | set(grpc_status_code_items_2):
            status_code = k.split(f"{cls.status_code_key}grpc_")[-1]
            grpc_status_code_resp.append(
                {
                    "id": f"grpc_{status_code}",
                    "name": _("错误数(GRPC: ") + status_code + ")",
                    "base": attrs.get(k),
                    "diff": other_attrs.get(k),
                }
            )
        return {
            cls.id: [
                {
                    "id": "error_count",
                    "name": _("总错误数"),
                    "base": attrs.get("error_count"),
                    "diff": other_attrs.get("error_count"),
                }
            ]
            + http_status_code_resp
            + grpc_status_code_resp,
        }


@PluginProvider.pre_plugin
@dataclass
class NodeErrorCountCallerMultiple(ErrorCountStatusCodeMixin):
    """
    节点主调错误量 (分为总错误、HTTP 错误、GRPC 错误)
    [!] 此插件返回的数据格式与其他插件不一致
    """

    id: str = BarChartDataType.ERROR_COUNT_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self._install("caller")


@PluginProvider.pre_plugin
@dataclass
class NodeErrorCountCalleeMultiple(ErrorCountStatusCodeMixin):
    """
    节点被调错误量 (分为总错误、HTTP 错误、GRPC 错误)
    [!] 此插件返回的数据格式与其他插件不一致
    """

    id: str = BarChartDataType.ERROR_COUNT_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self._install("callee")


@PluginProvider.pre_plugin
@dataclass
class NodeInstanceCount(PrePlugin):
    """节点实例数量"""

    id: str = BarChartDataType.INSTANCE_COUNT.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        instances = api.apm_api.query_instance(
            **{
                "bk_biz_id": self._runtime["application"].bk_biz_id,
                "app_name": self._runtime["application"].app_name,
                "fields": ["topo_node_key"],
            }
        ).get("data", [])
        instances_count_mapping = defaultdict(lambda: defaultdict(int))
        for i in instances:
            instances_count_mapping[(i["topo_node_key"],)][self.id] += 1

        return instances_count_mapping


@PluginProvider.pre_plugin
@dataclass
class NodeAlert(PrePlugin):
    """
    节点告警事件
    """

    id: str = BarChartDataType.Alert.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = None

    _ALERT_MAX_SIZE = 1000

    _NORMAL_METRICS = [
        "bk_apm_count",
        "bk_apm_total",
        "bk_apm_duration_max",
        "bk_apm_duration_min",
        "bk_apm_duration_sum",
        "bk_apm_duration_delta",
        "bk_apm_duration_bucket",
    ]
    _FLOW_METRICS = [
        "apm_service_to_apm_service_flow",
        "system_to_apm_service_flow",
        "apm_service_to_system_flow",
        "system_to_system_flow",
    ]
    _FLOW_METRICS_SUFFIX = ["min", "max", "sum", "count", "bucket"]

    def __post_init__(self):
        self.table_id = self._runtime["application"].metric_result_table_id
        flow_metrics = []
        for i in self._FLOW_METRICS:
            for j in self._FLOW_METRICS_SUFFIX:
                flow_metrics.append(f"{i}_{j}")
        self.flow_metrics = flow_metrics

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        """
        查询节点告警
        告警来源:
        1. 内置指标
            ->
            由于不能将 service_name + db_system / service_name + messaging_system 进行 group_by 查询 (ES太过复杂)
            又因为告警不会很多 包含 service_name 维度的告警更少了 所有直接限制 1000 条数据查询出来后进行分析是服务告警还是组建告警
        2. flow 指标
            -> 查询维度中 from_apm_service_name 或 to_apm_service_name 不为空的告警 (直接使用 ES 查询)
        """
        handler = AlertQueryHandler(bk_biz_ids=[self._runtime["application"].bk_biz_id])

        alert_level_mapping = defaultdict(dict)
        for i in [AlertLevel.INFO, AlertLevel.WARN, AlertLevel.ERROR]:
            node_count_mapping = self._query_normal_metric_alerts(handler, i)
            for k, v in node_count_mapping.items():
                alert_level_mapping[k].update({i: v})

        flow_alert_level_mapping = defaultdict(dict)
        for i in [AlertLevel.INFO, AlertLevel.WARN, AlertLevel.ERROR]:
            node_count_mapping = self._query_flow_metric_alerts(handler, i)
            for k, v in node_count_mapping.items():
                flow_alert_level_mapping[k].update({i: v})

        return self._combine_alerts_mapping(alert_level_mapping, flow_alert_level_mapping)

    def _query_normal_metric_alerts(self, handler, severity):
        query = handler.get_search_object(self._runtime["start_time"], self._runtime["end_time"])
        res = defaultdict(int)
        response = query.update_from_dict(
            {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"severity": severity}},
                            {
                                "nested": {
                                    "path": "event.tags",
                                    "query": {
                                        "bool": {
                                            "should": [
                                                {"term": {"event.tags.key": "service_name"}},
                                                {"term": {"event.tags.key": "db_system"}},
                                                {"term": {"event.tags.key": "messaging_system"}},
                                                {"term": {"event.tags.key": "peer_service"}},
                                            ]
                                        }
                                    },
                                }
                            },
                            {"terms": {"event.metric": [f"custom.{self.table_id}.{i}" for i in self._NORMAL_METRICS]}},
                        ]
                    }
                },
                "size": self._ALERT_MAX_SIZE,
                "_source": ["event.tags"],
            }
        ).execute()
        for i in response.hits:
            data = i.to_dict()
            tags = data.get("event", {}).get("tags")
            if not tags:
                continue
            mapping = {j["key"]: j["value"] for j in tags}
            service_name = mapping.get("service_name")
            if not service_name:
                continue

            db_system = mapping.get("db_system")
            messaging_system = mapping.get("messaging_system")
            peer_service = mapping.get("peer_service")
            if db_system or messaging_system:
                node = f"{service_name}-{db_system or messaging_system}"
            else:
                if peer_service:
                    node = ServiceHandler.generate_remote_service_name(peer_service)
                else:
                    node = service_name

            res[node] += 1

        return res

    def _query_flow_metric_alerts(self, handler, severity):
        query = handler.get_search_object(self._runtime["start_time"], self._runtime["end_time"])
        res = {}
        response = query.update_from_dict(
            {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"severity": severity}},
                            {
                                "nested": {
                                    "path": "event.tags",
                                    "query": {
                                        "bool": {
                                            "filter": [
                                                {
                                                    "terms": {
                                                        "event.tags.key": [
                                                            "from_apm_service_name",
                                                            "to_apm_service_name",
                                                        ]
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                }
                            },
                            {"terms": {"event.metric": [f"custom.{self.table_id}.{i}" for i in self.flow_metrics]}},
                        ]
                    }
                },
                "aggs": {
                    "nested_tags": {
                        "nested": {"path": "event.tags"},
                        "aggs": {
                            "values": {
                                "terms": {
                                    "field": "event.tags.value.raw",
                                    "size": self._ALERT_MAX_SIZE,
                                }
                            }
                        },
                    }
                },
            }
        ).execute()

        for i in response.aggregations.nested_tags.values.buckets:
            data = i.to_dict()
            node = data.get("key")
            if not node:
                continue
            res[node] = data.get("doc_count")

        return res

    def _combine_alerts_mapping(self, query_mapping, flow_query_mapping):
        merged_dict = {}

        all_keys = set(query_mapping.keys()).union(flow_query_mapping.keys())

        for key in all_keys:
            sub_dict1 = query_mapping.get(key, {})
            sub_dict2 = flow_query_mapping.get(key, {})

            merged_sub_dict = {}
            all_sub_keys = set(sub_dict1.keys()).union(sub_dict2.keys())

            for sub_key in all_sub_keys:
                merged_sub_dict[AlertLevel.get_label(sub_key)] = sub_dict1.get(sub_key, 0) + sub_dict2.get(sub_key, 0)

            merged_dict[(key,)] = merged_sub_dict

        return merged_dict


@PluginProvider.pre_plugin
@dataclass
class NodeApdex(PrePlugin):
    """节点 Apdex"""

    id: str = BarChartDataType.Apdex.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = ApdexInstance

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        res = defaultdict(lambda: defaultdict(str))

        # Step1: 计算服务节点的 Apdex
        response = self.metric(
            **self._runtime,
            **{
                "group_by": [
                    OtlpKey.get_metric_dimension_key("resource.service.name"),
                ]
            },
        ).get_instance_calculate_values_mapping(
            ignore_keys=[OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
        )
        res.update(response)

        # Step2: 计算组件节点的 Apdex
        component_response = self.metric(
            **self._runtime,
            **{
                "group_by": [
                    OtlpKey.get_metric_dimension_key("resource.service.name"),
                    OtlpKey.get_metric_dimension_key("attributes.db.system"),
                    OtlpKey.get_metric_dimension_key("attributes.messaging.system"),
                ],
                "where": [
                    {"key": "db_system", "method": "neq", "value": [""]},
                    {"condition": "or", "key": "messaging_system", "method": "neq", "value": [""]},
                ],
            },
        ).get_instance_calculate_values_mapping(
            ignore_keys=[OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
        )

        for k, v in component_response.items():
            service = k[0]
            system = k[1] or k[2]
            if system:
                # 这里忽略了 topoNode 更变了拼接逻辑带来的影响(正常来说 topoNode 不会更变拼接逻辑)
                res[(f"{service}-{system}",)] = v

        # Step3: 计算自定义服务节点的 Apdex
        custom_service_response = self.metric(
            **self._runtime, **{"group_by": [OtlpKey.get_metric_dimension_key("attributes.peer.service")]}
        ).get_instance_calculate_values_mapping(
            ignore_keys=[OtlpKey.get_metric_dimension_key(OtlpKey.STATUS_CODE), Apdex.DIMENSION_KEY]
        )
        for k, v in custom_service_response.items():
            if k[0]:
                res[(ServiceHandler.generate_remote_service_name(k[0]),)] = v

        return res


@PluginProvider.pre_plugin
@dataclass
class EndpointRequestCountCaller(PrePlugin, ValuesPluginMixin):
    """接口主调请求量"""

    id: str = BarChartDataType.REQUEST_COUNT_CALLER.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = functools.partial(ServiceFlowCount, group_by=["from_span_name"])

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_increase_values_mapping()

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointRequestCountCaller, self).add_endpoint_query(params, endpoint_name)

        params.setdefault("where", []).extend(
            [
                {"key": "from_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "from_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.pre_plugin
@dataclass
class EndpointRequestCountCallee(PrePlugin, ValuesPluginMixin):
    """接口被调请求量"""

    id: str = BarChartDataType.REQUEST_COUNT_CALLEE.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = functools.partial(ServiceFlowCount, group_by=["to_span_name"])

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_increase_values_mapping()

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointRequestCountCallee, self).add_endpoint_query(params, endpoint_name)
        params.setdefault("where", []).extend(
            [
                {"key": "to_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "to_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.pre_plugin
@dataclass
class EndpointAvgDurationCaller(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """接口主调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLER.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["from_span_name"])

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointAvgDurationCaller, self).add_endpoint_query(params, endpoint_name)
        params.setdefault("where", []).extend(
            [
                {"key": "from_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "from_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.pre_plugin
@dataclass
class EndpointAvgDurationCallee(DurationUnitMixin, SimpleMetricInstanceValuesMixin):
    """接口被调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLEE.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["to_span_name"])

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointAvgDurationCallee, self).add_endpoint_query(params, endpoint_name)
        params.setdefault("where", []).extend(
            [
                {"key": "to_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "to_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.pre_plugin
@dataclass
class EndpointErrorCountCaller(PrePlugin, ValuesPluginMixin):
    """接口主调错误量"""

    id: str = BarChartDataType.ERROR_COUNT_CALLER.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping(
            group_by=["from_span_name"], where=[{"key": "from_span_error", "method": "eq", "value": ["true"]}]
        )

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointErrorCountCaller, self).add_endpoint_query(params, endpoint_name)
        params.setdefault("where", []).extend(
            [
                {"key": "from_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "from_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.pre_plugin
@dataclass
class EndpointErrorCountCallee(PrePlugin, ValuesPluginMixin):
    """接口被调错误量"""

    id: str = BarChartDataType.ERROR_COUNT_CALLEE.value
    type: GraphPluginType = GraphPluginType.ENDPOINT
    metric: Type[MetricHandler] = ServiceFlowCount

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping(
            group_by=["to_span_name"], where=[{"key": "to_span_error", "method": "eq", "value": ["true"]}]
        )

    def add_endpoint_query(self, params, endpoint_name):
        params = super(EndpointErrorCountCallee, self).add_endpoint_query(params, endpoint_name)
        params.setdefault("where", []).extend(
            [
                {"key": "to_apm_service_name", "method": "eq", "value": [self._runtime["service_name"]]},
                {"key": "to_span_name", "method": "eq", "value": self._runtime["endpoint_names"]},
            ]
        )
        return params


@PluginProvider.post_plugin
@dataclass
class BreadthEdge(PostPlugin):
    """
    节点间线条粗细
    通过: 请求量 / 耗时(平均/P99/P95) 计算
    """

    id: str = "edge_breadth"
    type: GraphPluginType = GraphPluginType.EDGE_UI

    _min_width = 1
    _max_width = 5

    def process(self, data_type, edge_data_type, edge_data, graph):
        # 获取原始值进行计算
        metric_values = []
        value = edge_data.get(f"_{edge_data_type}", 0)
        for f, t, attr in graph.edges(data=True):
            # 虚拟服务不显示在拓扑图上 所以不需要将虚拟服务的边指标纳入计算
            if all(i not in TopoVirtualServiceKind.all_kinds() for i in [f.split("-")[-1], t.split("-")[-1]]):
                metric_values.append(attr.get(f"_{edge_data_type}", 0))

        if value in metric_values:
            edge_data[self.id] = self.calculate_breadth(value, metric_values)

    def calculate_breadth(self, value, metric_values):
        """根据指标在指标列表中的位置 映射到宽度范围中计算出线条的宽度"""
        if not value:
            return self._min_width

        sorted_values = sorted(set(metric_values))
        position = sorted_values.index(value)
        total = len(sorted_values)
        if total <= 1:
            return self._min_width

        return round((self._min_width + (self._max_width - self._min_width) * (position / (total - 1))), 2)


@PluginProvider.post_plugin
@dataclass
class NodeColor(PostPlugin):
    """
    节点边缘颜色
    通过: apdex / 告警 alert / 主调错误率 error_rate_caller / 被调错误率 error_rate_callee / 错误率 error_rate
    此插件依赖 NodeHaveData 插件
    """

    id: str = "color"
    type: GraphPluginType = GraphPluginType.NODE_UI

    class Color:
        GREEN = "#2DCB56"
        BLUE = "#3A84FF"
        YELLOW = "#FF9C01"
        RED = "#EA3636"
        WHITE = "#DCDEE5"

    def process(self, data_type, edge_data_type, node_data, graph):
        # 如果数据类型不是告警并且节点无数据 那么颜色就是灰色
        if data_type != BarChartDataType.Alert.value and not node_data.get(NodeHaveData.id):
            node_data[self.id] = self.Color.WHITE
            return

        if data_type in [
            BarChartDataType.ErrorRate.value,
            BarChartDataType.ErrorRateCaller.value,
            BarChartDataType.ErrorRateCallee.value,
        ]:
            value = node_data.get(data_type)

            if value is None:
                # 为 None 有两种情况 一种为无数据 一种为无异常
                request_count = node_data.get(NodeRequestCount.id)
                if request_count:
                    node_data[self.id] = self.Color.GREEN
                else:
                    node_data[self.id] = self.Color.WHITE
            elif value == 0:
                node_data[self.id] = self.Color.GREEN
            elif value < 0.1:
                node_data[self.id] = self.Color.YELLOW
            else:
                node_data[self.id] = self.Color.RED

        elif data_type == BarChartDataType.Alert.value:
            info_count = node_data.get(AlertLevel.get_label(AlertLevel.INFO), None)
            warn_count = node_data.get(AlertLevel.get_label(AlertLevel.WARN), None)
            error_count = node_data.get(AlertLevel.get_label(AlertLevel.ERROR), None)

            if error_count:
                color = self.Color.RED
            elif warn_count:
                color = self.Color.YELLOW
            elif info_count:
                color = self.Color.BLUE
            else:
                color = self.Color.GREEN

            node_data[self.id] = color
        elif data_type == BarChartDataType.Apdex.value:
            apdex = node_data.get(NodeApdex.metric.metric_id, None)
            if not apdex:
                color = self.Color.WHITE
            elif apdex == Apdex.SATISFIED:
                color = self.Color.GREEN
            elif apdex == Apdex.TOLERATING:
                color = self.Color.YELLOW
            else:
                color = self.Color.RED
            node_data[self.id] = color


@PluginProvider.post_plugin
@dataclass
class NodeHaveData(PostPlugin):
    """
    判断节点是否有数据
    """

    id: str = "have_data"
    type: GraphPluginType = GraphPluginType.NODE_UI

    def process(self, data_type, edge_data_type, node_data, graph):
        request_count = node_data.get(NodeRequestCount.id)
        node_data[self.id] = True if request_count else False


@PluginProvider.post_plugin
@dataclass
class NodeSize(PostPlugin):
    """
    节点大小
    只跟请求量有关
    """

    id: str = "size"
    type: GraphPluginType = GraphPluginType.NODE_UI

    class Size:
        NO_DATA = 20
        SMALL = 20
        MEDIUM = 30
        LARGE = 36

    def process(self, data_type, edge_data_type, node_data, graph):
        f_value = node_data.get(BarChartDataType.REQUEST_COUNT.value)
        if f_value is None:
            node_data[self.id] = self.Size.NO_DATA
            return

        if f_value < 200:
            node_data[self.id] = self.Size.SMALL
        elif f_value < 1000:
            node_data[self.id] = self.Size.MEDIUM
        else:
            node_data[self.id] = self.Size.LARGE


@PluginProvider.post_plugin
@dataclass
class EndpointSize(PostPlugin):
    """
    接口大小
    只跟请求量有关
    """

    id: str = "size"
    type: GraphPluginType = GraphPluginType.ENDPOINT_UI

    class Size:
        NO_DATA = 20
        SMALL = 20
        MEDIUM = 30
        LARGE = 36

    def process(self, endpoint_data):
        caller_value = endpoint_data.get(EndpointRequestCountCaller.id, 0)
        callee_value = endpoint_data.get(EndpointRequestCountCallee.id, 0)
        value = caller_value or 0 + callee_value or 0

        if not value:
            endpoint_data[self.id] = self.Size.NO_DATA
        elif value < 200:
            endpoint_data[self.id] = self.Size.SMALL
        elif value < 1000:
            endpoint_data[self.id] = self.Size.MEDIUM
        else:
            endpoint_data[self.id] = self.Size.LARGE


@PluginProvider.post_plugin
@dataclass
class NodeMenu(PostPlugin):
    """节点菜单"""

    id: str = "menu"
    type: GraphPluginType = GraphPluginType.NODE_UI

    def __post_init__(self):
        self.views = SceneViewModel.objects.filter(
            bk_biz_id=self._runtime["application"].bk_biz_id, scene_id="apm_service"
        )

    def process(self, data_type, edge_data_type, node_data, graph):
        kind = node_data.get("data", {}).get("kind")
        node_name = node_data["data"]["name"]
        if kind == TopoNodeKind.REMOTE_SERVICE:
            node_data[self.id] = [
                {
                    "name": _("接口下钻"),
                    "action": "span_drilling",
                },
            ]
            if not self._runtime.get("service_name"):
                relation_link = LinkHelper.get_relation_app_link(
                    self._runtime["application"].bk_biz_id,
                    self._runtime["application"].app_name,
                    node_name,
                    self._runtime["start_time"],
                    self._runtime["end_time"],
                )
                if relation_link:
                    # 如果没有服务名称的过滤 增加跳转链接
                    node_data[self.id].append(
                        {
                            "name": _("查看三方应用"),
                            "type": "link",
                            "action": "blank",
                            "url": relation_link,
                        }
                    )
        else:
            node_data[self.id] = [
                {
                    "name": _("接口下钻"),
                    "action": "span_drilling",
                },
                {"name": _("服务概览"), "action": "service_detail"},
                {
                    "name": _("资源拓扑"),
                    "action": "resource_drilling",
                },
            ]

            log_link = LinkHelper.get_service_log_tab_link(
                self._runtime["application"].bk_biz_id,
                self._runtime["application"].app_name,
                node_name,
                self._runtime["start_time"],
                self._runtime["end_time"],
                views=self.views,
            )
            if not self._runtime.get("service_name"):
                # 如果没有服务名称的过滤 增加菜单
                node_data[self.id].append(
                    {
                        "name": _("查看服务"),
                        "action": "self",
                        "type": "link",
                        "url": LinkHelper.get_service_overview_tab_link(
                            self._runtime["application"].bk_biz_id,
                            self._runtime["application"].app_name,
                            node_name,
                            self._runtime["start_time"],
                            self._runtime["end_time"],
                            views=self.views,
                        ),
                    },
                )
                if log_link:
                    node_data[self.id].append(
                        {
                            "name": _("查看日志"),
                            "action": "self",
                            "type": "link",
                            "url": LinkHelper.get_service_log_tab_link(
                                self._runtime["application"].bk_biz_id,
                                self._runtime["application"].app_name,
                                node_name,
                                self._runtime["start_time"],
                                self._runtime["end_time"],
                                views=self.views,
                            ),
                        },
                    )


class HoverTipsMixin:
    @classmethod
    def add_tips(cls, key, data):
        # 将节点数据归类在 tips 目录下
        duration_converter = functools.partial(load_unit("µs").auto_convert, decimal=2)

        duration_caller = data.pop(f"_{BarChartDataType.AVG_DURATION_CALLER.value}", None)
        duration_callee = data.pop(f"_{BarChartDataType.AVG_DURATION_CALLEE.value}", None)

        error_count_caller = data.pop(BarChartDataType.ERROR_COUNT_CALLER.value, None)
        error_count_callee = data.pop(BarChartDataType.ERROR_COUNT_CALLEE.value, None)

        def _join(items):
            res = ""
            for i in items:
                res += str(i)
            return res

        data[key] = [
            {
                "group": "request_count",
                "name": _("主调总量"),
                "value": data.pop(BarChartDataType.REQUEST_COUNT_CALLER.value, "--"),
            },
            {
                "group": "duration",
                "name": _("主调平均耗时"),
                "value": _join(duration_converter(value=duration_caller)) if duration_caller is not None else "--",
            },
            {
                "group": "error",
                "name": _("主调错误量"),
                "value": error_count_caller if error_count_caller is not None else "--",
            },
            {
                "group": "request_count",
                "name": _("被调总量"),
                "value": data.pop(BarChartDataType.REQUEST_COUNT_CALLEE.value, "--"),
            },
            {
                "group": "duration",
                "name": _("被调平均耗时"),
                "value": _join(duration_converter(value=duration_callee)) if duration_callee is not None else "--",
            },
            {
                "group": "error",
                "name": _("被调错误量"),
                "value": error_count_callee if error_count_callee is not None else "--",
            },
        ]


@PluginProvider.post_plugin
@dataclass
class NodeTips(PostPlugin, HoverTipsMixin):
    """节点 Hover 信息"""

    id: str = "node_tips"
    type: GraphPluginType = GraphPluginType.NODE_UI

    def process(self, data_type, edge_data_type, node_data, graph):
        """
        获取指标数据
        主调调用量 、 主调平均耗时 、 主调错误量
        被调调用量 、 被调平均耗时 、 被调错误量
        实例数量
        """
        self.add_tips(self.id, node_data)

        if data_type == BarChartDataType.Alert.value:
            count = sum(
                [
                    node_data.pop(AlertLevel.get_label(AlertLevel.INFO), 0),
                    node_data.pop(AlertLevel.get_label(AlertLevel.WARN), 0),
                    node_data.pop(AlertLevel.get_label(AlertLevel.ERROR), 0),
                ]
            )
            if count:
                node_data[self.id].append(
                    {
                        "name": _("告警数量"),
                        "value": count,
                    }
                )


@PluginProvider.post_plugin
@dataclass
class EndpointTips(PostPlugin, HoverTipsMixin):
    """接口 Hover 信息"""

    id: str = "endpoint_tips"
    type: GraphPluginType = GraphPluginType.ENDPOINT_UI

    def process(self, endpoint_data):
        """
        获取指标数据
        主调调用量 、 主调平均耗时 、 主调错误率
        被调调用量 、 被调平均耗时 、 被调错误率
        """
        self.add_tips(self.id, endpoint_data)


class ViewConverter:
    _extra_pre_plugins = PluginProvider.Container(_plugins=[])
    _extra_pre_convert_plugins = PluginProvider.Container(_plugins=[])

    def __init__(self, bk_biz_id, app_name, runtime, filter_params=None):
        self.filter_params = filter_params or {}
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.runtime = runtime

    def convert(self, graph):
        raise NotImplementedError

    def extra_pre_plugins(self, runtime):
        return PluginProvider.Container(_plugins=[i(_runtime=runtime) for i in self._extra_pre_plugins])

    @classmethod
    def extra_pre_convert_plugins(cls, runtime):
        return PluginProvider.Container(_plugins=[i(_runtime=runtime) for i in cls._extra_pre_convert_plugins])

    @classmethod
    def new(cls, bk_biz_id, app_name, data_type: str, runtime, filter_params=None):
        if data_type == GraphViewType.TOPO.value:
            return TopoViewConverter(bk_biz_id, app_name, runtime, filter_params=filter_params)
        elif data_type == GraphViewType.TABLE.value:
            return TableViewConverter(bk_biz_id, app_name, runtime, filter_params=filter_params)
        elif data_type == GraphViewType.TOPO_DIFF.value:
            return TopoDiffDataConverter(bk_biz_id, app_name, runtime, filter_params=filter_params)
        raise ValueError(f"Unsupported dataType: {data_type}")


class TopoViewConverter(ViewConverter):
    _extra_pre_plugins = PluginProvider.Container(
        _plugins=[
            NodeRequestCountCaller,
            NodeRequestCountCallee,
            NodeAvgDurationCaller,
            NodeAvgDurationCallee,
            NodeErrorCountCaller,
            NodeErrorCountCallee,
            NodeApdex,
        ]
    )
    _extra_pre_convert_plugins = PluginProvider.Container(
        _plugins=[
            BreadthEdge,
            NodeHaveData,
            NodeColor,
            NodeSize,
            NodeMenu,
            # NodeTips 会改变数据结构 放在最后
            NodeTips,
        ]
    )

    def convert(self, graph):
        nodes, edges = FilterChain.new(self.filter_params).filter(graph)

        return {
            "nodes": [attrs for _, attrs in nodes],
            "edges": [{**attrs, "from_name": f, "to_name": t} for f, t, attrs in edges],
        }


class TopoDiffDataConverter(ViewConverter):
    """拓扑图对比模式转换器"""

    _caller_plugins = [
        NodeErrorCountCallerMultiple,
        NodeDurationMaxCaller,
        NodeDurationMinCaller,
        NodeDurationP50Caller,
        NodeDurationP99Caller,
        NodeDurationP95Caller,
        NodeAvgDurationCaller,
    ]

    _callee_plugins = [
        NodeErrorCountCalleeMultiple,
        NodeDurationMaxCallee,
        NodeDurationMinCallee,
        NodeDurationP50Callee,
        NodeDurationP99Callee,
        NodeDurationP95Callee,
        NodeAvgDurationCallee,
    ]

    @property
    def _extra_pre_plugins(self):
        if self.runtime.get("option_kind") == "caller":
            return self._caller_plugins
        if self.runtime.get("option_kind") == "callee":
            return self._callee_plugins
        return self._caller_plugins + self._callee_plugins

    def convert(self, graph):
        nodes, edges = FilterChain.new(self.filter_params).filter(graph)

        return {
            "nodes": [attrs for _, attrs in nodes],
            "edges": [{**attrs, "from_name": f, "to_name": t} for f, t, attrs in edges],
        }


class TableViewConverter(ViewConverter):
    _extra_pre_plugins = PluginProvider.Container(
        _plugins=[
            EdgeAvgDuration,
            EdgeRequestCount,
            EdgeErrorRate,
            EdgeErrorCount,
        ]
    )

    @classmethod
    def columns(cls):
        return [
            {
                "id": "service",
                "name": "服务名称",
                "type": "link",
                "disabled": True,
            },
            {
                "id": "type",
                "name": "调用类型",
                "type": "string",
                "filterable": True,
                "filter_list": [
                    {"text": "主调", "value": "caller"},
                    {"text": "被调", "value": "callee"},
                ],
                "disabled": True,
            },
            {
                "id": "other_service",
                "name": "调用服务",
                "type": "string",
                "disabled": True,
            },
            {
                "id": "request_count",
                "name": "请求数",
                "sortable": "custom",
                "type": "number",
            },
            {
                "id": "error_count",
                "name": "错误数",
                "sortable": "custom",
                "type": "number",
            },
            {
                "id": "error_rate",
                "name": "错误率",
                "sortable": "custom",
                "type": "number",
            },
            {
                "id": "avg_duration",
                "name": "平均响应耗时",
                "sortable": "custom",
                "type": "number",
            },
            {"id": "operators", "name": "操作", "type": "more_operate", "width": 80, "disabled": True},
        ]

    def __init__(self, *args, **kwargs):
        super(TableViewConverter, self).__init__(*args, **kwargs)
        self.time_convert = load_unit("µs")
        self.percent_convert = load_unit("percent")
        self.views = SceneViewModel.objects.filter(bk_biz_id=self.bk_biz_id, scene_id="apm_service")

    def create_row(self, s, s_category, o_s, o_s_category, _type, attrs):
        # 组件类服务没有日志 tab 不显示此菜单
        operators = [
            {
                "value": _("查看告警"),
                "target": "blank",
                "url": LinkHelper.get_service_alert_link(
                    self.bk_biz_id,
                    self.app_name,
                    s,
                    self.runtime["start_time"],
                    self.runtime["end_time"],
                ),
            },
            {
                "value": _("查看指标"),
                "target": "blank",
                "url": LinkHelper.get_service_overview_tab_link(
                    self.bk_biz_id,
                    self.app_name,
                    s,
                    self.runtime["start_time"],
                    self.runtime["end_time"],
                    views=self.views,
                ),
            },
        ]
        log_link = LinkHelper.get_service_log_tab_link(
            self.bk_biz_id,
            self.app_name,
            s,
            self.runtime["start_time"],
            self.runtime["end_time"],
            views=self.views,
        )
        if log_link:
            operators.append(
                {
                    "value": _("查看日志"),
                    "target": "blank",
                    "url": log_link,
                }
            )

        return {
            "service": {
                "name": s,
                "category": s_category,
                "target": "self",
                "url": LinkHelper.get_service_overview_tab_link(
                    self.bk_biz_id,
                    self.app_name,
                    s,
                    self.runtime["start_time"],
                    self.runtime["end_time"],
                    views=self.views,
                ),
            },
            "other_service": {
                "name": o_s,
                "category": o_s_category,
            },
            "type": _type,
            "avg_duration": attrs.get(TopoEdgeDataType.DURATION_AVG.value),
            "avg_duration_original": round(attrs[f"_{TopoEdgeDataType.DURATION_AVG.value}"], 2)
            if f"_{TopoEdgeDataType.DURATION_AVG.value}" in attrs
            else None,
            "request_count": attrs.get(TopoEdgeDataType.REQUEST_COUNT.value),
            "error_count": attrs.get(EdgeErrorCount.id),
            "error_rate": attrs.get(EdgeErrorRate.id),
            "operators": operators,
        }

    def convert(self, graph):
        nodes, edges = FilterChain.new(self.filter_params).filter(graph)
        node_mappings = {k: v for k, v in nodes}

        data = []

        for k, v, attrs in edges:
            from_node = node_mappings.get(k)
            to_node = node_mappings.get(v)

            if not from_node or not to_node:
                continue

            data.append(
                self.create_row(
                    k,
                    from_node.get("data", {}).get("category"),
                    v,
                    to_node.get("data", {}).get("category"),
                    "caller",
                    attrs,
                )
            )
            data.append(
                self.create_row(
                    v,
                    to_node.get("data", {}).get("category"),
                    k,
                    from_node.get("data", {}).get("category"),
                    "callee",
                    attrs,
                )
            )

        return {"columns": self.columns(), "data": data, "total": len(data)}


class Filter:
    def __init__(self, filter_params=None):
        self.filter_params = filter_params

    def process(self, data):
        raise NotImplementedError


class FilterChain:
    def __init__(self, filter_params=None):
        self.filters = []
        self.filter_params = filter_params or {}

    def add(self, f):
        self.filters.append(f)

    def filter(self, data):
        for f in self.filters:
            data = f.process(data)
        return data

    @classmethod
    def new(cls, filter_params):
        c = cls()
        c.add(GraphToListFilter(filter_params))
        c.add(VirtualServiceFilter(filter_params))
        c.add(ServiceNameFilter(filter_params))
        return c


class GraphToListFilter(Filter):
    def process(self, graph):
        nodes = []
        edges = []
        for node_id, attrs in graph.nodes(data=True):
            nodes.append((node_id, attrs))

        for f, t, attrs in graph.edges(data=True):
            edges.append((f, t, {k: v for k, v in attrs.items()}))

        return nodes, edges


class VirtualServiceFilter(Filter):
    def process(self, data):
        nodes, edges = data
        new_nodes = []
        new_edges = []

        filter_node_ids = []
        for node_id, attrs in nodes:
            if attrs.get("data", {}).get("kind") == TopoNodeKind.VIRTUAL_SERVICE:
                filter_node_ids.append(node_id)
            else:
                new_nodes.append((node_id, attrs))

        for f, t, attrs in edges:
            if f in filter_node_ids or t in filter_node_ids:
                continue
            new_edges.append((f, t, attrs))

        return new_nodes, new_edges


class ServiceNameFilter(Filter):
    def process(self, data):
        nodes, edges = data
        filter_service_name = self.filter_params.get("service_name")
        if not filter_service_name:
            return nodes, edges

        valid_nodes = set()
        new_nodes, new_edges = [], []

        for k, v, attrs in edges:
            if k == filter_service_name or v == filter_service_name:
                new_edges.append((k, v, attrs))
                valid_nodes.add(k)
                valid_nodes.add(v)

        for node_id, attrs in nodes:
            if node_id in valid_nodes:
                new_nodes.append((node_id, attrs))

        return new_nodes, new_edges
