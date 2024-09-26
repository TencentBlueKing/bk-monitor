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
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from typing import Dict, List, Union

import networkx

from apm_web.constants import CustomServiceMatchType, TopoNodeKind
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric_handler import ServiceFlowCount
from apm_web.models import ApplicationCustomService
from apm_web.topo.constants import GraphPluginType
from apm_web.topo.handle import BaseQuery
from apm_web.topo.handle import NodeDisplayType as Display
from apm_web.topo.handle.graph_plugin import PluginProvider, ViewConverter
from apm_web.utils import merge_dicts
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import get_datetime_range

logger = logging.getLogger("apm")


@dataclass
class Node:
    display_key: str
    name: str
    category: str
    type: Display = Display.UNDEFINED
    kind: str = TopoNodeKind.SERVICE
    id: str = field(init=False)
    extra_info: dict = field(default_factory=dict)

    REQUIRE_FIELDS = ["display_key", "name", "category", "type", "kind", "id"]

    def __post_init__(self):
        self.id = self.name

    @property
    def is_valid(self) -> bool:
        for f in self.REQUIRE_FIELDS:
            if getattr(self, f) in [None, '', [], {}]:
                return False
        return True

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        # 不考虑重名问题 根据 topo_key 作为唯一键
        return self.name == other.name

    def __hash__(self):
        return hash((self.name,))


@dataclass
class NodeContainer:
    _nodes: List[Node] = field(default_factory=list)

    def __or__(self, other: "NodeContainer"):
        combined_nodes = {}
        all_ids = {node.id for node in self._nodes} | {node.id for node in other._nodes}

        def update_type(node, display_type):
            node.type = Display.to_display(
                [Display.DASHED if node.kind == TopoNodeKind.REMOTE_SERVICE else Display.SOLID, display_type]
            )

        for node_id in all_ids:
            s_node = next((node for node in self._nodes if node.id == node_id), None)
            o_node = next((node for node in other._nodes if node.id == node_id), None)
            if (s_node and o_node) or o_node:
                update_type(o_node, Display.NORMAL)
                if s_node:
                    o_node.extra_info = merge_dicts(o_node.extra_info, s_node.extra_info)
                chosen = o_node
            else:
                update_type(s_node, Display.VOID)
                chosen = s_node

            combined_nodes[node_id] = chosen
        return NodeContainer(_nodes=list(combined_nodes.values()))

    def append(self, p_object):
        if p_object.is_valid:
            self._nodes.append(p_object)
        return

    def __iter__(self):
        yield from self._nodes

    def to_nodes_attrs_mapping(self):
        # Node 与 Edge 保持统一 key 都使用 tuple 类型
        return {(i.id,): {"data": asdict(i)} for i in self._nodes}


@dataclass
class Edge:
    from_name: str
    to_name: str

    @property
    def is_valid(self) -> bool:
        for f in fields(self):
            if getattr(self, f.name) in [None, '', [], {}]:
                return False
        return True

    def __eq__(self, other):
        if not isinstance(other, Edge):
            return False
        return self.from_name == other.from_name and self.to_name == self.to_name

    def __hash__(self):
        return hash((self.from_name, self.to_name))


@dataclass
class EdgeContainer:
    _edges: List[Edge] = field(default_factory=list)

    def __or__(self, other):
        b = {hash(node): node for node in self._edges}
        b.update({hash(node): node for node in other})
        return EdgeContainer(_edges=list(b.values()))

    def append(self, p_object):
        if p_object.is_valid:
            self._edges.append(p_object)
        return

    def to_edges_attrs_mapping(self):
        return {(i.from_name, i.to_name): {} for i in self._edges}


@dataclass
class Graph:
    data_type: str = None
    edge_data_type: str = None
    plugins: PluginProvider.Container = field(default_factory=lambda: PluginProvider.Container(_plugins=[]))
    converter_plugins: PluginProvider.Container = field(default_factory=lambda: PluginProvider.Container(_plugins=[]))
    _graph: networkx.DiGraph = field(default_factory=networkx.DiGraph)
    _nodes_attrs: dict = field(default_factory=dict)
    _edges_attrs: dict = field(default_factory=dict)
    _node_merge_attrs: dict = field(default_factory=dict)
    _edge_merge_attrs: dict = field(default_factory=dict)

    def __post_init__(self):
        def _process_plugin(p):
            if p.type == GraphPluginType.NODE:
                return 'node', p.install()
            elif p.type == GraphPluginType.EDGE:
                return 'edge', p.install()
            return None, None

        def _merge_result(result, n, e):
            if result[0] == 'node':
                n = merge_dicts(n, result[1])
            elif result[0] == 'edge':
                e = merge_dicts(e, result[1])
            return n, e

        nodes_attrs = self._nodes_attrs
        edges_attrs = self._edges_attrs

        pool = ThreadPool()
        results = pool.map_ignore_exception(_process_plugin, self.plugins)
        for r in results:
            nodes_attrs, edges_attrs = _merge_result(r, nodes_attrs, edges_attrs)

        self._nodes_attrs = nodes_attrs
        self._edges_attrs = edges_attrs

    def _refresh(self):
        # 去除没有 data 字段的节点 (这些数据为插件查询时引入 不作为有效节点 有效节点以 DB + Flow 为准)
        node_attrs = {k[0]: v for k, v in self._node_merge_attrs.items() if "data" in v}
        self._graph.add_nodes_from(tuple({k: v for k, v in node_attrs.items()}.items()))
        self._graph.add_edges_from(
            tuple(
                [
                    (*key, value)
                    for key, value in self._edge_merge_attrs.items()
                    if key[0] in node_attrs and key[1] in node_attrs
                ]
            )
        )

    def __lshift__(self, patch: Union[NodeContainer, EdgeContainer, PluginProvider.Container]):
        if isinstance(patch, NodeContainer):
            self._node_merge_attrs = merge_dicts(patch.to_nodes_attrs_mapping(), self._nodes_attrs)
            self._refresh()
        elif isinstance(patch, EdgeContainer):
            self._edge_merge_attrs = merge_dicts(patch.to_edges_attrs_mapping(), self._edges_attrs)
            self._refresh()
        elif isinstance(patch, PluginProvider.Container):
            plugins_mapping = defaultdict(list)
            for i in patch:
                plugins_mapping[i.type].append(i)

            need_refresh = False
            for i in plugins_mapping[GraphPluginType.NODE]:
                self._nodes_attrs = merge_dicts(self._nodes_attrs, i.install())
                self._node_merge_attrs = merge_dicts(self._node_merge_attrs, self._nodes_attrs)
                need_refresh = True

            for i in plugins_mapping[GraphPluginType.EDGE]:
                self._edges_attrs = merge_dicts(self._edges_attrs, i.install())
                self._edge_merge_attrs = merge_dicts(self._edge_merge_attrs, self._edges_attrs)
                need_refresh = True

            if plugins_mapping[GraphPluginType.NODE_UI]:
                for node_id, attrs in self._graph.nodes(data=True):
                    for plugin in plugins_mapping[GraphPluginType.NODE_UI]:
                        plugin.process(self.data_type, self.edge_data_type, attrs, self._graph)

            if plugins_mapping[GraphPluginType.EDGE_UI]:
                for f, t, attrs in self._graph.edges(data=True):
                    for plugin in plugins_mapping[GraphPluginType.EDGE_UI]:
                        plugin.process(self.data_type, self.edge_data_type, attrs, self._graph)

            if need_refresh:
                self._refresh()
        else:
            raise ValueError(f"Graph received an unsupported type: {type(patch)}")

    def __rshift__(self, other: ViewConverter) -> Dict:
        self << self.converter_plugins
        return other.convert(self._graph)

    @property
    def nodes(self):
        return self._graph.nodes(data=True)

    @property
    def edges(self):
        return self._graph.edges(data=True)

    @property
    def node_attrs(self):
        return {k[0]: v for k, v in self._nodes_attrs.items()}

    @property
    def edge_attrs(self):
        return [{"from_name": k[0], "to_name": k[1], "attrs": v} for k, v in self._edges_attrs.items()]

    @property
    def node_mapping(self):
        return {node_id: attrs for node_id, attrs in self.nodes}

    def debug(self):
        """输出 graph 到控制图和图像"""
        for n in self._graph:
            logger.info(f"{n} -> {list(self._graph.successors(n))}")

        try:
            from matplotlib import pyplot

            pos = networkx.spring_layout(self._graph)
            networkx.draw(self._graph, pos, with_labels=True, arrows=True)
            pyplot.show()
        except ImportError:
            pass

    def __or__(self, other: "Graph") -> "Graph":
        """
        以自身为基准 非标准合并另一个 Graph
        非标准合并规则:
        1. 合并后的 Graph 所有节点和边都来自 Base Graph
        2. Other Graph 只提供节点和边的指标数据
        3. Base Graph.nodes - Other Graph.nodes 的差异节点会被转换为无数据节点
        """
        other_node_mapping = {k: v for k, v in other.nodes}
        other_edge_mapping = {(f, t): a for f, t, a in other.edges}

        # [!] 不能直接对 graph 进行更新 因为会有残留数据
        remove_nodes = []
        update_nodes = {}
        for base_node, attrs in self.nodes:
            if base_node in other_node_mapping:
                update_nodes[base_node] = other_node_mapping[base_node]
            else:
                # 如果 node 不在 other_node 说明在 other_graph 中此 node 已经无数据
                remove_nodes.append(base_node)
        for k, v in update_nodes.items():
            self._graph.remove_node(k)
            self._graph.add_node(k, **v)
        for i in remove_nodes:
            self._graph.remove_node(i)
            self._graph.add_node(i, **{"data": {}})

        remove_edges = []
        update_edges = {}
        for from_node, to_node, attrs in self.edges:
            key = (from_node, to_node)
            if key in other_edge_mapping:
                update_edges[key] = other_edge_mapping[key]
            else:
                # 如果 edge 不在 other_edge 说明在 other_graph 中此 edge 已经无数据
                remove_edges.append(key)
        for k, v in update_edges.items():
            self._graph.remove_edge(*k)
            self._graph.add_edge(*k, **v)
        for i in remove_edges:
            self._graph.remove_edge(*i)
            self._graph.add_edge(*i)

        return self

    def __and__(self, other: "Graph") -> "Graph":
        """
        以自身为基准 对比另一个 Graph 的节点数据 计算出差异并返回
        """
        other_node_mapping = {k: v for k, v in other.nodes}

        for base_node, attrs in self.nodes:
            for p in self.plugins:
                if p.type != GraphPluginType.NODE:
                    continue
                # 只对节点插件计算出的指标进行对比
                if hasattr(p, "diff"):
                    diff = p.diff(attrs, other_node_mapping.get(base_node))
                    self._graph.add_node(base_node, **{"data": attrs["data"], **diff})

        return self


class GraphQuery(BaseQuery):
    @classmethod
    def create_converter(cls, bk_biz_id, app_name, export_type, service_name=None, runtime=None):
        filter_params = {"service_name": service_name} if service_name else {}
        return ViewConverter.new(
            bk_biz_id,
            app_name,
            export_type,
            runtime=runtime or {},
            filter_params=filter_params,
        )

    def execute(self, edge_data_type, converter):
        converter_plugin_runtime = self.common_params()
        if converter.filter_params:
            converter_plugin_runtime.update(converter.filter_params)
        return self.create_graph(
            with_data_type_plugin=True,
            edge_data_type=edge_data_type,
            extra_plugins=converter.extra_pre_plugins(converter_plugin_runtime),
            extra_converter_plugins=converter.extra_pre_convert_plugins(converter_plugin_runtime),
        )

    def create_graph(
        self,
        with_data_type_plugin=False,
        edge_data_type=None,
        extra_plugins=None,
        extra_converter_plugins=None,
    ):
        db_nodes = self._list_nodes_from_db()
        flow_nodes, flow_edges = self._list_nodes_and_edges_from_flow()

        plugins = PluginProvider.Container()
        if with_data_type_plugin and self.data_type:
            plugins += PluginProvider.node_plugins(self.data_type, self.common_params())
        if edge_data_type:
            plugins += PluginProvider.edge_plugins(edge_data_type, self.common_params())
        if extra_plugins:
            plugins += extra_plugins

        graph = Graph(
            plugins=plugins,
            converter_plugins=extra_converter_plugins or PluginProvider.Container(_plugins=[]),
            data_type=self.data_type,
            edge_data_type=edge_data_type,
        )
        graph << (db_nodes | flow_nodes)
        graph << flow_edges
        return graph

    def _list_nodes_from_db(self) -> [NodeContainer, EdgeContainer]:
        nodes = NodeContainer()

        found_node_keys = []
        # Resource1: 拓扑发现
        topo_nodes = ServiceHandler.list_nodes(self.bk_biz_id, self.app_name)
        for node in topo_nodes:
            extra_data = node.get("extra_data", {})

            nodes.append(
                Node(
                    display_key=node.get("topo_key"),
                    name=node.get("topo_key"),
                    category=extra_data.get("category"),
                    kind=extra_data.get("kind"),
                    extra_info={"language": extra_data["service_language"]}
                    if extra_data.get("service_language")
                    else {},
                )
            )
            found_node_keys.append(node.get("topo_key"))

        # Resource2: 自定义服务
        custom_services = ApplicationCustomService.objects.filter(
            bk_biz_id=self.bk_biz_id,
            app_name=self.app_name,
            match_type=CustomServiceMatchType.MANUAL,
        )
        for i in custom_services:
            n = f"{i.type}:{i.name}"
            if n in found_node_keys:
                continue
            nodes.append(
                Node(
                    display_key=n,
                    name=n,
                    category=i.type,
                    kind=TopoNodeKind.REMOTE_SERVICE,
                )
            )

        return nodes

    def _list_nodes_and_edges_from_flow(self) -> [NodeContainer, EdgeContainer]:
        """
        从 flow 指标中获取节点和边
        数据需要为完整数据 查询周期为应用存储周期
        """
        retention = self.application.es_retention
        start_time, end_time = get_datetime_range(period="day", distance=retention, rounding=False)
        nodes = NodeContainer()
        edges = EdgeContainer()
        dimension_mapping = self.get_metric(
            ServiceFlowCount,
            params=self.common_params(
                start_time=int(start_time.timestamp()),
                end_time=int(end_time.timestamp()),
            ),
            group_by=[
                "from_apm_service_name",
                "from_apm_service_category",
                "from_apm_service_kind",
                "to_apm_service_name",
                "to_apm_service_category",
                "to_apm_service_kind",
            ],
        ).get_dimension_values_mapping()
        for item in dimension_mapping:
            # fromService
            nodes.append(
                Node(
                    display_key=item.get("from_apm_service_name"),
                    name=item.get("from_apm_service_name"),
                    category=item.get("from_apm_service_category"),
                    kind=item.get("from_apm_service_kind"),
                )
            )

            # toService
            nodes.append(
                Node(
                    display_key=item.get("to_apm_service_name"),
                    name=item.get("to_apm_service_name"),
                    category=item.get("to_apm_service_category"),
                    kind=item.get("to_apm_service_kind"),
                )
            )
            edges.append(Edge(from_name=item.get("from_apm_service_name"), to_name=item.get("to_apm_service_name")))

        return nodes, edges
