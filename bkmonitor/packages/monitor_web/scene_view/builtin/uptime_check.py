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
import json
from typing import Dict, Optional

from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin import BuiltinProcessor


class UptimeCheckBuiltinProcessor(BuiltinProcessor):
    task_detail_view = None

    @classmethod
    def load_builtin_views(cls):
        if cls.task_detail_view is None:
            cls.task_detail_view = cls._read_builtin_view_config("uptime_check_task_detail")

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_view):
        if existed_view:
            return

        cls.load_builtin_views()
        view_config = cls.task_detail_view
        SceneViewModel.objects.create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            type=view_type,
            id=view_config["id"],
            name=view_config["name"],
            mode=view_config["mode"],
            variables=view_config.get("variables", []),
            panels=view_config.get("panels", []),
            list=view_config.get("list", []),
            order=view_config.get("order", []),
            options=view_config.get("options", {}),
        )

    @classmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> Dict:
        if view.id != "task" or view.type != "detail":
            return {}

        cls.load_builtin_views()
        return json.loads(json.dumps(cls.task_detail_view))

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id == "uptime_check"

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        return None
