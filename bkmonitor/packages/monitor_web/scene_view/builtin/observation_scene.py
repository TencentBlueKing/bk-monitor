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
from typing import Dict, List, Tuple, Type

from monitor_web.models.scene_view import SceneViewModel

from .collect import CollectBuiltinProcessor
from .custom_event import CustomEventBuiltinProcessor
from .custom_metric import CustomMetricBuiltinProcessor


class ObservationSceneBuiltinProcessor(CollectBuiltinProcessor):
    """
    观测场景视图
    """

    @classmethod
    def get_processor(cls, scene_id: str) -> Tuple[str, Type[CollectBuiltinProcessor]]:
        """
        按场景ID获取对应类型处理器
        """
        scene_id = scene_id[6:]
        processors = [CollectBuiltinProcessor, CustomMetricBuiltinProcessor, CustomEventBuiltinProcessor]
        for p in processors:
            if p.is_builtin_scene(scene_id):
                return scene_id, p
        raise ValueError(f"scene({scene_id}) is invalid")

    @classmethod
    def get_default_view_config(cls, bk_biz_id: int, scene_id: str):
        scene_id, processor = cls.get_processor(scene_id)
        return processor.get_default_view_config(bk_biz_id, scene_id)

    @classmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> Dict:
        view.scene_id, processor = cls.get_processor(view.scene_id)
        return processor.get_view_config(view)

    @classmethod
    def get_auto_view_panels(cls, view: SceneViewModel) -> Tuple[List[Dict], List[Dict]]:
        """
        获取平铺视图配置
        """
        view.scene_id, processor = cls.get_processor(view.scene_id)
        return processor.get_auto_view_panels(view)

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith("scene_")
