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
#   - 简单实例由 ResourceResolver 补全；列表已有元数据时保留 name / ancestor_chain，
#     沿用 V3 的 instance_create_func 扩展点，避免冗余查询
#   - 已移除：ResourceMeta / parent_resource / system_id / selection_mode /
#     related_instance_selections / _all_resources / get_resource_by_id
#     （元数据查询统一走 get_schema()，父资源走 rt_def.ancestor）
#   - 切换到 V4 后：ResourceEnum 成员直接作为 ResourceTypeDef 使用
# ---------------------------------------------------------------------------

from __future__ import annotations

from bkmonitor.iam.definitions.resource_types import ResourceTypes as _NewResourceTypes
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


# ============================================================================
# 资源类型类（4 个）— 元数据从 ResourceTypeDef 派生，实例返回 FwResource
# ============================================================================


class Business:
    """空间资源 — 顶级资源。"""

    _rt_def = _NewResourceTypes.SPACE
    id: str = _rt_def.id
    name: str = _rt_def.name

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)


class ApmApplication:
    """APM 应用资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.APM_APPLICATION
    id: str = _rt_def.id
    name: str = _rt_def.name

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> ResourceInstance:
        return ResourceInstance(
            type=cls.id,
            id=str(item["application_id"]),
            name=item["app_name"],
            ancestor_chain=(ResourceInstance(type=Business.id, id=str(item["bk_biz_id"])),),
            attributes={"id": item["application_id"], "name": item["app_name"], "bk_biz_id": str(item["bk_biz_id"])},
        )


class GrafanaDashboard:
    """Grafana 仪表盘资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.GRAFANA_DASHBOARD
    id: str = _rt_def.id
    name: str = _rt_def.name

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)


class RumApplication:
    """RUM 应用资源 — 父资源 Business。"""

    _rt_def = _NewResourceTypes.RUM_APPLICATION
    id: str = _rt_def.id
    name: str = _rt_def.name

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return ResourceInstance(type=cls.id, id=str(instance_id))

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> ResourceInstance:
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def create_instance_by_info(cls, item: dict) -> ResourceInstance:
        return ResourceInstance(
            type=cls.id,
            id=str(item["application_id"]),
            name=item["app_name"],
            ancestor_chain=(ResourceInstance(type=Business.id, id=str(item["bk_biz_id"])),),
            attributes={"id": item["application_id"], "name": item["app_name"], "bk_biz_id": str(item["bk_biz_id"])},
        )


# ============================================================================
# ResourceEnum
# ============================================================================


class ResourceEnum:
    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication
