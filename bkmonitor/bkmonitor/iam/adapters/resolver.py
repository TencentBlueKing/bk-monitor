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
# MonitorResourceResolver — 监控平台资源实例补全器
#
# 纯业务逻辑（与 provider 方言 v3/v4 无关，两者共用）：
#   - Business: space_uid → bk_biz_id 转换 + SpaceApi 查询名称
#   - ApmApplication / GrafanaDashboard / RumApplication：经资源目录
#     adapters/catalog.py 查询名称与祖先链（与平台回调、权限树同一份实现）
#
# 由框架基类从 IAM_FRAMEWORK.PROVIDERS[*].options.resolver_class 加载，
# 在 is_allowed / batch_by_* / get_apply_data 等鉴权路径统一调用。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
from typing import Any


from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid

from ..iam_engine.core.types import ResourceInstance, to_resource_type_id
from ..iam_engine.provider.resolver import ResourceResolver
from ..definitions.resource_types import ResourceTypes
from bkmonitor.utils.cache import lru_cache_with_ttl

from . import catalog

logger = logging.getLogger(__name__)


def _normalize_app_info(instance_id: str, items: list[dict]) -> dict[str, Any] | None:
    """把 catalog 返回的应用概要条目规范化为 {"application_id", "app_name", "bk_biz_id"}。

    查不到实例或缺少父链信息时返回 None（与旧版 DB 查询的"未命中"语义一致）。
    """
    if not items:
        return None
    item = items[0]
    path = catalog.parse_iam_path(item.get("_bk_iam_path_", ""))
    if not path:
        return None
    return {
        "application_id": str(item.get("id", instance_id)),
        "app_name": item.get("name", "") or item.get("display_name", ""),
        "bk_biz_id": int(path[0]["id"]),
    }


def _chain_from_iam_path(path: str) -> tuple[ResourceInstance, ...]:
    """把 _bk_iam_path_ 解析为 ResourceInstance 祖先链。"""
    return tuple(ResourceInstance(type=seg["type"], id=seg["id"]) for seg in catalog.parse_iam_path(path or ""))


class MonitorResourceResolver(ResourceResolver):
    """监控平台资源实例补全器（v3/v4 通用）。

    根据 type + id 查询 DB，补全 name / ancestor_chain。
    配置方式：
        IAM_FRAMEWORK.PROVIDERS[*].options.resolver_class =
            "bkmonitor.iam.adapters.resolver.MonitorResourceResolver"
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
        """补全 APM 应用实例的名称和祖先链（经资源目录 catalog 查询）。"""
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
        """获取 APM 应用概要信息（经 catalog 批量查询，60min 内存缓存）。

        返回 {"application_id", "app_name", "bk_biz_id"} 或 None。
        """
        items = catalog.fetch_instance_info(
            ResourceTypes.APM_APPLICATION.id, [application_id], requires=["name", "_bk_iam_path_"]
        )
        return _normalize_app_info(application_id, items)

    # ================================================================
    # GrafanaDashboard
    # ================================================================

    def _resolve_grafana(self, resource: ResourceInstance) -> ResourceInstance:
        """补全 Grafana 仪表盘/目录实例的名称和祖先链（经资源目录 catalog 查询）。

        支持三种实例 ID 格式（与 catalog / 平台回调约定一致）：
          * "folder:{org_id}|{folder_id}"   —— 目录
          * "{org_id}|{uid}" / "{uid}"      —— 仪表盘
        """
        items = catalog.fetch_instance_info(
            ResourceTypes.GRAFANA_DASHBOARD.id, [resource.id], requires=["display_name", "_bk_iam_path_"]
        )
        if not items:
            return resource
        item = items[0]
        return ResourceInstance(
            type=resource.type,
            id=resource.id,
            name=item.get("display_name", ""),
            ancestor_chain=_chain_from_iam_path(item.get("_bk_iam_path_", "")),
        )

    # ================================================================
    # RumApplication
    # ================================================================

    def _resolve_rum(self, resource: ResourceInstance) -> ResourceInstance:
        """补全 RUM 应用实例的名称和祖先链（经资源目录 catalog 查询）。"""
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
        """获取 RUM 应用概要信息（经 catalog 批量查询，60min 内存缓存）。

        返回 {"application_id", "app_name", "bk_biz_id"} 或 None。
        """
        items = catalog.fetch_instance_info(
            ResourceTypes.RUM_APPLICATION.id, [application_id], requires=["name", "_bk_iam_path_"]
        )
        return _normalize_app_info(application_id, items)
