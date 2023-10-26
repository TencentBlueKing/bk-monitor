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
import logging
from typing import Dict, Optional

from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel
from monitor_web.scene_view.builtin import BuiltinProcessor, NormalProcessorMixin

from api.cmdb.client import list_biz_hosts

logger = logging.getLogger(__name__)


class AlertBuiltinProcessor(NormalProcessorMixin, BuiltinProcessor):
    """告警中心视图配置"""

    SCENE_ID = "alert"
    builtin_views: Dict = None

    filenames = [
        # ⬇️ 告警中心视图
        "alert-log",
    ]

    @classmethod
    def load_builtin_views(cls):
        cls.builtin_views = {}
        for filename in cls.filenames:
            cls.builtin_views[filename] = cls._read_builtin_view_config(filename)

    @classmethod
    def exists_views(cls, name):
        """是否存在指定的视图"""
        return bool(next((i for i in cls.filenames if name in i), None))

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        view = SceneViewModel.objects.get(bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id)
        if "order" in view_config:
            view.order = view_config["order"]
        view.save()
        return view

    @classmethod
    def get_view_config(cls, view: SceneViewModel, params: Dict = None, *args, **kwargs) -> Dict:
        cls.load_builtin_views()

        bk_biz_id = view.bk_biz_id
        builtin_view = f"{view.scene_id}-{view.id}"

        view_config = cls.builtin_views[builtin_view]
        view_config = cls._replace_variable(view_config, "${bk_biz_id}", bk_biz_id)

        if builtin_view == "alert-log":

            keyword = None

            if params.get("bk_host_id"):
                # 需要转为IP地址
                keyword = cls._get_bk_host_innerip(bk_biz_id, params["bk_host_id"])
            elif params.get("bk_host_innerip"):
                keyword = params["bk_host_innerip"]

            if keyword:
                cls._handle_log_chart_keyword(view_config, keyword)

        return view_config

    @classmethod
    def _handle_log_chart_keyword(cls, view_config, keyword):
        """
        处理日志标签页默认的查询条件
        对于告警日志处 如果存在IP 需要将此IP作为查询关键词
        """

        for overview_panel in view_config.get("overview_panels", []):
            overview_panel["options"] = {"related_log_chart": {"defaultKeyword": keyword}}

    @classmethod
    def _get_bk_host_innerip(cls, bk_biz_id, bk_host_id):
        try:
            params = {
                "page": {"start": 0, "limit": 1},
                "fields": ["bk_cloud_id", "bk_host_innerip", "bk_host_id"],
                "bk_biz_id": bk_biz_id,
                "host_property_filter": {
                    "condition": "AND",
                    "rules": [{"field": "bk_host_id", "operator": "equal", "value": int(bk_host_id)}],
                },
            }

            response = list_biz_hosts(params)

            if response.get("count"):
                info = response.get("info")
                if info:
                    return info[0].get("bk_host_innerip")
            return None

        except Exception:  # noqa
            logger.warning(f"[Alert] ")
            return None

    @classmethod
    def _replace_variable(cls, view_config, target, value):
        """替换模版中的变量"""
        content = json.dumps(view_config)
        return json.loads(content.replace(target, str(value)))

    @classmethod
    def create_default_order(cls, bk_biz_id: int, scene_id: str):
        # 顶部栏优先级配置
        SceneViewOrderModel.objects.update_or_create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            type="",
            defaults={"config": ["log"]},
        )

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith(cls.SCENE_ID)

    @classmethod
    def is_custom_view_list(cls) -> bool:
        return False

    @classmethod
    def is_custom_sort(cls, scene_id) -> bool:
        """
        是否需要自定义视图列表的排序
        """

        return False

    @classmethod
    def convert_custom_params(cls, scene_id, params):
        return {
            "bk_host_innerip": params.get("bk_host_innerip"),
            "bk_cloud_id": params.get("bk_cloud_id"),
            "bk_host_id": params.get("bk_host_id"),
        }
