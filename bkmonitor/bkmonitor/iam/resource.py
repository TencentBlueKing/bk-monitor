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
from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy
from iam import Resource
from core.errors.iam import ResourceNotExistError
from iam_engine.provider.requests import ResourceInstance


def to_resource_instance(resource) -> ResourceInstance:
    """Convert the V3 product SDK input at one boundary, retaining local metadata."""
    if isinstance(resource, ResourceInstance):
        return resource
    from bkmonitor.iam.handlers.resolver import _chain_from_iam_path

    attributes = dict(getattr(resource, "attribute", {}) or {})
    return ResourceInstance(
        type=resource.type,
        id=str(resource.id),
        system=getattr(resource, "system", ""),
        name=attributes.get("name", ""),
        ancestor_chain=_chain_from_iam_path(attributes.get("_bk_iam_path_", "")),
        attributes=attributes,
    )



class ResourceMeta(metaclass=abc.ABCMeta):
    """
    资源定义
    """

    # === IAM 资源元数据声明 ===
    system_id: str = ""
    id: str = ""
    name: str = ""
    selection_mode: str = ""
    related_instance_selections: list = ""

    # === 资源拓扑关系 ===
    # 父资源类型；顶级资源为 None。
    parent_resource: type["ResourceMeta"] | None = None

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

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {instance_id: parent_instance_id}。

        注意：
          - “是否有父资源”这一模型层信息，请通过 `parent_resource` 类属性判断，
            不要用“本方法是否返回空”来隐式判断。
          - 顶级资源（parent_resource is None）不应重写本方法，保持默认返回 {}。
          - 非顶级资源子类应重写本方法，返回本实例到父实例 id 的批量映射。
        """
        return {}

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {instance_id: display_name}。子类重写。"""
        return {}


class Business(ResourceMeta):
    """
    CMDB业务
    """
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "space"
    name = _lazy("空间")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "space_list"}]
    parent_resource = None
    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None):
        from monitor_web.iam.views import SpaceProvider
        return SpaceProvider.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None):
        from monitor_web.iam.views import SpaceProvider
        return SpaceProvider.create_instance(instance_id, attribute)

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]):
        from monitor_web.iam.views import SpaceProvider
        return SpaceProvider.batch_get_display_names(instance_ids)



class ApmApplication(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "apm_application"
    name = _lazy("APM应用")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "apm_application_list_v2"}]
    parent_resource = Business
    @classmethod
    def create_instance_by_info(cls, item: dict):
        from monitor_web.iam.views import ApmApplicationProvider
        return ApmApplicationProvider.create_instance_by_info(item)

    @classmethod
    def _get_app_simple_info_by_id_or_none(cls, application_id: str):
        from monitor_web.iam.views import ApmApplicationProvider
        return ApmApplicationProvider._get_app_simple_info_by_id_or_none(application_id)

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None):
        from monitor_web.iam.views import ApmApplicationProvider
        return ApmApplicationProvider.create_simple_instance(instance_id, attribute)

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]):
        from monitor_web.iam.views import ApmApplicationProvider
        return ApmApplicationProvider.batch_get_display_names(instance_ids)

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]):
        from monitor_web.iam.views import ApmApplicationProvider
        return ApmApplicationProvider.batch_get_parent(instance_ids)



class GrafanaDashboard(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "grafana_dashboard"
    name = _lazy("Grafana仪表盘")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "grafana_dashboard_list"}]
    parent_resource = Business
    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None):
        from monitor_web.iam.views import GrafanaDashboardProvider
        return GrafanaDashboardProvider.create_simple_instance(instance_id, attribute)

    GENERAL_FOLDER_NAME = "General"
    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]):
        from monitor_web.iam.views import GrafanaDashboardProvider
        return GrafanaDashboardProvider.batch_get_display_names(instance_ids)

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]):
        from monitor_web.iam.views import GrafanaDashboardProvider
        return GrafanaDashboardProvider.batch_get_parent(instance_ids)



class RumApplication(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "rum_application"
    name = _lazy("RUM应用")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "rum_application_list_v2"}]
    parent_resource = Business
    @classmethod
    def create_instance_by_info(cls, item: dict):
        from monitor_web.iam.views import RumApplicationProvider
        return RumApplicationProvider.create_instance_by_info(item)

    @classmethod
    def _get_app_simple_info_by_id_or_none(cls, application_id: str):
        from monitor_web.iam.views import RumApplicationProvider
        return RumApplicationProvider._get_app_simple_info_by_id_or_none(application_id)

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None):
        from monitor_web.iam.views import RumApplicationProvider
        return RumApplicationProvider.create_simple_instance(instance_id, attribute)

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]):
        from monitor_web.iam.views import RumApplicationProvider
        return RumApplicationProvider.batch_get_display_names(instance_ids)

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]):
        from monitor_web.iam.views import RumApplicationProvider
        return RumApplicationProvider.batch_get_parent(instance_ids)



class ResourceEnum:
    """
    资源类型枚举
    """

    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication


_all_resources = {resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")}


def get_resource_by_id(resource_id: str) -> ResourceMeta:
    """
    根据资源ID获取资源
    """
    if resource_id not in _all_resources:
        raise ResourceNotExistError({"resource_id": resource_id})

    return _all_resources[resource_id]
