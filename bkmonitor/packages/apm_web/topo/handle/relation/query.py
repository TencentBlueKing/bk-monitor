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
from dataclasses import dataclass
from typing import List, Type

from apm_web.topo.handle.relation.define import Node, Relation, Source, SourceProvider
from core.drf_resource import api


@dataclass
class Q:
    bk_biz_ids: List[int]
    start_time: int
    end_time: int
    target_type: str
    source_info: dict
    source_type: str = None
    step: str = None


class RelationQ:
    @classmethod
    def query(cls, qs, expect_paths=None):
        """Relation 接口普通查询"""

        response = api.unify_query.query_multi_resource_range(**{"query_list": qs})
        res = []
        for item in response.get("data", []):
            if item.get("code") != 200:
                continue
            if expect_paths and item.get("path") != expect_paths:
                continue

            source_info_id = Source.calculate_id_from_dict(item["source_info"])
            target_nodes = []
            node_ids = []
            # 路径中最后一项即为目标资源类型
            target_source_type = SourceProvider.get_source(item["path"][-1])

            for i in item.get("target_list", []):
                for j in i.get("items", []):
                    source_instance = target_source_type.create(j)
                    if source_instance.id in node_ids:
                        continue
                    node_ids.append(source_instance.id)
                    target_nodes.append(Node(source_type=target_source_type.name, source_info=source_instance))

            res.append(Relation(parent_id=source_info_id, nodes=target_nodes))

        return res

    @classmethod
    def generate_q(
        cls,
        bk_biz_id,
        source_info: Source,
        target_type: Type[Source],
        start_time,
        end_time,
        step=None,
        path_resource=None,
    ):
        """生成单个 relation 接口的查询条件"""

        return [
            {
                "bk_biz_ids": [bk_biz_id],
                "start_time": start_time,
                "end_time": end_time,
                "target_type": target_type.name,
                "source_info": source_info.to_source_info(),
                "source_type": source_info.name,
                "step": step or f"{end_time - start_time}s",
                "path_resource": path_resource or [],
            }
        ]
