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
import abc
import json
import os
from typing import Dict, List, Optional, Set

from django.utils.translation import gettext_lazy as _
from monitor_web.models.scene_view import SceneViewModel

BUILTIN_SCENES = {
    "host": {"name": _("主机监控"), "detail": {"host", "process"}, "overview": {"host", "process"}},
    "kubernetes": {"name": _("Kubernetes监控"), "detail": {"cluster"}, "overview": {"cluster"}},
    "uptime_check": {"name": _("服务拨测"), "detail": {"task"}, "overview": set()},
}

_BUILTIN_VIEWS: Optional[Dict[str, Dict]] = None


def get_builtin_processors():
    """
    内置视图处理器
    """
    from .alert import AlertBuiltinProcessor
    from .apm import ApmBuiltinProcessor
    from .collect import CollectBuiltinProcessor
    from .custom_event import CustomEventBuiltinProcessor
    from .custom_metric import CustomMetricBuiltinProcessor
    from .host import HostBuiltinProcessor
    from .kubernetes import KubernetesBuiltinProcessor
    from .observation_scene import ObservationSceneBuiltinProcessor
    from .uptime_check import UptimeCheckBuiltinProcessor

    return [
        HostBuiltinProcessor,
        KubernetesBuiltinProcessor,
        UptimeCheckBuiltinProcessor,
        ObservationSceneBuiltinProcessor,
        CollectBuiltinProcessor,
        CustomEventBuiltinProcessor,
        CustomMetricBuiltinProcessor,
        ApmBuiltinProcessor,
        AlertBuiltinProcessor,
    ]


class BuiltinProcessor(metaclass=abc.ABCMeta):
    view_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "view_configs")

    @classmethod
    def _read_builtin_view_config(cls, filename: str) -> Dict:
        """
        读取内置视图配置文件
        """
        file_path = os.path.join(cls.view_config_path, f"{filename}.json")
        with open(file_path, "r", encoding="utf8") as f:
            return json.loads(f.read())

    @classmethod
    @abc.abstractmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        """
        常见该场景下默认视图
        """

    @classmethod
    def handle_view_list_config(cls, scene_id: str, list_config_item):
        """
        常见该场景下默认视图
        """
        return

    @classmethod
    @abc.abstractmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        """
        常见或更新该场景下的视图
        """

    @classmethod
    @abc.abstractmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> Dict:
        """
        根据视图对象生成视图配置，内置视图可能只会使用其中的部分字段
        """

    @classmethod
    @abc.abstractmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        """
        判断是否是该内置场景
        """

    @classmethod
    def convert_custom_params(cls, scene_id, params):
        """将接口参数转换为视图类需要的参数"""
        return params

    @classmethod
    def is_custom_view_list(cls) -> bool:
        """
        是否需要自定义视图列表返回
        """
        return False

    @classmethod
    def list_view_list(cls, scene_id, views: List[SceneViewModel], params):
        """
        返回自定义视图列表 当cls.is_custom_view_list() = True时有效
        """
        return None

    @classmethod
    def is_custom_sort(cls, scene_id) -> bool:
        """
        是否需要自定义视图列表的排序
        """
        return False

    @classmethod
    def sort_view_list(cls, scene_id, order, results):
        """
        返回排序后的视图列表 当cls.is_custom_sort() = True时有效
        """
        return None


class NormalProcessorMixin:

    SCENE_ID = None
    builtin_views: Dict = None

    filenames = []

    @classmethod
    def load_builtin_views(cls):
        cls.builtin_views = {}
        for filename in cls.filenames:
            cls.builtin_views[filename] = cls._read_builtin_view_config(filename)

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        cls.load_builtin_views()

        builtin_view_ids = {v.split("-", 1)[-1] for v in cls.builtin_views if v.startswith(f"{scene_id}-")}
        existed_view_ids: Set[str] = {v.id for v in existed_views}
        create_view_ids = builtin_view_ids - existed_view_ids
        new_views = []
        for view_id in create_view_ids:
            view_config = cls.builtin_views[f"{scene_id}-{view_id}"]
            new_views.append(
                SceneViewModel(
                    bk_biz_id=bk_biz_id,
                    scene_id=scene_id,
                    type=view_type,
                    id=view_id,
                    name=view_config["name"],
                    mode=view_config["mode"],
                    variables=view_config.get("variables", []),
                    panels=view_config.get("panels", []),
                    list=view_config.get("list", []),
                    order=view_config.get("order", []),
                    options=view_config.get("options", {}),
                )
            )
        if new_views:
            SceneViewModel.objects.bulk_create(new_views)

        # 删除多余的视图
        delete_view_ids = existed_view_ids - builtin_view_ids
        if delete_view_ids:
            SceneViewModel.objects.filter(bk_biz_id=bk_biz_id, scene_id=scene_id, id__in=delete_view_ids).delete()

        cls.create_default_order(bk_biz_id, scene_id)

    @classmethod
    def create_default_order(cls, bk_biz_id: int, scene_id: str):
        """创建视图列表顺序"""
        return


def get_view_config(view: SceneViewModel, params: Dict = None) -> Dict:
    """
    获取实际配置
    """
    for generator in get_builtin_processors():
        if not generator.is_builtin_scene(view.scene_id):
            continue

        result = generator.get_view_config(view, generator.convert_custom_params(view.scene_id, params))

        return result

    raise TypeError("not scene processor")


def list_processors_view(scene_id: str, views: List[SceneViewModel], params: dict):

    for generator in get_builtin_processors():
        if generator.is_builtin_scene(scene_id) and generator.is_custom_view_list():
            return generator.list_view_list(scene_id, views, params)

    return None


def get_scene_processors(scene_id):
    for generator in get_builtin_processors():
        if generator.is_builtin_scene(scene_id):
            return generator


def create_default_views(bk_biz_id: int, scene_id: str, view_type: str, existed_views):
    """
    创建默认视图
    """
    for generator in get_builtin_processors():
        if not generator.is_builtin_scene(scene_id):
            continue
        generator.create_default_views(bk_biz_id, scene_id, view_type, existed_views)
        return

    raise TypeError("not scene processor")


def post_handle_view_list_config(scene_id, config_list):
    """
    视图配置列表后置处理(如添加params参数等)
    """
    for generator in get_builtin_processors():
        if not generator.is_builtin_scene(scene_id):
            continue

        for item in config_list:
            generator.handle_view_list_config(scene_id, item)
        return

    raise TypeError("not scene processor")


def create_or_update_view(
    bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
) -> Optional[SceneViewModel]:
    """
    创建或更新视图
    """
    for generator in get_builtin_processors():
        if not generator.is_builtin_scene(scene_id):
            continue
        return generator.create_or_update_view(bk_biz_id, scene_id, view_type, view_id, view_config)

    raise TypeError("not scene processor")


def is_builtin_scene(scene_id: str) -> bool:
    """
    是否是内置场景
    """
    for generator in get_builtin_processors():
        if generator.is_builtin_scene(scene_id):
            return True
    return False


def get_builtin_scene_processor(view: SceneViewModel) -> BuiltinProcessor:
    """
    获取指定的内置场景处理器
    """
    for generator in get_builtin_processors():
        if not generator.is_builtin_scene(view.scene_id):
            continue
        return generator

    raise TypeError("not scene processor")
