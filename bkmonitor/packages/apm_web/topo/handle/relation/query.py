"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass
from typing import Any

from apm_web.topo.handle.relation.define import Node, Relation, Source, SourceProvider
from core.drf_resource import api


@dataclass
class Q:
    bk_biz_ids: list[int]
    start_time: int
    end_time: int
    target_type: str
    source_info: dict
    source_type: str = None
    step: str = None


class RelationQ:
    @classmethod
    def query(cls, qs, expect_paths=None, fill_with_empty=False):
        """Relation 接口普通查询"""

        # 从查询参数提取业务 ID，用于数据查询鉴权
        bk_biz_ids: set[int] = set()
        for query_config in qs:
            bk_biz_ids |= set(query_config.get("bk_biz_ids") or [])

        query_params: dict[str, Any] = {"query_list": qs}
        if bk_biz_ids:
            query_params["bk_biz_ids"] = list(bk_biz_ids)

        response = api.unify_query.query_multi_resource_range(**query_params)
        res = []
        for item in response.get("data", []):
            if item.get("code") != 200:
                if fill_with_empty:
                    res.append(None)
                continue
            if expect_paths and item.get("path") != expect_paths:
                if fill_with_empty:
                    res.append(None)
                continue

            source_info_id = Source.calculate_id_from_dict(item["source_info"])
            target_nodes = []
            node_ids = []
            # 路径中最后一项即为目标资源类型
            target_source_type = SourceProvider.get_source(item["path"][-1])

            for i in item.get("target_list", []):
                for j in i.get("items", []):
                    if not j:
                        continue

                    source_instance = target_source_type.create(j)
                    if source_instance.id in node_ids:
                        continue
                    node_ids.append(source_instance.id)
                    target_nodes.append(Node(source_type=target_source_type.name, source_info=source_instance))

            res.append(Relation(parent_id=source_info_id, source_info=item["source_info"], nodes=target_nodes))

        return res

    @classmethod
    def generate_q(
        cls,
        bk_biz_id,
        source_info: Source | dict[str, Any],
        target_type: type[Source],
        start_time,
        end_time,
        step=None,
        path_resource=None,
    ):
        """生成单个 relation 接口的查询条件"""

        if isinstance(source_info, dict):
            source_type: str = source_info["name"]
            source_info_dict: dict[str, Any] = source_info
        else:
            source_type: str = source_info.name
            source_info_dict: dict[str, Any] = source_info.to_source_info()

        return [
            {
                "bk_biz_ids": [bk_biz_id],
                "start_time": start_time,
                "end_time": end_time,
                "target_type": target_type.name,
                "source_info": source_info_dict,
                "source_type": source_type,
                "step": step or f"{end_time - start_time}s",
                "path_resource": [i.name for i in path_resource] if path_resource else [],
            }
        ]

    @classmethod
    def generate_multi_q(
        cls,
        bk_biz_id,
        source_infos: list[Source],
        target_type: type[Source],
        start_time,
        end_time,
        step=None,
        path_resource=None,
    ):
        """生成单个 relation 接口的查询条件"""
        return [
            cls.generate_q(bk_biz_id, i, target_type, start_time, end_time, step, path_resource)[0]
            for i in source_infos
        ]
