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

from apm_web.topo.constants import SourceType


@dataclass
class Source:
    name = None

    _ignore_fields = ["name"]

    @property
    def id(self):
        field_values = {f.name: getattr(self, f.name) for f in fields(self) if f.name not in self._ignore_fields}
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
            if f.name in cls._ignore_fields:
                continue
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
    name: str = SourceType.APM_SERVICE.value


@dataclass
class SourceServiceInstance(Source):
    apm_application_name: str
    apm_service_name: str
    apm_service_instance_name: str
    name: str = SourceType.APM_SERVICE_INSTANCE.value


@dataclass
class SourceSystem(Source):
    bk_target_ip: str
    name: str = SourceType.SYSTEM.value


@dataclass
class SourceK8sPod(Source):
    bcs_cluster_id: str
    namespace: str
    pod: str
    name: str = SourceType.POD.value


@dataclass
class SourceK8sNode(Source):
    bcs_cluster_id: str
    node: str
    name: str = SourceType.NODE.value


@dataclass
class SourceK8sService(Source):
    bcs_cluster_id: str
    namespace: str
    service: str
    name: str = SourceType.SERVICE.value


@dataclass
class Node:
    source_type: str
    source_info: Source
    children: List['Node'] = field(default_factory=list)
    id: str = None

    def __post_init__(self):
        self.id = f"{self.source_type}-{self.source_info.id}"

    @classmethod
    def list_nodes_by_level(cls, node: "Node", level, current_level=0):
        """从 node 节点开始 获取树的第 level 层的所有节点 返回列表"""
        if level == 0:
            # 返回自身关联
            return [node]

        if current_level == level - 1:
            return node.children

        res = []
        for c in node.children:
            res.extend(cls.list_nodes_by_level(c, level, current_level + 1))
        return res

    @classmethod
    def get_depth(cls, node):
        if not node.children:
            return 1

        return 1 + max(cls.get_depth(c) for c in node.children)

    @property
    def info(self):
        """打印节点自身信息（不包含叶子）"""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_info": asdict(self.source_info),
        }

    @classmethod
    def get_all_edges(cls, node, parent_id=None) -> List[Tuple[str, str]]:
        """返回以此 node 往下的所有边"""
        res = []
        if parent_id is not None:
            res.append((parent_id, node.id))

        for c in node.children:
            res.extend(cls.get_all_edges(c, node.id))

        return res


@dataclass
class TreeInfo:
    # 根节点的 Id
    root_id: str
    # tree 的层级模板
    paths: List[str]
    # 树的层级是否完整 (即根据 layers 判断是否每一层都有节点)
    is_complete: bool
    runtime: dict
    layers_have_data: List[bool]
