"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# resource.py — ResourceEnum 定义（元数据从 definitions/resource_types.py 派生）
#
# 改造说明 (2026-08, Step 4+6):
#   - ResourceEnum 成员是轻量包装类，元数据从 ResourceTypeDef 自动派生
#   - 实例创建方法返回未解析的 FwResource（仅 type + id），
#     框架自动通过 ResourceResolver 补全 name / ancestor_chain
#   - V3InstanceResolver / batch_get_display_names / batch_get_parent 已移除
#   - 切换到 V4 后：ResourceEnum 成员直接作为 ResourceTypeDef 使用
# ---------------------------------------------------------------------------

from __future__ import annotations

from django.conf import settings

from bkmonitor.iam.definitions.resource_types import ResourceTypes as _NewResourceTypes
from bkmonitor.iam.iam_engine.core.types import ResourceInstance
from core.errors.iam import ResourceNotExistError


# ============================================================================
# ResourceMeta — 最小基类（保留仅为 drf.py / upgrade.py 类型注解兼容）
# ============================================================================


class ResourceMeta:
    """[DEPRECATED] 旧资源类型基类。drf.py/upgrade.py 类型注解兼容。Step 5 后可删除。"""

    pass


# ============================================================================
# 资源类型类（4 个）— 元数据从 ResourceTypeDef 派生，实例返回 FwResource
# ============================================================================


class Business(ResourceMeta):
    """空间资源 — 顶级资源。"""

    _rt_def = _NewResourceTypes.SPACE
    _v3 = _rt_def.extensions.get("v3", {})
    system_id: str = settings.BK_IAM_SYSTEM_ID
    id: str = _rt_def.id
    name: str = _rt_def.name
    selection_mode: str = _v3.get("selection_mode", "")
    related_instance_selections: list = _v3.get("related_instance_selections", [])
    parent_resource: type[ResourceMeta] | None = None

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)


class ApmApplication(ResourceMeta):
    """APM 应用资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.APM_APPLICATION
    _v3 = _rt_def.extensions.get("v3", {})
    system_id: str = settings.BK_IAM_SYSTEM_ID
    id: str = _rt_def.id
    name: str = _rt_def.name
    selection_mode: str = _v3.get("selection_mode", "")
    related_instance_selections: list = _v3.get("related_instance_selections", [])
    parent_resource: type[ResourceMeta] | None = None  # 模块末尾 _resolve_parent_refs 设置

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(item.get("application_id", "")))


class GrafanaDashboard(ResourceMeta):
    """Grafana 仪表盘资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.GRAFANA_DASHBOARD
    _v3 = _rt_def.extensions.get("v3", {})
    system_id: str = settings.BK_IAM_SYSTEM_ID
    id: str = _rt_def.id
    name: str = _rt_def.name
    selection_mode: str = _v3.get("selection_mode", "")
    related_instance_selections: list = _v3.get("related_instance_selections", [])
    parent_resource: type[ResourceMeta] | None = None

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)


class RumApplication(ResourceMeta):
    """RUM 应用资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.RUM_APPLICATION
    _v3 = _rt_def.extensions.get("v3", {})
    system_id: str = settings.BK_IAM_SYSTEM_ID
    id: str = _rt_def.id
    name: str = _rt_def.name
    selection_mode: str = _v3.get("selection_mode", "")
    related_instance_selections: list = _v3.get("related_instance_selections", [])
    parent_resource: type[ResourceMeta] | None = None

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(item.get("application_id", "")))


# ============================================================================
# 延迟解析 ancestor → parent_resource
# ============================================================================

_RESOURCE_BY_ID: dict[str, type] = {
    _NewResourceTypes.SPACE.id: Business,
    _NewResourceTypes.APM_APPLICATION.id: ApmApplication,
    _NewResourceTypes.GRAFANA_DASHBOARD.id: GrafanaDashboard,
    _NewResourceTypes.RUM_APPLICATION.id: RumApplication,
}

for _rt_def in (
    _NewResourceTypes.SPACE,
    _NewResourceTypes.APM_APPLICATION,
    _NewResourceTypes.GRAFANA_DASHBOARD,
    _NewResourceTypes.RUM_APPLICATION,
):
    _cls = _RESOURCE_BY_ID.get(_rt_def.id)
    if _cls is not None and _rt_def.ancestor:
        _cls.parent_resource = _RESOURCE_BY_ID.get(_rt_def.ancestor)


# ============================================================================
# ResourceEnum
# ============================================================================


class ResourceEnum:
    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication


# ============================================================================
# _all_resources / get_resource_by_id — 向后兼容
# ============================================================================

_all_resources: dict[str, type] = {r.id: r for r in ResourceEnum.__dict__.values() if hasattr(r, "id")}


def get_resource_by_id(resource_id: str):
    if resource_id not in _all_resources:
        raise ResourceNotExistError({"resource_id": resource_id})
    return _all_resources[resource_id]
