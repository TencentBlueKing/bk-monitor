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
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import List, Type

from django.utils.translation import ugettext_lazy as _

from apm_web.constants import AlertLevel
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.topo.constants import RelationResourcePath
from apm_web.topo.handle.graph_plugin import NodeColor
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
            "start_time": self._runtime["start_time"],
            "end_time": self._runtime["end_time"],
            # + 1s 使接口能够完全覆盖 start_time 和 end_time 保持只返回一个元素
            "step": f"{self._runtime['end_time'] - self._runtime['start_time'] + 1}s",
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
        response = api.unify_query.query_multi_resource_range(
            **{
                "query_list": [
                    {
                        **self.common_params,
                        "source_info": node.source_info.to_source_info(),
                    }
                    for node in nodes
                ]
            }
        )

        res = []
        for item in response.get("data", []):
            if item.get("code") != 200 or (self.source_path and item.get("path") != self.source_path):
                continue

            res.append(
                Relation(
                    parent_id=Source.calculate_id_from_dict(item["source_info"]),
                    nodes=[
                        Node(
                            source_type=self.target_type.name,
                            source_info=self.target_type.create(i),
                        )
                        for i in item["target_list"][0].get("items", [])
                    ]
                    if item.get("target_list")
                    else [],
                )
            )

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
    name: str = _("主机/云平台")


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
    # ---

    id: str = None
    name: str = None
    bind_source_type: Source = None
    group: SidebarGroup = None

    def combine_and_generate(self, parent_id, nodes: List[Node]):
        """
        处理(合并或者转换等逻辑)当前侧边栏对应的资源实体的所有节点 返回此层的节点和与上层的连线
        需要根据是否有告警来对此叶子节点划分出三种不同的状态(正常、预警、告警)
        """

        # 根据告警来区分出节点的状态 适用于: system, pod, service
        if self.bind_source_type.name == SourceSystem.name:
            # 检查 system 的告警
            r_nodes = self._group_by_nodes(
                "ip",
                "bk_target_ip",
                "("
                + " OR ".join(
                    [f"ip: {getattr(i.source_info, 'bk_target_ip')}" for i in nodes]
                    + [f"tags.ip: {getattr(i.source_info, 'bk_target_ip')}" for i in nodes]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceK8sPod.name:
            r_nodes = self._group_by_nodes(
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
                        for i in nodes
                    ]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceK8sService.name:
            r_nodes = self._group_by_nodes(
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
                        for i in nodes
                    ]
                )
                + ")",
                nodes,
            )
        elif self.bind_source_type.name == SourceService.name:
            this_tree_info = next(i for i in self._tree_infos if i.root_id == self._tree.id)

            # 如果是服务 需要增加 icon 返回
            r_nodes = [
                {
                    **i.info,
                    "sidebar_id": self.id,
                    "collapses": [],
                    "color": NodeColor.Color.WHITE,
                    "category": ServiceHandler.get_node(
                        this_tree_info.runtime["bk_biz_id"],
                        getattr(i.source_info, "apm_application_name"),
                        getattr(i.source_info, "apm_service_name"),
                    )
                    .get("extra_data", {})
                    .get("category"),
                }
                for i in nodes
            ]
        else:
            r_nodes = [
                {**i.info, "sidebar_id": self.id, "collapses": [], "color": NodeColor.Color.WHITE} for i in nodes
            ]

        return r_nodes, [{"source": parent_id, "target": i["id"]} for i in r_nodes if i["id"] != parent_id]

    def _group_by_nodes(self, group_by_key, node_key, query_string, nodes):
        alerts = self._search_alert(query_string)

        mapping = defaultdict(list)
        for item in alerts:
            for i in item["tags"]:
                if i["key"] in group_by_key:
                    mapping[i["value"]].append(item.get("severity"))

        status_mapping = defaultdict(list)
        for node in nodes:
            v = getattr(node.source_info, node_key, None)
            color = NodeColor.Color.GREEN
            if v in mapping:
                if any(i == AlertLevel.ERROR for i in mapping[v]):
                    color = NodeColor.Color.RED
                else:
                    color = NodeColor.Color.YELLOW

            status_mapping[color].append({**node.info, "color": color})

        res = []
        for status, status_nodes in status_mapping.items():
            if len(status_nodes) == 1:
                # 只有一个 不需要折叠
                res.append(
                    {
                        **status_nodes[0],
                        "sidebar_id": self.id,
                        "collapses": [],
                        "color": status,
                    }
                )
            else:
                # 发生折叠 节点使用第一个节点的信息
                res.append(
                    {
                        **status_nodes[0],
                        "sidebar_id": self.id,
                        "collapses": status_nodes,
                        "color": status,
                    }
                )

        return res

    def _search_alert(self, query_string):
        this_tree_info = next(i for i in self._tree_infos if i.root_id == self._tree.id)
        full_query_string = f"{query_string} AND status: ABNORMAL"
        query_params = {
            "bk_biz_ids": [this_tree_info.runtime["bk_biz_id"]],
            "query_string": full_query_string,
            "start_time": this_tree_info.runtime["start_time"],
            "end_time": this_tree_info.runtime["end_time"],
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

        this_tree_info = next(i for i in self._tree_infos if i.root_id == self._tree.id)
        # 可以替换的条件为:
        # 此 sidebar 绑定的 source_type 对应的 layer 在层级模板 layers 中有平替
        # (即 layer 在某个 pathTemplate 中层级和 layer 在此 tree 的 pathTemplate 中处于索引的位置一致)
        for t in self._tree_infos:
            if t == this_tree_info:
                continue

            other_path_template = PathProvider.get_template(t.paths)
            if len(other_path_template.sidebars) >= self._sidebar_index:
                other_path_template_sidebar = other_path_template.sidebars[self._sidebar_index]
                if other_path_template_sidebar.name != self.name and Node.get_depth(self._tree) >= self._sidebar_index:
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

    def to_layers_json(self, tree: Node, tree_infos: List[TreeInfo]):
        nodes = []
        edges = []
        sidebars = []

        sidebar_count_info = []
        for sidebar_index, sidebar in enumerate(self.sidebars):
            sidebar_instance = sidebar(_sidebar_index=sidebar_index, _tree=tree, _tree_infos=tree_infos)  # noqa
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

            layer_nodes_mapping = Node.get_relation_mapping(tree, sidebar_layer_index)

            # 统计当前侧边栏的总、异常节点数量
            sidebar_node_total_count = 0
            sidebar_node_error_count = 0
            for parent_id, sidebar_nodes in layer_nodes_mapping.items():
                l_nodes, l_edges = sidebar_instance.combine_and_generate(parent_id, sidebar_nodes)
                nodes += l_nodes
                edges += l_edges
                sidebar_node_total_count += len(l_nodes)
                sidebar_node_error_count += len(
                    [i for i in l_nodes if i["color"] not in [NodeColor.Color.WHITE, NodeColor.Color.GREEN]]
                )

            sidebar_count_info.append((sidebar_node_error_count, sidebar_node_total_count))
            sidebars.append(sidebar_instance)

        return {"edges": edges, "nodes": nodes, "sidebars": self._group_sidebar(sidebars, sidebar_count_info)}

    @classmethod
    def _group_sidebar(cls, sidebar_instances: List[PathTemplateSidebar], sidebar_count_info):
        """对侧边栏进行分组归类"""

        group_mapping = defaultdict(dict)
        for index, i in enumerate(sidebar_instances):
            if i.group.id in group_mapping:
                group_mapping[i.group.id]["list"].append(
                    {
                        **i.info,
                        "total_count": sidebar_count_info[index][-1],
                        "error_count": sidebar_count_info[index][0],
                    }
                )
            else:
                group_mapping[i.group.id] = {
                    "id": i.group.id,
                    "name": i.group.name,
                    "list": [
                        {
                            **i.info,
                            "total_count": sidebar_count_info[index][-1],
                            "error_count": sidebar_count_info[index][0],
                        }
                    ],
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
