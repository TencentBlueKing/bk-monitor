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
import hashlib
from dataclasses import asdict, dataclass, field, fields
from typing import List, Tuple

from apm_web.topo.constants import RelationResourcePath
from core.drf_resource import api


@dataclass
class Source:
    @property
    def id(self):
        field_values = {f.name: getattr(self, f.name) for f in fields(self)}
        return self.calculate_id_from_dict(field_values)

    def to_source_info(self):
        res = {}
        for f in fields(self):
            res[f.name] = getattr(self, f.name)

        return res

    @classmethod
    def create(cls, info):
        attr = {}
        for f in fields(cls):
            if f.name not in info:
                raise ValueError(f"资源: {cls.__name__} 的 {f.name} 字段在信息中没有找到: {info}")
            attr[f.name] = info[f.name]
        return cls(**attr)

    @classmethod
    def calculate_id_from_dict(cls, info: dict):
        """从 dict 中计算资源实体的 Id"""
        combined_string = '-'.join(f"{key}:{info[key]}" for key in sorted(info.keys()))
        return hashlib.md5(combined_string.encode()).hexdigest()


@dataclass
class SourceService(Source):
    apm_application_name: str
    apm_service_name: str


@dataclass
class SourceServiceInstance(Source):
    apm_application_name: str
    apm_service_name: str
    apm_service_instance_name: str


@dataclass
class SourceSystem(Source):
    bk_target_ip: str


@dataclass
class SourceK8sPod(Source):
    bcs_cluster_id: str
    namespace: str
    pod: str


@dataclass
class SourceK8sService(Source):
    bcs_cluster_id: str
    namespace: str
    service: str


@dataclass
class Node:
    source_type: str
    source_info: Source
    children: List['Node'] = field(default_factory=list)
    id: str = None

    def __post_init__(self):
        self.id = f"{self.source_type}-{self.source_info.id}"


@dataclass
class Relation:
    parent_id: str
    nodes: List[Node]


class LayerTemplate:
    source_type: str = None
    target_type: str = None

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
            "source_type": self.source_type,
            "target_type": self.target_type,
        }


class Layer0(LayerTemplate):
    target_type = "apm_service"

    def get_layer(self) -> Node:
        return Node(
            source_type=self.target_type,
            source_info=SourceService(
                apm_application_name=self._runtime["app_name"],
                apm_service_name=self._runtime["service_name"],
            ),
        )


class ResourceLayerTemplate(LayerTemplate):
    target_type_resource: Source = None
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
                            source_type=self.target_type,
                            source_info=self.target_type_resource.create(i),
                        )
                        for i in item["target_list"][0].get("items", [])
                    ]
                    if item.get("target_list")
                    else [],
                )
            )

        return res


class ServiceToServiceInstancesLayer(ResourceLayerTemplate):
    source_type: str = "apm_service"
    target_type: str = "apm_service_instance"
    target_type_resource: Source = SourceServiceInstance
    source_path = ["apm_service", "apm_service_instance"]


class ServiceInstanceToSystemsLayer(ResourceLayerTemplate):
    source_type: str = "apm_service_instance"
    target_type: str = "system"
    target_type_resource: Source = SourceSystem
    source_path = ["apm_service_instance", "system"]


class ServiceInstanceToK8sPodLayer(ResourceLayerTemplate):
    source_type: str = "apm_service_instance"
    target_type: str = "pod"
    target_type_resource: Source = SourceK8sPod
    source_path = ["apm_service_instance", "pod"]


class K8sPodToSystemLayer(ResourceLayerTemplate):
    source_type: str = "pod"
    target_type: str = "system"
    target_type_resource: Source = SourceSystem
    source_path = ["pod", "node", "system"]


class ServiceInstanceToK8sServiceLayer(ResourceLayerTemplate):
    source_type = "apm_service_instance"
    target_type = "service"
    target_type_resource: Source = SourceK8sService
    source_path = ["apm_service_instance", "pod", "service"]


class K8sServiceToSystemLayer(ResourceLayerTemplate):
    source_type = "service"
    target_type = "system"
    target_type_resource: Source = SourceSystem
    source_path = ["service", "pod", "node", "system"]


class PathProvider:
    layer0 = Layer0
    path_mapping = {
        RelationResourcePath.INSTANCE_TO_SYSTEM.value: [
            ServiceToServiceInstancesLayer,
            ServiceInstanceToSystemsLayer,
        ],
        RelationResourcePath.INSTANCE_TO_POD_TO_SYSTEM.value: [
            ServiceToServiceInstancesLayer,
            ServiceInstanceToK8sPodLayer,
            K8sPodToSystemLayer,
        ],
        RelationResourcePath.INSTANCE_TO_SERVICE_TO_SYSTEM.value: [
            ServiceToServiceInstancesLayer,
            ServiceInstanceToK8sServiceLayer,
            K8sServiceToSystemLayer,
        ],
    }

    def __init__(self, name, runtime):
        if name not in self.path_mapping:
            raise ValueError(f"关联拓扑不支持 {name} 路径查询")

        self.name = name
        self.runtime = runtime
        self.layers = [i(rt=runtime) for i in self.path_mapping[name]]

    def build_tree(self):

        root = self.layer0(rt=self.runtime).get_layer()
        self._build_children([root], depth=0)
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
        return cls.path_mapping.keys()

    @classmethod
    def get_depth(cls, name):
        return len(cls.path_mapping[name])


class RelationEntrance:
    path: RelationResourcePath = RelationResourcePath.DEFAULT

    def __init__(self, path, **kwargs):
        self.path = path
        self._runtime = kwargs

    @property
    def relation_tree(self):
        if self.path != RelationResourcePath.DEFAULT.value:
            return self.to_json(PathProvider(self.path, self._runtime).build_tree())
        # 如果为默认逻辑 则所有路径都尝试获取 然后返回最完整的那棵树
        trees = []
        for path in PathProvider.all_path():
            trees.append((path, PathProvider(path, self._runtime).build_tree()))

        return self.to_json(self._find_complex(trees))

    def _find_complex(self, trees: List[Tuple[str, Node]]):
        """
        从树列表中返回最复杂的那颗
        树的得分：对每层的节点数量进行加权求和 层级越深此层级的节点权重越低
        """
        max_depth = max(PathProvider.get_depth(t[0]) for t in trees)
        the_best = None
        the_best_score = -1

        for i in trees:
            score = self._score_tree(i[1], 0, max_depth)
            if score > the_best_score:
                the_best_score = score
                the_best = i[1]

        return the_best

    def _score_tree(self, node, depth, max_depth):
        if depth > max_depth:
            return 0
        score = 1.0 / (depth + 1)
        for c in node.children:
            score += self._score_tree(c, depth + 1, max_depth)
        return score

    @classmethod
    def to_json(cls, tree):
        return asdict(tree)
