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
import itertools
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import List, Type

from django.utils.translation import ugettext_lazy as _

from apm_web.constants import CategoryEnum
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.topo.constants import RelationResourcePath
from apm_web.topo.handle.relation.define import (
    Node,
    Source,
    SourceK8sNode,
    SourceK8sPod,
    SourceK8sService,
    SourceService,
    SourceServiceInstance,
    SourceSystem,
    TreeInfo,
)
from core.drf_resource import api, resource


@dataclass
class Relation:
    parent_id: str
    nodes: List[Node]


class Layer:
    source_type: Source = None
    target_type: Source = None

    def __init__(self, rt):
        self._runtime = rt

    def get_layer(self, *args, **kwargs) -> [Node, List[Relation]]:
        raise NotImplementedError

    @property
    def common_params(self):
        return {
            "bk_biz_ids": [self._runtime["bk_biz_id"]],
            "start_time": self._runtime["start_time"],
            "end_time": self._runtime["end_time"],
            "step": f"{self._runtime['end_time'] - self._runtime['start_time']}s",
            "source_type": self.source_type.name,
            "target_type": self.target_type.name,
        }


class Layer0(Layer):
    source_type: Source = SourceService
    target_type: Source = SourceService

    def get_layer(self) -> Node:
        return Node(
            source_type=self.target_type.name,
            source_info=SourceService(
                apm_application_name=self._runtime["app_name"],
                apm_service_name=self._runtime["service_name"],
            ),
        )


class ResourceLayer(Layer):
    source_path: List[str] = None

    def get_layer(self, nodes: List[Node]) -> List[Relation]:
        query_lists = []
        source_ids = []
        for node in nodes:
            if node.source_info.id in source_ids:
                continue
            query_lists.append(
                {
                    **self.common_params,
                    "source_info": node.source_info.to_source_info(),
                }
            )

        response = api.unify_query.query_multi_resource_range(**{"query_list": query_lists})

        res = []
        for item in response.get("data", []):
            if item.get("code") != 200 or (self.source_path and item.get("path") != self.source_path):
                continue

            source_info_id = Source.calculate_id_from_dict(item["source_info"])
            target_nodes = []
            node_ids = []

            for i in item.get("target_list", []):
                for j in i.get("items", []):
                    source_instance = self.target_type.create(j)
                    if source_instance.id in node_ids:
                        continue
                    node_ids.append(source_instance.id)
                    target_nodes.append(Node(source_type=self.target_type.name, source_info=source_instance))

            res.append(Relation(parent_id=source_info_id, nodes=target_nodes))

        return res


class ServiceToServiceInstancesLayer(ResourceLayer):
    source_type: Source = SourceService
    target_type: Source = SourceServiceInstance
    source_path = [SourceService.name, SourceServiceInstance.name]


class ServiceInstanceToSystemsLayer(ResourceLayer):
    source_type: Source = SourceServiceInstance
    target_type: Source = SourceSystem
    source_path = [SourceServiceInstance.name, SourceSystem.name]


class ServiceInstanceToK8sPodLayer(ResourceLayer):
    source_type: Source = SourceServiceInstance
    target_type: Source = SourceK8sPod
    source_path = [SourceServiceInstance.name, SourceK8sPod.name]


class K8sPodToSystemLayer(ResourceLayer):
    source_type: Source = SourceK8sPod
    target_type: Source = SourceSystem
    source_path = [SourceK8sPod.name, SourceK8sNode.name, SourceSystem.name]


class ServiceInstanceToK8sServiceLayer(ResourceLayer):
    source_type: Source = SourceServiceInstance
    target_type: Source = SourceK8sService
    source_path = [SourceServiceInstance.name, SourceK8sPod.name, SourceK8sService.name]


class K8sServiceToSystemLayer(ResourceLayer):
    source_type: Source = SourceK8sService
    target_type: Source = SourceSystem
    source_path = [SourceK8sService.name, SourceK8sPod.name, SourceK8sNode.name, SourceSystem.name]


@dataclass
class PathTemplateNode:
    pass


@dataclass
class SidebarGroup:
    id: str = None
    name: str = None


@dataclass
class ServiceGroup(SidebarGroup):
    id: str = "service"
    name: str = _("服务")


@dataclass
class HostGroup(SidebarGroup):
    id: str = "host"
    name: str = _("Kubernetes")


@dataclass
class DataCenterGroup(SidebarGroup):
    id: str = "data_center"
    name: str = _("数据中心")


@dataclass
class PathTemplateSidebar:
    # --- runtime attrs
    _sidebar_index: int
    _tree: Node
    _tree_infos: List[TreeInfo]
    _tree_info: TreeInfo
    # 此侧边栏是否有节点数据
    have_data: bool = False
    # ---

    id: str = None
    name: str = None
    bind_source_type: Source = None
    group: SidebarGroup = None

    def combine_nodes(self, nodes: List[Node]):
        """
        处理当前侧边栏对应的资源实体的所有节点 返回合并后的节点列表
        正常的节点会合并
        异常的节点不会合并
        """
        # 去掉重复节点
        unique_nodes = set(nodes)

        # 根据告警来区分出节点的状态 适用于: system, pod, service
        if self.bind_source_type.name == SourceSystem.name:
            # 检查 system 的告警
            r_nodes = self._group_by_alert(
                "ip",
                "bk_target_ip",
                "("
                + " OR ".join(
                    [f"ip: {getattr(i.source_info, 'bk_target_ip')}" for i in unique_nodes]
                    + [f"tags.ip: {getattr(i.source_info, 'bk_target_ip')}" for i in unique_nodes]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceK8sPod.name:
            r_nodes = self._group_by_alert(
                "pod",
                "pod",
                "("
                + " OR ".join(
                    [
                        f"("
                        f"tags.pod: {getattr(i.source_info, 'pod')} "
                        f"AND tags.bcs_cluster_id: {getattr(i.source_info, 'bcs_cluster_id')} "
                        f"AND tags.namespace: {getattr(i.source_info, 'namespace')}"
                        f")"
                        for i in unique_nodes
                    ]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceK8sService.name:
            r_nodes = self._group_by_alert(
                "service",
                "service",
                "("
                + " OR ".join(
                    [
                        f"("
                        f"tags.service: {getattr(i.source_info, 'service')} "
                        f"AND tags.bcs_cluster_id: {getattr(i.source_info, 'bcs_cluster_id')} "
                        f"AND tags.namespace: {getattr(i.source_info, 'namespace')}"
                        f")"
                        for i in unique_nodes
                    ]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceService.name:
            # 如果是服务 需要增加 icon 返回 并且不需要合并
            r_nodes = []
            for i in nodes:
                node = ServiceHandler.get_node(
                    self._tree_info.runtime["bk_biz_id"],
                    getattr(i.source_info, "apm_application_name"),
                    getattr(i.source_info, "apm_service_name"),
                    raise_exception=False,
                )
                r_nodes.append(
                    {
                        **i.info,
                        "sidebar_id": self.id,
                        "collapses": [],
                        "category": node.get("extra_data", {}).get("category") if node else CategoryEnum.OTHER,
                        "status": "normal",
                    }
                )
        else:
            # 其他类型不需要进行合并
            r_nodes = [{**i.info, "sidebar_id": self.id, "collapses": [], "status": "normal"} for i in nodes]

        return r_nodes

    def _group_by_alert(self, group_by_key, node_key, query_string, nodes: List[Node]):
        """根据告警状态来聚合节点"""

        alerts = self._search_alert(query_string)

        mapping = defaultdict(list)
        for item in alerts:
            for i in item["dimensions"]:
                if group_by_key in i["key"]:
                    mapping[i["value"]].append(item.get("severity"))

        normal_nodes = set()
        error_nodes = set()
        for node in nodes:
            v = getattr(node.source_info, node_key, None)
            if v in mapping:
                error_nodes.add(node)
            else:
                normal_nodes.add(node)

        res = []
        # 异常节点不需要折叠
        for n in error_nodes:
            res.append({**n.info, "sidebar_id": self.id, "collapses": [], "status": "abnormal"})
        # 正常节点折叠
        if normal_nodes:
            # 页面显示为按照排序后的第一个
            first = sorted(normal_nodes, key=lambda p: getattr(p.source_info, node_key))[0]
            res.append(
                {
                    **first.info,
                    "sidebar_id": self.id,
                    "collapses": [{**n.info, "status": "normal"} for n in normal_nodes]
                    if len(normal_nodes) > 1
                    else [],
                    "status": "normal",
                }
            )

        return res

    def _search_alert(self, query_string):
        if query_string == "()":
            return []

        full_query_string = f"{query_string} AND status: ABNORMAL"
        query_params = {
            "bk_biz_ids": [self._tree_info.runtime["bk_biz_id"]],
            "query_string": full_query_string,
            "start_time": self._tree_info.runtime["start_time"],
            "end_time": self._tree_info.runtime["end_time"],
            "page_size": 1000,
        }
        return resource.fta_web.alert.search_alert(**query_params).get("alerts", [])

    @property
    def info(self):
        return {
            "id": self.id,
            "name": self.name,
            "bind_source_type": self.bind_source_type.name,
            "options": self.options,
        }

    @classmethod
    def option_info(cls):
        """作为选项提供时 返回的数据格式"""
        return {
            "id": cls.id,
            "name": cls.name,
            "bind_source_type": cls.bind_source_type.name,
        }

    @property
    def options(self):
        """获取此侧边栏的可选项"""
        options = []
        if not self._tree_infos:
            return options

        # 可以替换的条件为:
        # 此 sidebar 绑定的 source_type 对应的 layer 在层级模板 layers 中有平替
        # (即 layer 在某个 pathTemplate 中层级和 layer 在此 tree 的 pathTemplate 中处于索引的位置一致并且有数据)
        for t in self._tree_infos:
            if t == self._tree_info:
                continue

            other_path_template = PathProvider.get_template(t.paths)
            # TODO 这里其实还需要判断截止至 self._sidebar_index 前的元素绑定的资源是否都一致
            # TODO 现在只根据层级判断有问题 但是我们现在页面上层级是固定的所以不需要考虑这个问题
            if len(other_path_template.sidebars) > self._sidebar_index:
                other_path_template_sidebar = other_path_template.sidebars[self._sidebar_index]
                if other_path_template_sidebar.name != self.name and Node.get_depth(self._tree) >= self._sidebar_index:
                    if t.layers_have_data[self._sidebar_index]:
                        # 其他模版的 sidebar_index 层有数据 说明可以平替了
                        options.append(other_path_template_sidebar.option_info())
                        # 加上自身
                        options.append(self.option_info())

        return options


@dataclass
class ServiceSidebar(PathTemplateSidebar):
    id: str = SourceService.name
    name: str = "Service"
    bind_source_type: Source = SourceService
    group: SidebarGroup = ServiceGroup


@dataclass
class ServiceInstanceSidebar(PathTemplateSidebar):
    id: str = SourceServiceInstance.name
    name: str = "Service Instance"
    bind_source_type: Source = SourceServiceInstance
    group: SidebarGroup = ServiceGroup


@dataclass
class K8sPodSidebar(PathTemplateSidebar):
    id: str = SourceK8sPod.name
    name: str = "Pod"
    bind_source_type: Source = SourceK8sPod
    group: SidebarGroup = HostGroup


@dataclass
class K8sServiceSidebar(PathTemplateSidebar):
    id: str = SourceK8sService.name
    name: str = "Service"
    bind_source_type: Source = SourceK8sService
    group: SidebarGroup = HostGroup


@dataclass
class SystemSidebar(PathTemplateSidebar):
    id: str = SourceSystem.name
    name: str = "IDC"
    bind_source_type: Source = SourceSystem
    group: SidebarGroup = DataCenterGroup


@dataclass
class PathTemplate:
    layers: List[Type[Layer]]
    sidebars: List[Type[PathTemplateSidebar]]

    def to_tree_json(self, tree: Node, _):
        return asdict(tree)

    def to_layers_json(self, tree: Node, tree_info, tree_infos: List[TreeInfo]):
        sidebars = []

        # Step1: 先获取 tree 的所有边
        all_edges = Node.get_all_edges(tree)
        all_layer_nodes = []

        for sidebar_index, sidebar in enumerate(self.sidebars):
            sidebar_instance = sidebar(
                _sidebar_index=sidebar_index, _tree=tree, _tree_infos=tree_infos, _tree_info=tree_info  # noqa
            )
            # 获取侧边栏绑定的资源实体
            sidebar_layer_index = next(
                (
                    index
                    for index, i in enumerate(self.layers)
                    if i.target_type.name == sidebar_instance.bind_source_type.name
                ),
                None,
            )
            if sidebar_layer_index is None:
                raise ValueError(f"[PathTemplate] 无法在路径中找到资源实体: {sidebar_instance.bind_source_type.name}")

            # layer 层级与 layer_nodes 列表下标索引一致
            layer_nodes = Node.list_nodes_by_level(tree, sidebar_layer_index)
            if layer_nodes:
                sidebar_instance.have_data = True
            combine_layer_nodes = sidebar_instance.combine_nodes(layer_nodes)

            all_layer_nodes.append(combine_layer_nodes)
            sidebars.append(sidebar_instance)

        return {
            "edges": self._process_edges(all_edges, all_layer_nodes),
            "nodes": list(itertools.chain(*all_layer_nodes)),
            "sidebars": self._group_sidebar(sidebars),
        }

    @classmethod
    def _process_edges(cls, all_edges, layer_nodes):
        """根据聚合后的节点 处理边数据"""
        node_merged_id = {}

        for layer in layer_nodes:
            for node in layer:
                if node["collapses"]:
                    for item in node["collapses"]:
                        node_merged_id[item["id"]] = node["id"]

        merged_edges_mapping = defaultdict(list)

        for edge in all_edges:
            from_node, to_node = edge
            from_node_merged = node_merged_id.get(from_node, from_node)
            to_node_merged = node_merged_id.get(to_node, to_node)

            if from_node_merged != to_node_merged:
                merged_edge = (from_node_merged, to_node_merged)
                merged_edges_mapping[merged_edge].append((from_node, to_node))

        return [
            {
                "source": e[0],
                "target": e[1],
                "original": [{"source": i[0], "target": i[1]} for i in set(original_edges)]
                if len(original_edges) > 1
                else [],
            }
            for e, original_edges in merged_edges_mapping.items()
        ]

    @classmethod
    def _group_sidebar(cls, sidebar_instances: List[PathTemplateSidebar]):
        """对侧边栏进行分组归类"""

        group_mapping = defaultdict(dict)
        for index, i in enumerate(sidebar_instances):
            if not i.have_data:
                # 无数据时 不显示此侧边栏
                continue
            if i.group.id in group_mapping:
                group_mapping[i.group.id]["list"].append(i.info)
            else:
                group_mapping[i.group.id] = {
                    "id": i.group.id,
                    "name": i.group.name,
                    "list": [i.info],
                }

        return list(group_mapping.values())


class PathProvider:
    path_mapping = {
        RelationResourcePath.INSTANCE_TO_SYSTEM.value: PathTemplate(
            layers=[
                Layer0,
                ServiceToServiceInstancesLayer,
                ServiceInstanceToSystemsLayer,
            ],
            sidebars=[
                ServiceSidebar,
                ServiceInstanceSidebar,
                SystemSidebar,
            ],
        ),
        RelationResourcePath.INSTANCE_TO_POD_TO_SYSTEM.value: PathTemplate(
            layers=[
                Layer0,
                ServiceToServiceInstancesLayer,
                ServiceInstanceToK8sPodLayer,
                K8sPodToSystemLayer,
            ],
            sidebars=[
                ServiceSidebar,
                ServiceInstanceSidebar,
                K8sPodSidebar,
                SystemSidebar,
            ],
        ),
        RelationResourcePath.INSTANCE_TO_SERVICE_TO_SYSTEM.value: PathTemplate(
            layers=[
                Layer0,
                ServiceToServiceInstancesLayer,
                ServiceInstanceToK8sServiceLayer,
                K8sServiceToSystemLayer,
            ],
            sidebars=[
                ServiceSidebar,
                ServiceInstanceSidebar,
                K8sServiceSidebar,
                SystemSidebar,
            ],
        ),
    }

    _CONNECT_CHAR = "_to_"

    def __init__(self, paths, runtime):
        path_name = self.to_path_template_key(paths)
        if path_name not in self.path_mapping:
            raise ValueError(f"关联拓扑中没有找到 {paths} 路径")

        self.runtime = runtime
        self.layers = [i(rt=runtime) for i in self.path_mapping[path_name].layers]

    @classmethod
    def to_path_template_key(cls, paths):
        return cls._CONNECT_CHAR.join(paths)

    def build_tree(self):
        # depth = 0
        root = self.layers[0].get_layer()
        self._build_children([root], depth=1)
        return root

    def _build_children(self, nodes, depth):

        if depth >= len(self.layers) or not nodes:
            return

        parent_id_mapping = {i.source_info.id: [] for i in nodes}
        for relation in self.layers[depth].get_layer(nodes):
            parent_id_mapping[relation.parent_id].extend(relation.nodes)

        for node in nodes:
            if node.source_info.id in parent_id_mapping:
                node.children.extend(parent_id_mapping[node.source_info.id])
            self._build_children(node.children, depth + 1)

    @classmethod
    def all_path(cls):
        return [i.split(cls._CONNECT_CHAR) for i in cls.path_mapping.keys()]

    @classmethod
    def get_depth(cls, paths):
        return len(cls.path_mapping[cls.to_path_template_key(paths)].layers)

    @classmethod
    def get_template(cls, paths):
        return cls.path_mapping[cls.to_path_template_key(paths)]
