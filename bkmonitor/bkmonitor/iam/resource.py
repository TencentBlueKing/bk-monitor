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

import abc
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy
from iam import Resource

from bk_dataview.api import get_org_by_id
from bk_dataview.models import Dashboard
from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from bkmonitor.utils.cache import lru_cache_with_ttl
from core.errors.iam import ResourceNotExistError


class ResourceMeta(metaclass=abc.ABCMeta):
    """
    资源定义
    """

    system_id: str = ""
    id: str = ""
    name: str = ""
    selection_mode: str = ""
    related_instance_selections: List = ""

    @classmethod
    def to_json(cls):
        return {
            "system_id": cls.system_id,
            "id": cls.id,
            "selection_mode": cls.selection_mode,
            "related_instance_selections": cls.related_instance_selections,
        }

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return Resource(cls.system_id, cls.id, str(instance_id), attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建资源实例（带实例名称）可由子类重载
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return cls.create_simple_instance(instance_id, attribute)


class Business(ResourceMeta):
    """
    CMDB业务
    """

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "space"
    name = _lazy("空间")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "space_list"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """

        # 注意，此处 instance_id 有可能是 bk_biz_id，或者是space_uid，需要做统一转换
        try:
            bk_biz_id = int(instance_id)
        except Exception:  # pylint: disable=broad-except
            bk_biz_id = None

        try:
            if bk_biz_id is None:
                space = space_api.SpaceApi.get_space_detail(space_uid=instance_id)
            else:
                space = space_api.SpaceApi.get_space_detail(space_uid=bk_biz_id_to_space_uid(bk_biz_id))
            bk_biz_id = str(space_uid_to_bk_biz_id(space_uid=space.space_uid, id=space.id))
            space_name = f"[{space.space_type_id}] {space.space_name}"
        except Exception:  # pylint: disable=broad-except:
            bk_biz_id = str(instance_id)
            space_name = instance_id

        attribute = attribute or {}
        attribute.update({"id": bk_biz_id, "name": space_name})
        return Resource(cls.system_id, cls.id, bk_biz_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = cls.create_simple_instance(instance_id, attribute)
        return resource


class ApmApplication(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "apm_application"
    name = _lazy("APM应用")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "apm_application_list_v2"}]

    @classmethod
    def create_instance_by_info(cls, item: dict) -> Resource:
        instance_id = item["application_id"]
        bk_biz_id = str(item["bk_biz_id"])
        resource = super().create_simple_instance(
            instance_id=instance_id,
            attribute={
                "id": instance_id,
                "name": item["app_name"],
                "bk_biz_id": bk_biz_id,
                "_bk_iam_path_": f"/{Business.id},{bk_biz_id}/",
            },
        )
        return resource

    @classmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 60, decision_to_drop_func=lambda v: v is None)
    def _get_app_simple_info_by_id_or_none(cls, application_id: str) -> Optional[Dict[str, Any]]:
        """获取应用概要信息，不存在则返回 None。
        应用概要信息不会修改，此处给 60 min 的内存缓存，以提高整体鉴权性能。
        :param application_id: 应用 ID
        :return:
        """
        from apm_web.models import Application

        return (
            Application.objects.filter(application_id=application_id)
            .values("application_id", "app_name", "bk_biz_id")
            .first()
        )

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = super().create_simple_instance(instance_id, attribute)
        app_simple_info: Optional[Dict[str, Any]] = cls._get_app_simple_info_by_id_or_none(instance_id)
        if app_simple_info is None:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": app_simple_info["app_name"],
            "bk_biz_id": str(app_simple_info["bk_biz_id"]),
            "_bk_iam_path_": "/{},{}/".format(Business.id, app_simple_info["bk_biz_id"]),
        }
        return resource


class GrafanaDashboard(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "grafana_dashboard"
    name = _lazy("Grafana仪表盘")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "grafana_dashboard_list"}]

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = super().create_simple_instance(instance_id, attribute)
        dashboard = Dashboard.objects.filter(uid=instance_id).only("uid", "title", "org_id").first()
        if not dashboard:
            return resource

        org = get_org_by_id(dashboard.org_id)
        if not org:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": dashboard.title,
            "bk_biz_id": org["name"],
            "_bk_iam_path_": "/{},{}/".format(Business.id, org["name"]),
        }
        return resource


class ResourceEnum:
    """
    资源类型枚举
    """

    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard


_all_resources = {resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")}


def get_resource_by_id(resource_id: str) -> ResourceMeta:
    """
    根据资源ID获取资源
    """
    if resource_id not in _all_resources:
        raise ResourceNotExistError({"resource_id": resource_id})

    return _all_resources[resource_id]
