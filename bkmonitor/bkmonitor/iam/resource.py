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
# 改造说明:
#   - ResourceEnum 成员是轻量包装类，元数据从 ResourceTypeDef 自动派生
#   - 实例创建逻辑（DB 查询、iam.Resource 构造）集中在 V3InstanceResolver
#   - batch_get_display_names / batch_get_parent 已移除（唯一调用方 kernel_api 将自行实现）
#   - 新增 action.py 只需在 definitions/resource_types.py 添加 ResourceTypeDef
#   - 切换到 V4 后：ResourceEnum 成员直接作为 ResourceTypeDef 使用，
#     不再需要 create_instance（V4 用框架 ResourceInstance）
#
# V3 兼容路径：
#   ResourceEnum.BUSINESS.create_instance(3) → V3InstanceResolver → iam.Resource
#   ResourceEnum.BUSINESS.id → "space"（与 ResourceTypeDef 一致）
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any

from django.conf import settings
from iam import Resource

from bk_dataview.api import get_org_by_id
from bk_dataview.models import Dashboard
from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from bkmonitor.iam.definitions.resource_types import ResourceTypes as _NewResourceTypes
from bkmonitor.utils.cache import lru_cache_with_ttl
from core.errors.iam import ResourceNotExistError


# ============================================================================
# V3InstanceResolver — V3 资源实例创建逻辑（查 DB → iam.Resource）
#
# 切换到 V4 后，此类不再需要。V4 使用框架 ResourceInstance，
# 资源属性通过 definitions/v4_callbacks.py 的 fetch_instance_info 回调获取。
# ============================================================================


class V3InstanceResolver:
    """V3 IAM SDK Resource 实例解析器。

    集中管理 4 种资源类型的实例创建逻辑：
    Business — space_uid / bk_biz_id 统一转换 + SpaceApi 查询
    ApmApplication — Application 表查询 app_name / bk_biz_id
    GrafanaDashboard — Dashboard + Org 表查询
    RumApplication — Application 表查询（同 APM 模式）
    """

    # ================================================================
    # Business（空间）
    # ================================================================

    @staticmethod
    def create_business_instance(instance_id: str, attribute=None) -> Resource:
        """创建空间资源实例。instance_id 可能是 bk_biz_id 或 space_uid。"""
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
        except Exception:  # pylint: disable=broad-except
            bk_biz_id = str(instance_id)
            space_name = instance_id

        attribute = attribute or {}
        attribute.update({"id": bk_biz_id, "name": space_name})
        return Resource(settings.BK_IAM_SYSTEM_ID, _NewResourceTypes.SPACE.id, bk_biz_id, attribute)

    # ================================================================
    # ApmApplication
    # ================================================================

    @staticmethod
    def create_apm_instance(instance_id: str, attribute=None) -> Resource:
        """创建 APM 应用资源实例。从 Application 表查询名称和 bk_biz_id。"""
        resource = Resource(
            settings.BK_IAM_SYSTEM_ID, _NewResourceTypes.APM_APPLICATION.id, str(instance_id), attribute
        )
        app_info = V3InstanceResolver._get_apm_app_info(instance_id)
        if app_info is None:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": app_info["app_name"],
            "bk_biz_id": str(app_info["bk_biz_id"]),
            "_bk_iam_path_": "/{},{}/".format("space", app_info["bk_biz_id"]),
        }
        return resource

    @staticmethod
    def create_apm_instance_by_info(item: dict) -> Resource:
        """从 item dict 创建 APM 应用资源实例（含 _bk_iam_path_）。"""
        instance_id = item["application_id"]
        bk_biz_id = str(item["bk_biz_id"])
        return Resource(
            settings.BK_IAM_SYSTEM_ID,
            _NewResourceTypes.APM_APPLICATION.id,
            instance_id,
            attribute={
                "id": instance_id,
                "name": item["app_name"],
                "bk_biz_id": bk_biz_id,
                "_bk_iam_path_": f"/space,{bk_biz_id}/",
            },
        )

    @staticmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 60, decision_to_drop_func=lambda v: v is None)
    def _get_apm_app_info(application_id: str) -> dict[str, Any] | None:
        from apm_web.models import Application

        return (
            Application.objects.filter(application_id=application_id)
            .values("application_id", "app_name", "bk_biz_id")
            .first()
        )

    # ================================================================
    # GrafanaDashboard
    # ================================================================

    @staticmethod
    def create_grafana_instance(instance_id: str, attribute=None) -> Resource:
        """创建 Grafana 仪表盘资源实例。从 Dashboard + Org 表查询。"""
        resource = Resource(
            settings.BK_IAM_SYSTEM_ID, _NewResourceTypes.GRAFANA_DASHBOARD.id, str(instance_id), attribute
        )
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
            "_bk_iam_path_": "/{},{}/".format("space", org["name"]),
        }
        return resource

    # ================================================================
    # RumApplication
    # ================================================================

    @staticmethod
    def create_rum_instance(instance_id: str, attribute=None) -> Resource:
        """创建 RUM 应用资源实例。从 rum_web.models.Application 表查询。"""
        resource = Resource(
            settings.BK_IAM_SYSTEM_ID, _NewResourceTypes.RUM_APPLICATION.id, str(instance_id), attribute
        )
        app_info = V3InstanceResolver._get_rum_app_info(instance_id)
        if app_info is None:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": app_info["app_name"],
            "bk_biz_id": str(app_info["bk_biz_id"]),
            "_bk_iam_path_": "/{},{}/".format("space", app_info["bk_biz_id"]),
        }
        return resource

    @staticmethod
    def create_rum_instance_by_info(item: dict) -> Resource:
        """从 item dict 创建 RUM 应用资源实例。"""
        instance_id = item["application_id"]
        bk_biz_id = str(item["bk_biz_id"])
        return Resource(
            settings.BK_IAM_SYSTEM_ID,
            _NewResourceTypes.RUM_APPLICATION.id,
            instance_id,
            attribute={
                "id": instance_id,
                "name": item["app_name"],
                "bk_biz_id": bk_biz_id,
                "_bk_iam_path_": f"/space,{bk_biz_id}/",
            },
        )

    @staticmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 60, decision_to_drop_func=lambda v: v is None)
    def _get_rum_app_info(application_id: str) -> dict[str, Any] | None:
        from rum_web.models.application import Application

        return (
            Application.objects.filter(application_id=application_id)
            .values("application_id", "app_name", "bk_biz_id")
            .first()
        )


# ============================================================================
# 资源类型包装类 — 复用辅助函数
# ============================================================================


def _v3_meta(rt_def):
    """从 ResourceTypeDef 提取 V3 元数据 dict。"""
    return rt_def.extensions.get("v3", {})


def _resolve_parent(ancestor: str):
    """将 ancestor 字符串解析为父资源类引用。返回 None 表示顶级资源。"""
    if not ancestor:
        return None
    # 延迟解析：在 ResourceEnum 全部创建后通过 _resolve_parent_refs() 完成
    return ancestor  # 先存字符串，后面再替换


# ============================================================================
# ResourceMeta — 最小基类（保留为 drf.py / upgrade.py 类型注解兼容，Step 5 后可删除）
# ============================================================================


class ResourceMeta:
    """[DEPRECATED] 旧资源类型基类。保留仅为 drf.py / upgrade.py 类型注解兼容。
    元数据已从 ResourceTypeDef 派生，实例创建已委托 V3InstanceResolver。
    Step 5 (drf.py) / 清理 upgrade.py 后可删除。
    """

    pass


# ============================================================================
# 资源类型类（4 个）— 元数据自动派生，实例创建委托 V3InstanceResolver
# ============================================================================


class Business(ResourceMeta):
    """空间资源 — 顶级资源，元数据从 ResourceTypes.SPACE 派生。"""

    _rt_def = _NewResourceTypes.SPACE
    _v3 = _rt_def.extensions.get("v3", {})

    system_id = settings.BK_IAM_SYSTEM_ID
    id = _rt_def.id
    name = _rt_def.name
    selection_mode = _v3.get("selection_mode", "")
    related_instance_selections = _v3.get("related_instance_selections", [])

    parent_resource = None

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        return V3InstanceResolver.create_business_instance(instance_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.create_simple_instance(instance_id, attribute)


class ApmApplication(ResourceMeta):
    """APM 应用资源 — 父资源 Business，元数据从 ResourceTypes.APM_APPLICATION 派生。"""

    _rt_def = _NewResourceTypes.APM_APPLICATION
    _v3 = _rt_def.extensions.get("v3", {})

    system_id = settings.BK_IAM_SYSTEM_ID
    id = _rt_def.id
    name = _rt_def.name
    selection_mode = _v3.get("selection_mode", "")
    related_instance_selections = _v3.get("related_instance_selections", [])

    parent_resource = None  # 由 _resolve_parent_refs 在模块末尾设置

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        return V3InstanceResolver.create_apm_instance(instance_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> Resource:
        return V3InstanceResolver.create_apm_instance_by_info(item)


class GrafanaDashboard(ResourceMeta):
    """Grafana 仪表盘资源 — 父资源 Business，元数据从 ResourceTypes.GRAFANA_DASHBOARD 派生。"""

    _rt_def = _NewResourceTypes.GRAFANA_DASHBOARD
    _v3 = _rt_def.extensions.get("v3", {})

    system_id = settings.BK_IAM_SYSTEM_ID
    id = _rt_def.id
    name = _rt_def.name
    selection_mode = _v3.get("selection_mode", "")
    related_instance_selections = _v3.get("related_instance_selections", [])

    parent_resource = None  # 由 _resolve_parent_refs 设置

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        return V3InstanceResolver.create_grafana_instance(instance_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.create_simple_instance(instance_id, attribute)


class RumApplication(ResourceMeta):
    """RUM 应用资源 — 父资源 Business，元数据从 ResourceTypes.RUM_APPLICATION 派生。"""

    _rt_def = _NewResourceTypes.RUM_APPLICATION
    _v3 = _rt_def.extensions.get("v3", {})

    system_id = settings.BK_IAM_SYSTEM_ID
    id = _rt_def.id
    name = _rt_def.name
    selection_mode = _v3.get("selection_mode", "")
    related_instance_selections = _v3.get("related_instance_selections", [])

    parent_resource = None  # 由 _resolve_parent_refs 设置

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        return V3InstanceResolver.create_rum_instance(instance_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> Resource:
        return V3InstanceResolver.create_rum_instance_by_info(item)


# ============================================================================
# 延迟解析 ancestor → parent_resource 引用
# ============================================================================

_RESOURCE_BY_ID: dict[str, type] = {
    _NewResourceTypes.SPACE.id: Business,
    _NewResourceTypes.APM_APPLICATION.id: ApmApplication,
    _NewResourceTypes.GRAFANA_DASHBOARD.id: GrafanaDashboard,
    _NewResourceTypes.RUM_APPLICATION.id: RumApplication,
}

# 根据 ResourceTypeDef.ancestor 设置 parent_resource
for _rt_def in [
    _NewResourceTypes.SPACE,
    _NewResourceTypes.APM_APPLICATION,
    _NewResourceTypes.GRAFANA_DASHBOARD,
    _NewResourceTypes.RUM_APPLICATION,
]:
    _cls = _RESOURCE_BY_ID.get(_rt_def.id)
    if _cls is None:
        continue
    _ancestor_id = _rt_def.ancestor
    _cls.parent_resource = _RESOURCE_BY_ID.get(_ancestor_id) if _ancestor_id else None


# ============================================================================
# ResourceEnum — 资源类型枚举
# ============================================================================


class ResourceEnum:
    """资源类型枚举。成员是轻量包装类，元数据从 definitions/resource_types.py 派生。

    V3: ResourceEnum.BUSINESS.create_instance(biz_id) → iam.Resource
    V4: 直接使用 ResourceTypeDef，实例创建走框架 ResourceInstance
    """

    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication


# ============================================================================
# _all_resources / get_resource_by_id — 向后兼容
# ============================================================================

_all_resources: dict[str, type] = {
    resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")
}


def get_resource_by_id(resource_id: str):
    """根据资源 ID 获取资源类型类。"""
    if resource_id not in _all_resources:
        raise ResourceNotExistError({"resource_id": resource_id})

    return _all_resources[resource_id]
