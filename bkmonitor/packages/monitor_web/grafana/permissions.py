"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.utils import timezone
from django.conf import settings
from iam.exceptions import AuthAPIError, AuthInvalidParam
from rest_framework import permissions

from bk_dataview.api import get_or_create_org
from bk_dataview.models import Dashboard
from bk_dataview.permissions import BasePermission, GrafanaPermission, GrafanaRole
from bkmonitor.iam import ActionEnum, Permission
from iam_engine.exceptions import ProviderError
from bkmonitor.models.external_iam import ExternalPermission
from bkmonitor.utils.request import get_request_tenant_id

logger = logging.getLogger("monitor_web")


class DashboardPermission(BasePermission):
    """
    仪表盘权限 - 支持 folder 权限展开(直接返回当前folder下所有dashboard)

    实例级可见性统一走框架 filter_visible_resources（provider 中立）：
      * v3：策略表达式 + 本地求值（1 次 API）
      * v4：正向批量鉴权
    """

    # 添加前缀， 便于区分
    FOLDER_PREFIX = "folder:"

    @classmethod
    def _parse_resource_id(cls, org_id: int, resource_id: str) -> tuple[str | None, tuple[int, int] | None]:
        """
        解析资源 ID，区分 folder 和 dashboard

        返回: (dashboard_uid, folder_id_tuple)
        - dashboard_uid: 纯 dashboard uid 字符串，或 None
        - folder_id_tuple: (org_id, folder_id) 元组，或 None
        """
        resource_id = str(resource_id)

        # Folder 格式: "folder:{org_id}|{folder_id}"
        if resource_id.startswith(cls.FOLDER_PREFIX):
            folder_part = resource_id[len(cls.FOLDER_PREFIX) :]
            if "|" in folder_part:
                try:
                    f_org_id_str, folder_id_str = folder_part.split("|", 1)
                    f_org_id = int(f_org_id_str)
                    folder_id = int(folder_id_str)
                    # 只返回当前 org 的 folder
                    if f_org_id == org_id:
                        return None, (f_org_id, folder_id)
                except ValueError:
                    # 资源id无效
                    logger.warning(f"Invalid folder resource ID format: {resource_id}")
            return None, None

        # Dashboard 格式: "{org_id}|{uid}" 或 "{uid}"
        if "|" in resource_id:
            parts = resource_id.split("|", 1)
            # 特判两种特殊情况
            if len(parts) == 2:
                try:
                    d_org_id = int(parts[0])
                    # 只返回当前 org 的 dashboard
                    if d_org_id == org_id:
                        return parts[1], None
                    return None, None
                except ValueError:
                    # org_id 不是数字，可能是纯 uid
                    return resource_id, None
        return resource_id, None

    @classmethod
    def expand_folder_to_dashboards(cls, org_id: int, folder_ids: set[tuple[int, int]]) -> set[str]:
        """
        将 folder 权限展开为其下所有 dashboard 的 uid

        参数:
            org_id: 当前组织 ID
            folder_ids: (org_id, folder_id) 元组集合

        返回:
            dashboard uid 集合
        """
        if not folder_ids:
            return set()

        # 提取当前 org 的 folder_id
        target_folder_ids = {fid for f_org_id, fid in folder_ids if f_org_id == org_id}

        if not target_folder_ids:
            return set()

        # 查询这些 folder 下的所有 dashboard
        dashboards = Dashboard.objects.filter(
            org_id=org_id, folder_id__in=target_folder_ids, is_folder=False
        ).values_list("uid", flat=True)

        return set(dashboards)

    @classmethod
    def expand_resources_to_dashboard_uids(cls, org_id: int, resource_ids: list[str]) -> set[str]:
        """
        将资源列表（包含 dashboard 和 folder）展开为 dashboard uid 集合
        这是一个通用方法，用于统一处理资源展开逻辑

        参数:
            org_id: 当前组织 ID
            resource_ids: 资源 ID 列表，可包含:
                - dashboard: "{org_id}|{uid}" 或 "{uid}"
                - folder: "folder:{org_id}|{folder_id}"

        返回:
            dashboard uid 集合
        """
        dashboard_uids = set()
        folder_ids = set()

        # 分离 dashboard 和 folder 资源
        for resource_id in resource_ids:
            d_uid, f_id = cls._parse_resource_id(org_id, resource_id)
            if d_uid:
                dashboard_uids.add(d_uid)
            if f_id:
                folder_ids.add(f_id)

        # 展开 folder 为 dashboards
        folder_dashboard_uids = cls.expand_folder_to_dashboards(org_id, folder_ids)

        # 合并所有 dashboard uids
        return dashboard_uids | folder_dashboard_uids

    @classmethod
    def get_user_role(cls, username: str, org_name: str, force_check: bool = False) -> GrafanaRole:
        """
        获取仪表盘角色
        """
        if not username:
            message = "username is required"
            if settings.ROLE == "api":
                message += "request header: [X-Bkapi-Authorization] need bk_username field"
            raise AuthInvalidParam(message)

        role = GrafanaRole.Anonymous
        bk_biz_id = int(org_name)
        permission = Permission(username=username, bk_tenant_id=get_request_tenant_id())
        if force_check:
            permission.skip_check = False

        if permission.is_allowed_by_biz(bk_biz_id, ActionEnum.MANAGE_DATASOURCE):
            return GrafanaRole.Admin

        try:
            if permission.is_allowed_by_biz(bk_biz_id, ActionEnum.MANAGE_DASHBOARD):
                role = GrafanaRole.Editor
            elif permission.is_allowed_by_biz(bk_biz_id, ActionEnum.VIEW_DASHBOARD):
                role = GrafanaRole.Viewer
        except (AuthAPIError, ProviderError):
            # AuthAPIError：兼容旧版 SDK；新框架下 v3/v4 provider 已在内部兜底并转抛
            # ProviderError（含 ProviderUnavailable），故此处两者都需要接住。
            pass

        return role

    @classmethod
    def get_visible_dashboards(
        cls,
        username: str,
        org_name: str,
        resource_ids: list[str] | None = None,
        force_check: bool = False,
    ) -> tuple[GrafanaRole, dict[str, GrafanaPermission]]:
        """
        查询用户可见的仪表盘（候选过滤，provider 中立）。

        Args:
            username: 用户名
            org_name: 业务ID（Grafana org 名称）
            resource_ids: IAM 格式资源 id 候选列表：
                - dashboard: "{org_id}|{uid}"
                - folder: "folder:{org_id}|{folder_id}"
                None 时查询当前组织全部仪表盘；空列表只检查全量授权。
                仪表盘所属文件夹由权限服务补齐，调用方不负责构造父资源。

        Returns:
            (role, {uid: GrafanaPermission})
            role 包含实例级全量授权提级；map 中 folder 授权已展开为其下所有 dashboard uid。
        """
        p = Permission(username=username, bk_tenant_id=get_request_tenant_id())
        if force_check:
            p.skip_check = False
        if p.skip_check:
            return GrafanaRole.Admin, {}

        # 实例级查询不混入空间角色；空间角色由 request-aware 入口合并。
        role = GrafanaRole.Anonymous

        org_id = get_or_create_org(org_name)["id"]
        candidate_ids = cls._candidate_ids(org_id, resource_ids)
        view_result = p.filter_visible_resource_ids(
            ActionEnum.VIEW_SINGLE_DASHBOARD, "grafana_dashboard", candidate_ids, bk_biz_id=int(org_name)
        )
        edit_result = p.filter_visible_resource_ids(
            ActionEnum.EDIT_SINGLE_DASHBOARD, "grafana_dashboard", candidate_ids, bk_biz_id=int(org_name)
        )

        # 实例级全量授权 → role 提级
        if edit_result.all_granted:
            role = GrafanaRole.Editor
        elif view_result.all_granted:
            role = GrafanaRole.Viewer

        if role >= GrafanaRole.Editor:
            return role, {}

        # 可见资源 → uid map（folder 展开为 dashboard uid；过滤探针产生的空 id）
        view_uids = cls.expand_resources_to_dashboard_uids(org_id, [rid for rid in view_result.visible_ids if rid])
        edit_uids = cls.expand_resources_to_dashboard_uids(org_id, [rid for rid in edit_result.visible_ids if rid])

        dashboard_permissions: dict[str, GrafanaPermission] = {}
        for uid in view_uids:
            dashboard_permissions[uid] = GrafanaPermission.View
        for uid in edit_uids:
            dashboard_permissions[uid] = GrafanaPermission.Edit

        return role, dashboard_permissions

    @classmethod
    def _candidate_ids(cls, org_id: int, resource_ids: list[str] | None) -> tuple[str, ...]:
        """集中维护本地仪表盘与文件夹覆盖关系，避免业务入口遗漏父资源。"""
        if resource_ids is None:
            records = Dashboard.objects.filter(org_id=org_id).values_list("id", "uid", "is_folder")
            ids = {
                f"{cls.FOLDER_PREFIX}{org_id}|{did}" if is_folder else f"{org_id}|{uid}"
                for did, uid, is_folder in records
            }
        else:
            ids = set(resource_ids)
            uids = {uid for rid in resource_ids if (uid := cls._parse_resource_id(org_id, rid)[0]) is not None}
            if uids:
                folder_ids = Dashboard.objects.filter(org_id=org_id, uid__in=uids, is_folder=False).values_list(
                    "folder_id", flat=True
                )
                ids.update(f"{cls.FOLDER_PREFIX}{org_id}|{fid}" for fid in folder_ids if fid)
        # 空 id 探针仅用于识别当前空间的全量授权，不会返回实例 ACL。
        return tuple(sorted(ids)) or (f"{org_id}|",)

    @classmethod
    def get_user_permission(
        cls, username: str, org_name: str, force_check: bool = False, *, dashboard_uids: list[str] | None = None
    ) -> tuple[bool, GrafanaRole, dict[str, GrafanaPermission]]:
        """保留 V3 产品接口与三项返回契约；业务只传产品参数，不接触 IAM DTO。"""
        resource_ids = None
        if dashboard_uids is not None:
            org_id = get_or_create_org(org_name)["id"]
            resource_ids = [f"{org_id}|{uid}" for uid in dashboard_uids]
        role, dashboard_permissions = cls.get_visible_dashboards(
            username, org_name, resource_ids=resource_ids, force_check=force_check
        )
        return True, role, dashboard_permissions

    @classmethod
    def has_permission(
        cls, request, view, org_name: str, force_check: bool = False
    ) -> tuple[bool, GrafanaRole, dict[str, GrafanaPermission]]:
        """
        检查用户的仪表盘权限（内部用户 role 门禁 + 外部用户资源列表合并）。

        代理同步需要完整的当前 org 候选，包含 folder，才能增加和撤销实例 ACL。
        """
        # 内部用户权限处理
        if getattr(request, "skip_check", False) or request.user.is_superuser:
            role, dashboard_permissions = GrafanaRole.Admin, {}
        else:
            role = cls.get_user_role(request.user.username, org_name, force_check)
            dashboard_permissions = {}
            if role < GrafanaRole.Editor:
                _, new_role, dashboard_permissions = cls.get_user_permission(
                    request.user.username, org_name, force_check
                )
                if new_role >= role:
                    role = new_role

        # 外部用户权限处理
        # 兼容处理folder权限判断: 将folder权限展开为dashboard权限
        if getattr(request, "external_user", None):
            external_dashboard_permissions = {}
            # 获取权限记录
            external_permissions = ExternalPermission.objects.filter(
                authorized_user=request.external_user,
                bk_biz_id=int(org_name),
                action_id__in=["view_grafana", "manage_grafana"],
                expire_time__gt=timezone.now(),
            )

            org_id = get_or_create_org(org_name)["id"]

            for permission in external_permissions:
                # 展开资源（dashboard 和 folder）为 dashboard uids
                all_dashboard_uids = cls.expand_resources_to_dashboard_uids(org_id, permission.resources)

                # 为所有dashboard设置权限
                for uid in all_dashboard_uids:
                    if permission.action_id == "view_grafana" and (
                        role >= GrafanaRole.Viewer or uid in dashboard_permissions
                    ):
                        external_dashboard_permissions[uid] = GrafanaPermission.View
                    elif permission.action_id == "manage_grafana" and (
                        role >= GrafanaRole.Editor or uid in dashboard_permissions
                    ):
                        external_dashboard_permissions[uid] = GrafanaPermission.Edit

            role = GrafanaRole.Viewer
            dashboard_permissions = external_dashboard_permissions

        return True, role, dashboard_permissions


class GrafanaReadPermission:
    def __init__(self, permission: permissions.BasePermission = None):
        self.permission = permission

    def has_permission(self, request, view):
        if not request.biz_id:
            return True

        ok, role, dashboard_permissions = DashboardPermission.has_permission(request, view, request.biz_id)
        if ok and (role != GrafanaRole.Anonymous or dashboard_permissions):
            return True

        if self.permission is None:
            return False
        return self.permission.has_permission(request, view)


class GrafanaWritePermission:
    def __init__(self, permission: permissions.BasePermission = None):
        self.permission = permission

    def has_permission(self, request, view):
        if not request.biz_id:
            return True

        ok, role, dashboard_permissions = DashboardPermission.has_permission(request, view, request.biz_id)
        if ok and role >= GrafanaRole.Editor:
            return True

        if self.permission is None:
            return False
        return self.permission.has_permission(request, view)
