# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from typing import Dict, Set, Tuple

from django.utils import timezone
from iam import ObjectSet, make_expression
from iam.exceptions import AuthAPIError
from rest_framework import permissions

from bk_dataview.permissions import BasePermission, GrafanaPermission, GrafanaRole
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.models.external_iam import ExternalPermission

logger = logging.getLogger("monitor_web")


class DashboardPermission(BasePermission):
    """
    仪表盘权限
    """

    @classmethod
    def get_policy_dashboard_uids(cls, bk_biz_id: int, policy: Dict) -> Set[str]:
        """
        从权限策略中获取仪表盘 ID
        """
        bk_biz_id = int(bk_biz_id)
        uids = set()
        op = policy.get("op", "").lower()
        if op == "or":
            for content in policy["content"]:
                uids.update(cls.get_policy_dashboard_uids(bk_biz_id, content))
        elif op == "in":
            uids.update(policy["value"])
        elif op == "eq":
            uids.add(policy["value"])
        elif op == "and":
            iam_biz_id = None
            iam_uids = set()
            for content in policy["content"]:
                if content.get("field") == "grafana_dashboard._bk_iam_path_":
                    result = content["value"].split(",")
                    if len(result) == 2 and result[0] == f"/{ResourceEnum.BUSINESS.id}":
                        iam_biz_id = int(result[1][:-1])
                        break
                elif content.get("field") == "grafana_dashboard.id":
                    iam_uids.update(cls.get_policy_dashboard_uids(bk_biz_id, content))
            if not iam_biz_id or iam_biz_id == bk_biz_id:
                uids.update(iam_uids)
        return uids

    @classmethod
    def get_user_role(cls, request, org_name: str) -> GrafanaRole:
        """
        获取仪表盘角色
        """
        role = GrafanaRole.Anonymous
        if request.user.is_superuser:
            return GrafanaRole.Admin

        bk_biz_id = int(org_name)
        permission = Permission(username=request.user.username)

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
    def get_user_permission(cls, request, org_name: str) -> Tuple[bool, GrafanaRole, Dict[str, GrafanaPermission]]:
        role = cls.get_user_role(request, org_name)

        # 如果用户拥有编辑以上权限, 则不需要再同步仪表盘权限
        if role >= GrafanaRole.Editor:
            return True, role, {}

        p = Permission(username=request.user.username)
        if getattr(request, "skip_check", False):
            p.skip_check = True
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
        view_uids = cls.get_policy_dashboard_uids(int(org_name), view_policy)
        edit_uids = cls.get_policy_dashboard_uids(int(org_name), edit_policy)
        dashboard_permissions = {}

        for uid in view_uids:
            dashboard_permissions[uid] = GrafanaPermission.View
        for uid in edit_uids:
            dashboard_permissions[uid] = GrafanaPermission.Edit

        return True, role, dashboard_permissions

    @classmethod
    def has_permission(cls, request, view, org_name: str) -> Tuple[bool, GrafanaRole, Dict[str, GrafanaPermission]]:
        """
        仪表盘权限校验
        """
        # 内部用户权限处理
        _, role, dashboard_permissions = cls.get_user_permission(request, org_name)

        logger.info(f"user_permission: {role}, {dashboard_permissions}")

        # 外部用户权限处理
        if getattr(request, "external_user", None):
            external_dashboard_permissions = {}
            external_permissions = ExternalPermission.objects.filter(
                authorized_user=request.external_user,
                bk_biz_id=int(org_name),
                action_id__in=["view_grafana", "manage_grafana"],
                expire_time__gt=timezone.now(),
            )

            for permission in external_permissions:
                for record in permission.resources:
                    if permission.action_id == "view_grafana" and (
                        role >= GrafanaRole.Viewer or record in dashboard_permissions
                    ):
                        external_dashboard_permissions[record] = GrafanaPermission.View
                    elif permission.action_id == "manage_grafana" and (
                        role >= GrafanaRole.Editor or record in dashboard_permissions
                    ):
                        external_dashboard_permissions[record] = GrafanaPermission.Edit

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
