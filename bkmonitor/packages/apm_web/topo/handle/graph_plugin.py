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
    ServiceFlowErrorRate,
)
from apm_web.topo.constants import (
    BarChartDataType,
    GraphPluginType,
    GraphViewType,
    TopoEdgeDataType,
)
from constants.apm import OtlpKey
from core.drf_resource import api
from core.unit import load_unit
from fta_web.alert.handlers.alert import AlertQueryHandler


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
    """前置插件"""

    metric: Type[MetricHandler] = None
    _runtime: dict = field(default_factory=dict)
    is_common: bool = False

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        raise NotImplementedError


@dataclass
class PostPlugin(Plugin):
    """后置插件"""

    _runtime: dict = field(default_factory=dict)

    def process(self, data_type, edge_data_type, node_or_edge_data, graph):
        raise NotImplementedError


class ValuesPluginMixin:
    def get_increase_values_mapping(self, **kwargs) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        m = self.metric(
            **self._runtime,
            **kwargs,
        )
        response = m.get_instance_values_mapping(ignore_keys=self._ignore_keys())
        res = defaultdict(lambda: defaultdict(int))
        for k, v in response.items():
            for i in k:
                res[(i,)][self.id] += v[m.metric_id]
        return dict(res)

    def get_instance_values_mapping(self, **kwargs) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        if not self.metric:
            raise ValueError(f"Plugin: {self.__name__} metric is empty")

        metric = self.metric(**self._runtime, **kwargs)
        mappings = metric.get_instance_values_mapping(ignore_keys=self._ignore_keys())
        res = {}
        for k, v in mappings.items():
            # 还需要保存原始值 以便后面插件进行处理
            res[k] = {self.id: self._to_value(v[metric.metric_id]), f"_{self.id}": v[metric.metric_id]}

        return res

    def get_instance_calculate_values_mapping(self, **kwargs):
        if not self.metric:
            raise ValueError(f"Plugin: {self.__name__} metric is empty")

        metric = self.metric(**self._runtime, **kwargs)
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
class EdgeAvgDuration(PrePlugin, ValuesPluginMixin):
    id: str = TopoEdgeDataType.DURATION_AVG.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowAvgDuration,
        group_by=["from_apm_service_name", "to_apm_service_name"],
    )

    def __post_init__(self):
        self.converter = load_unit("µs")

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    def _to_value(self, value):
        return "".join([str(i) for i in self.converter.auto_convert(decimal=2, value=value)]) if value else None


@PluginProvider.pre_plugin
@dataclass
class EdgeDurationP95(PrePlugin, ValuesPluginMixin):
    id: str = TopoEdgeDataType.DURATION_P95.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name", "to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.95"}]}],
    )

    def __post_init__(self):
        self.converter = load_unit("µs")

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    def _to_value(self, value):
        return "".join([str(i) for i in self.converter.auto_convert(decimal=2, value=value)]) if value else None

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class EdgeDurationP99(PrePlugin, ValuesPluginMixin):
    id: str = TopoEdgeDataType.DURATION_P99.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowDurationBucket,
        group_by=["from_apm_service_name", "to_apm_service_name"],
        functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.99"}]}],
    )

    def __post_init__(self):
        self.converter = load_unit("µs")

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()

    def _to_value(self, value):
        return "".join([str(i) for i in self.converter.auto_convert(decimal=2, value=value)]) if value else None

    @classmethod
    def _ignore_keys(cls):
        return ["le"]


@PluginProvider.pre_plugin
@dataclass
class EdgeErrorRate(PrePlugin, ValuesPluginMixin):
    """边错误率"""

    id: str = TopoEdgeDataType.ERROR_RATE.value
    type: GraphPluginType = GraphPluginType.EDGE
    metric: Type[MetricHandler] = functools.partial(
        ServiceFlowErrorRate, group_by=["from_apm_service_name", "to_apm_service_name"]
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
    """节点主调请求量"""

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
class NodeAvgDurationCaller(PrePlugin, ValuesPluginMixin):
    """节点主调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLER.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["from_apm_service_name"])

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


@PluginProvider.pre_plugin
@dataclass
class NodeAvgDurationCallee(PrePlugin, ValuesPluginMixin):
    """节点被调平均耗时"""

    id: str = BarChartDataType.AVG_DURATION_CALLEE.value
    type: GraphPluginType = GraphPluginType.NODE
    metric: Type[MetricHandler] = functools.partial(ServiceFlowAvgDuration, group_by=["to_apm_service_name"])

    def install(self) -> Dict[Tuple[Union[str, Tuple]], Dict]:
        return self.get_instance_values_mapping()


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

            res[node] = {self.id: round((caller_count / total_count), 2) if total_count else None}

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

            res[node] = {self.id: round((callee_count / total_count) if total_count else None, 2)}

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

            res[node] = {self.id: round((error_count / total_count) if total_count else None, 2)}

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
                res[k[1]][self.id] += attrs[self.metric.metric_id]
            if k[2] == "true":
                res[k[0]][self.id] += attrs[self.metric.metric_id]
        return res


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
                                    "query": {"bool": {"filter": [{"terms": {"event.tags.key": ["service_name"]}}]}},
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
            if db_system or messaging_system:
                node = f"{service_name}-{db_system or messaging_system}"
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

            merged_dict[key] = merged_sub_dict

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
        for k, v in response.items():
            res[k[0]] = v

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
                res[f"{service}-{system}"] = v

        return res


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

        return round((self._min_width + (self._max_width - self._min_width) * (position / (total - 1))), 2)


@PluginProvider.post_plugin
@dataclass
class NodeColor(PostPlugin):
    """
    节点边缘颜色
    通过: apdex / 告警 alert / 主调错误率 error_rate_caller / 被调错误率 error_rate_callee / 错误率 error_rate

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

        if data_type in [
            BarChartDataType.ErrorRate.value,
            BarChartDataType.ErrorRateCaller.value,
            BarChartDataType.ErrorRateCallee.value,
        ]:
            value = node_data.get(data_type)

            if value is None:
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
class NodeMenu(PostPlugin):
    """节点菜单"""

    id: str = "menu"
    type: GraphPluginType = GraphPluginType.NODE_UI

    def process(self, data_type, edge_data_type, node_data, graph):
        kind = node_data.get("data", {}).get("kind")
        if kind == TopoNodeKind.REMOTE_SERVICE:
            node_data[self.id] = [
                {
                    "name": _("接口下钻"),
                    "action": "span_drilling",
                },
                {
                    "name": _("查看三方应用"),
                    "action": "blank",
                    "url": ServiceHandler.build_url(self._runtime["application"].app_name, node_data["data"]["name"]),
                },
            ]
        else:
            node_data[self.id] = [
                {
                    "name": _("接口下钻"),
                    "action": "span_drilling",
                },
                {
                    "name": _("资源拓扑"),
                    "action": "resource_drilling",
                },
            ]


@PluginProvider.post_plugin
@dataclass
class NodeTips(PostPlugin):
    """节点 Hover 信息"""

    id: str = "node_tips"
    type: GraphPluginType = GraphPluginType.NODE_UI

    def process(self, data_type, edge_data_type, node_data, graph):
        """
        获取指标数据
        主调调用量 、 主调平均耗时 、 主调错误率
        被调调用量 、 被调平均耗时 、 被调错误率
        实例数量
        """
        # 将节点数据归类在 tips 目录下
        duration_converter = functools.partial(load_unit("µs").auto_convert, decimal=2)
        percent_converter = functools.partial(load_unit("percent").auto_convert, decimal=2)

        duration_caller = node_data.pop(BarChartDataType.AVG_DURATION_CALLER.value, None)
        duration_callee = node_data.pop(BarChartDataType.AVG_DURATION_CALLEE.value, None)

        error_rate_caller = node_data.pop(BarChartDataType.ErrorRateCaller.value, None)
        error_rate_callee = node_data.pop(BarChartDataType.ErrorRateCallee.value, None)

        def _join(items):
            res = ""
            for i in items:
                res += str(i)
            return res

        node_data[self.id] = [
            {
                "name": _("主调调用量"),
                "value": node_data.pop(BarChartDataType.REQUEST_COUNT_CALLER.value, "--"),
            },
            {
                "name": _("主调平均耗时"),
                "value": _join(duration_converter(value=duration_caller)) if duration_caller else "--",
            },
            {
                "name": _("主调错误率"),
                "value": _join(percent_converter(value=error_rate_caller * 100)) if error_rate_caller else "--",
            },
            {
                "name": _("被调调用量"),
                "value": node_data.pop(BarChartDataType.REQUEST_COUNT_CALLEE.value, "--"),
            },
            {
                "name": _("被调平均耗时"),
                "value": _join(duration_converter(value=duration_callee)) if duration_callee else "--",
            },
            {
                "name": _("被调错误率"),
                "value": _join(percent_converter(value=error_rate_callee * 100)) if error_rate_callee else "--",
            },
            {
                "name": _("实例数量"),
                "value": node_data.pop(BarChartDataType.INSTANCE_COUNT.value, "--"),
            },
        ]

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


class ViewConverter:
    _extra_pre_plugins = PluginProvider.Container(_plugins=[])
    _extra_pre_convert_plugins = PluginProvider.Container(_plugins=[])

    def __init__(self, bk_biz_id, app_name, filter_params=None):
        self.filter_params = filter_params or {}
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    def convert(self, graph):
        raise NotImplementedError

    def extra_pre_plugins(self, runtime):
        return PluginProvider.Container(_plugins=[i(_runtime=runtime) for i in self._extra_pre_plugins])

    def extra_pre_convert_plugins(self, runtime):
        return PluginProvider.Container(_plugins=[i(_runtime=runtime) for i in self._extra_pre_convert_plugins])

    @classmethod
    def new(cls, bk_biz_id, app_name, data_type: str, filter_params=None):
        if data_type == GraphViewType.TOPO.value:
            return TopoViewConverter(bk_biz_id, app_name, filter_params=filter_params)
        elif data_type == GraphViewType.TABLE.value:
            return TableViewConverter(bk_biz_id, app_name, filter_params=filter_params)
        raise ValueError(f"Unsupported dataType: {data_type}")


class TopoViewConverter(ViewConverter):
    _extra_pre_plugins = PluginProvider.Container(
        _plugins=[
            NodeInstanceCount,
            NodeRequestCountCaller,
            NodeRequestCountCallee,
            NodeAvgDurationCaller,
            NodeAvgDurationCallee,
            NodeErrorRateCaller,
            NodeErrorRateCallee,
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


class TableViewConverter(ViewConverter):
    _extra_pre_plugins = PluginProvider.Container(
        _plugins=[
            EdgeAvgDuration,
            EdgeRequestCount,
            EdgeErrorRate,
        ]
    )

    @classmethod
    def columns(cls):
        return [
            {
                "id": "service_name",
                "name": "服务名称",
                "sortable": "custom",
                "type": "link",
            },
            {
                "id": "type",
                "name": "调用类型",
                "type": "relation",
                "filterable": True,
                "filter_list": [
                    {"text": "主调", "value": "caller"},
                    {"text": "被调", "value": "callee"},
                ],
            },
            {
                "id": "other_service_name",
                "name": "调用服务",
                "sortable": "custom",
                "type": "string",
            },
            {
                "id": "request_count",
                "name": "调用数",
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
        ]

    def __init__(self, *args, **kwargs):
        super(TableViewConverter, self).__init__(*args, **kwargs)
        self.time_convert = load_unit("µs")
        self.percent_convert = load_unit("percent")

    def create_row(self, s, s_category, o_s, o_s_category, _type, attrs):
        return {
            "service": {
                "name": s,
                "category": s_category,
                "target": "self",
                "url": ServiceHandler.build_url(self.app_name, s),
            },
            "other_service": {
                "name": o_s,
                "category": o_s_category,
            },
            "type": _type,
            "avg_duration": attrs.get(TopoEdgeDataType.DURATION_AVG.value),
            "request_count": attrs.get(TopoEdgeDataType.REQUEST_COUNT.value),
            "error_rate": attrs.get(TopoEdgeDataType.ERROR_RATE.value),
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
            # 不显示隐藏属性
            edges.append((f, t, {k: v for k, v in attrs.items() if not k.startswith("_")}))

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

        new_nodes, new_edges = [], []
        for node_id, attrs in nodes:
            if node_id == filter_service_name:
                new_nodes.append((node_id, attrs))

        for k, v, attrs in edges:
            if k == filter_service_name or v == filter_service_name:
                new_edges.append((k, v, attrs))

        return new_nodes, new_edges
