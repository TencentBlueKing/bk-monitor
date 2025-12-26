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
from iam import ObjectSet, make_expression
from iam.exceptions import AuthAPIError, AuthInvalidParam
from rest_framework import permissions

from bk_dataview.api import get_or_create_org
from bk_dataview.models import Dashboard
from bk_dataview.permissions import BasePermission, GrafanaPermission, GrafanaRole
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.models.external_iam import ExternalPermission
from bkmonitor.utils.request import get_request_tenant_id

logger = logging.getLogger("monitor_web")


class DashboardPermission(BasePermission):
    """
    仪表盘权限 - 支持 folder 权限展开(直接返回当前folder下所有dashboard)
    """

    # 添加前缀， 便于区分
    FOLDER_PREFIX = "folder:"

    @classmethod
    def get_policy_resources(cls, org_id: int, bk_biz_id: int, policy: dict) -> tuple[set[str], set[tuple[int, int]]]:
        """
        从权限策略中获取资源 ID（dashboard 和 folder）

        返回:
            dashboard_uids: 仪表盘 uid 集合
            folder_ids: (org_id, folder_id) 元组集合
        """
        bk_biz_id = int(bk_biz_id)
        raw_ids = set()
        op = policy.get("op", "").lower()

        if op == "or":
            for content in policy["content"]:
                d_uids, f_ids = cls.get_policy_resources(org_id, bk_biz_id, content)
                # 递归结果需要转换回 raw_ids 再处理
                for uid in d_uids:
                    raw_ids.add(f"{org_id}|{uid}")
                for f_org_id, f_id in f_ids:
                    raw_ids.add(f"{cls.FOLDER_PREFIX}{f_org_id}|{f_id}")
        elif op == "in":
            raw_ids.update(policy["value"])
        elif op == "eq":
            raw_ids.add(policy["value"])
        elif op == "and":
            iam_biz_id = None
            # 存储folder_id和dashboard_id, 并返回
            iam_raw_ids = set()
            for content in policy["content"]:
                # 解析iam_path，获取业务ID
                if content.get("field") == "grafana_dashboard._bk_iam_path_":
                    result = content["value"].split(",")
                    if len(result) == 2 and result[0] == f"/{ResourceEnum.BUSINESS.id}":
                        iam_biz_id = int(result[1][:-1])
                        break
                # 解析资源ID， 获取仪表盘和folder
                elif content.get("field") == "grafana_dashboard.id":
                    d_uids, f_ids = cls.get_policy_resources(org_id, bk_biz_id, content)
                    # 分别处理 dashboard 和 folder
                    for uid in d_uids:
                        iam_raw_ids.add(f"{org_id}|{uid}")
                    for f_org_id, f_id in f_ids:
                        iam_raw_ids.add(f"{cls.FOLDER_PREFIX}{f_org_id}|{f_id}")
            if not iam_biz_id or iam_biz_id == bk_biz_id:
                raw_ids.update(iam_raw_ids)

        # 解析 raw_ids，分离 dashboard 和 folder
        dashboard_uids = set()
        folder_ids = set()

        for raw_id in raw_ids:
            d_uid, f_id = cls._parse_resource_id(org_id, raw_id)
            if d_uid:
                dashboard_uids.add(d_uid)
            if f_id:
                folder_ids.add(f_id)

        return dashboard_uids, folder_ids

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
    def get_policy_dashboard_uids(cls, org_id: int, bk_biz_id: int, policy: dict) -> set[str]:
        """
        从权限策略中获取仪表盘 ID（兼容旧接口，同时支持 folder 展开）
        """
        if not policy:
            return set()

        # 获取 dashboard 和 folder
        dashboard_uids, folder_ids = cls.get_policy_resources(org_id, bk_biz_id, policy)

        # 展开 folder 为 dashboard
        folder_dashboard_uids = cls.expand_folder_to_dashboards(org_id, folder_ids)

        # 合并结果
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
        except AuthAPIError:
            pass

        return role

    @classmethod
    def get_user_permission(
        cls, username: str, org_name: str, force_check: bool = False
    ) -> tuple[bool, GrafanaRole, dict[str, GrafanaPermission]]:
        role = GrafanaRole.Anonymous
        p = Permission(username=username, bk_tenant_id=get_request_tenant_id())
        if force_check:
            p.skip_check = False

        if p.skip_check:
            return True, GrafanaRole.Admin, {}

        view_policy = p.iam_client._do_policy_query(p.make_request(action=ActionEnum.VIEW_SINGLE_DASHBOARD))
        edit_policy = p.iam_client._do_policy_query(p.make_request(action=ActionEnum.EDIT_SINGLE_DASHBOARD))

        # 判断是否有全仪表盘权限
        obj_set = ObjectSet()
        obj_set.add_object(
            ResourceEnum.GRAFANA_DASHBOARD.id, {"_bk_iam_path_": f"/{ResourceEnum.BUSINESS.id},{org_name}/", "id": ""}
        )
        if role < GrafanaRole.Editor and edit_policy and p.iam_client._eval_expr(make_expression(edit_policy), obj_set):
            role = GrafanaRole.Editor
        elif (
            role < GrafanaRole.Viewer and view_policy and p.iam_client._eval_expr(make_expression(view_policy), obj_set)
        ):
            role = GrafanaRole.Viewer

        # 如果用户拥有编辑以上权限, 则不需要再同步仪表盘权限
        if role >= GrafanaRole.Editor:
            return True, role, {}

        # 获取仪表盘权限
        org_id = get_or_create_org(org_name)["id"]
        view_uids = cls.get_policy_dashboard_uids(org_id, int(org_name), view_policy)
        edit_uids = cls.get_policy_dashboard_uids(org_id, int(org_name), edit_policy)
        dashboard_permissions = {}

        for uid in view_uids:
            dashboard_permissions[uid] = GrafanaPermission.View
        for uid in edit_uids:
            dashboard_permissions[uid] = GrafanaPermission.Edit

        return True, role, dashboard_permissions

    @classmethod
    def has_permission(
        cls, request, view, org_name: str, force_check: bool = False
    ) -> tuple[bool, GrafanaRole, dict[str, GrafanaPermission]]:
        """
        检查用户的仪表盘权限
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
