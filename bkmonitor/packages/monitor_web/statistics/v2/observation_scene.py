# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from core.drf_resource import resource
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class ObservationSceneCollector(BaseCollector):
    """
    自定义场景
    """

    @register(labelnames=("bk_biz_id", "bk_biz_name", "scene_type", "plugin_id", "plugin_name"))
    def observation_scene_count(self, metric: Metric):
        """
        自定义场景数
        """
        error_list = []
        for bk_biz_id in self.biz_info:
            try:
                scene_list = resource.scene_view.get_observation_scene_list(bk_biz_id=bk_biz_id)
                for scene in scene_list:
                    metric.labels(
                        bk_biz_id=int(bk_biz_id),
                        bk_biz_name=self.get_biz_name(bk_biz_id),
                        scene_type=scene["scene_type"],
                        plugin_id=scene["id"],
                        plugin_name=scene["name"],
                    ).inc()
            except SystemExit as exec:
                error_list.append(exec)
                continue

        if error_list:
            raise (error_list[0])
