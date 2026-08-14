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
#   - 实例创建方法返回未解析的 FwResource（仅 type + id），
#     框架自动通过 ResourceResolver 补全 name / ancestor_chain
#   - 已移除：ResourceMeta / parent_resource / system_id / selection_mode /
#     related_instance_selections / _all_resources / get_resource_by_id
#     （元数据查询统一走 get_framework().schema，父资源走 rt_def.ancestor）
#   - 切换到 V4 后：ResourceEnum 成员直接作为 ResourceTypeDef 使用
# ---------------------------------------------------------------------------

from __future__ import annotations

from bkmonitor.iam.definitions.resource_types import ResourceTypes as _NewResourceTypes
from bkmonitor.iam.iam_engine.core.types import ResourceInstance


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
        return ResourceInstance(type=cls.id, id=str(item.get("application_id", "")))


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
        return ResourceInstance(type=cls.id, id=str(item.get("application_id", "")))


# ============================================================================
# ResourceEnum
# ============================================================================


class ResourceEnum:
    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication
