# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Callable, Dict, List

from core.drf_resource import api, resource

from .base import BaseContext, EntityT


class BcsClusterContext(BaseContext):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(args, kwargs)

    def fetch(
        self, entities: List[EntityT], get_key: Callable[[EntityT], str] = lambda _e: _e.get("id", "")
    ) -> Dict[str, EntityT]:
        cluster_map: Dict[str, EntityT] = {}
        for entity in entities:
            bk_biz_id = entity.get("bk_biz_id", "")
            bcs_cluster_id = entity.get("bcs_cluster_id", "")
            cluster_info_key = f"{bk_biz_id}::{bcs_cluster_id}"

            if cluster_info_key in self._cache:
                cluster_map[cluster_info_key] = self._cache[cluster_info_key]
                continue
            clusters = resource.scene_view.get_kubernetes_cluster_choices(bk_biz_id=bk_biz_id)
            for cluster in clusters:
                new_cluster_info_key = f"{bk_biz_id}::{cluster['id']}"
                cluster_info = {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": cluster["id"],
                    "bcs_cluster_name": cluster["name"],
                }
                self._cache[new_cluster_info_key] = cluster_info
                if new_cluster_info_key == cluster_info_key:
                    cluster_map[cluster_info_key] = cluster_info

        return cluster_map


class SystemClusterContext(BaseContext):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(args, kwargs)

    def fetch(
        self, entities: List[EntityT], get_key: Callable[[EntityT], str] = lambda _e: _e.get("id", "")
    ) -> Dict[str, EntityT]:
        clusters = {}

        for entity in entities:
            bk_cloud_id = entity["bk_cloud_id"]
            if bk_cloud_id in self._cache:
                # 如果已经在缓存中，使用缓存的值
                clusters[bk_cloud_id] = self._cache[bk_cloud_id]
                continue
            # 查询云区域并更新缓存
            self._cache.update(
                {
                    cloud["bk_cloud_id"]: {"bk_cloud_id": cloud["bk_cloud_id"], "bk_cloud_name": cloud["bk_cloud_name"]}
                    for cloud in api.cmdb.search_cloud_area()
                }
            )
            # 检查当前 bk_cloud_id 是否在新缓存中
            if bk_cloud_id in self._cache:
                clusters[bk_cloud_id] = self._cache[bk_cloud_id]

        return clusters
