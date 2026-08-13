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
# V3ResourceResolver — V3 资源实例补全器（DB 查询版）
#
# 吸收原 resource.py V3InstanceResolver 的 DB 查询逻辑：
#   - Business: space_uid → bk_biz_id 转换 + SpaceApi 查询名称
#   - ApmApplication: Application 表查询 app_name / bk_biz_id → ancestor_chain
#   - GrafanaDashboard: Dashboard + Org 表查询 → ancestor_chain
#   - RumApplication: rum_web.models.Application 查询 → ancestor_chain
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any


from bk_dataview.api import get_org_by_id
from bk_dataview.models import Dashboard
from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid

from ...iam_engine.core.types import ResourceInstance, to_resource_type_id
from ...iam_engine.provider.resolver import ResourceResolver
from ...definitions.resource_types import ResourceTypes
from bkmonitor.utils.cache import lru_cache_with_ttl

logger = logging.getLogger(__name__)


class V3ResourceResolver(ResourceResolver):
    """V3 资源实例补全器。

    根据 type + id 查询 DB，补全 name / ancestor_chain。
    配置方式：
        IAM_FRAMEWORK.PROVIDERS[*].options.resolver_class =
            "bkmonitor.iam.adapters.v3.resolver.V3ResourceResolver"
    """

    def resolve(self, resource: ResourceInstance) -> ResourceInstance:
        rt_id = to_resource_type_id(resource.type)
        if rt_id == ResourceTypes.SPACE.id:
            return self._resolve_space(resource)
        if rt_id == ResourceTypes.APM_APPLICATION.id:
            return self._resolve_apm(resource)
        if rt_id == ResourceTypes.GRAFANA_DASHBOARD.id:
            return self._resolve_grafana(resource)
        if rt_id == ResourceTypes.RUM_APPLICATION.id:
            return self._resolve_rum(resource)
        return resource

    # ================================================================
    # Business（空间）
    # ================================================================

    def _resolve_space(self, resource: ResourceInstance) -> ResourceInstance:
        """补全空间实例的名称。"""
        try:
            bk_biz_id = int(resource.id)
        except (TypeError, ValueError):
            bk_biz_id = None

        try:
            if bk_biz_id is None:
                space = space_api.SpaceApi.get_space_detail(space_uid=resource.id)
            else:
                space = space_api.SpaceApi.get_space_detail(space_uid=bk_biz_id_to_space_uid(bk_biz_id))
            space_name = f"[{space.space_type_id}] {space.space_name}"
        except Exception:
            space_name = resource.id

        return ResourceInstance(
            type=resource.type,
            id=resource.id,
            name=space_name,
        )

    # ================================================================
    # ApmApplication
    # ================================================================

    def _resolve_apm(self, resource: ResourceInstance) -> ResourceInstance:
        """补全 APM 应用实例的名称和祖先链。"""
        app_info = self._get_apm_app_info(resource.id)
        if app_info is None:
            return resource
        return ResourceInstance(
            type=resource.type,
            id=resource.id,
            name=app_info["app_name"],
            ancestor_chain=(ResourceInstance(type=ResourceTypes.SPACE.id, id=str(app_info["bk_biz_id"])),),
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

    def _resolve_grafana(self, resource: ResourceInstance) -> ResourceInstance:
        """补全 Grafana 仪表盘实例的名称和祖先链。"""
        dashboard = Dashboard.objects.filter(uid=resource.id).only("uid", "title", "org_id").first()
        if not dashboard:
            return resource
        org = get_org_by_id(dashboard.org_id)
        if not org:
            return resource
        return ResourceInstance(
            type=resource.type,
            id=resource.id,
            name=dashboard.title,
            ancestor_chain=(ResourceInstance(type=ResourceTypes.SPACE.id, id=str(org["name"])),),
        )

    # ================================================================
    # RumApplication
    # ================================================================

    def _resolve_rum(self, resource: ResourceInstance) -> ResourceInstance:
        """补全 RUM 应用实例的名称和祖先链。"""
        app_info = self._get_rum_app_info(resource.id)
        if app_info is None:
            return resource
        return ResourceInstance(
            type=resource.type,
            id=resource.id,
            name=app_info["app_name"],
            ancestor_chain=(ResourceInstance(type=ResourceTypes.SPACE.id, id=str(app_info["bk_biz_id"])),),
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
