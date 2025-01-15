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
import json
from collections import defaultdict
from functools import reduce
from typing import Dict, List, Optional, Set, Tuple, Union

from django.db import IntegrityError
from django.db.models import Q

from .models import (
    BuiltinRole,
    Dashboard,
    Org,
    OrgUser,
    Permission,
    Preferences,
    Role,
    User,
    UserRole,
)
from .permissions import GrafanaPermission, GrafanaRole
from .utils import generate_uid

DashboardPermissionActions = {
    GrafanaPermission.View: ["dashboards:read"],
    GrafanaPermission.Edit: ["dashboards:read", "dashboards:write", "dashboards:delete"],
    GrafanaPermission.Admin: [
        "dashboards:read",
        "dashboards:write",
        "dashboards:delete",
        "dashboards.permissions:read",
        "dashboards.permissions:write",
    ],
}

_ORG_CACHE = {}
_USER_CACHE = {}


def get_or_create_user(username: str) -> dict:
    """
    创建用户
    """
    if username in _USER_CACHE:
        return _USER_CACHE[username]

    try:
        user = User.objects.get(login=username)
    except User.DoesNotExist:
        email = username
        if "@" not in email:
            email += "@localhost"

        try:
            user = User.objects.create(
                login=username,
                version=0,
                email=email,
            )
        except IntegrityError:
            user = User.objects.get(login=username)

    _USER_CACHE[username] = {
        "id": user.id,
        "login": user.login,
        "email": user.email,
        "name": user.name,
        "theme": user.theme,
    }
    return _USER_CACHE[username]


def get_org_by_name(org_name: str) -> Optional[dict]:
    """
    获取组织
    """
    org_name = str(org_name)

    if org_name in _ORG_CACHE:
        return _ORG_CACHE[org_name]

    try:
        org = Org.objects.get(name=org_name)
    except Org.DoesNotExist:
        return None

    _ORG_CACHE[org_name] = {"id": org.id, "name": org.name}
    return _ORG_CACHE[org_name]


def get_org_by_id(org_id: int) -> Optional[dict]:
    """
    获取组织
    """
    org_id = int(org_id)

    if org_id in _ORG_CACHE:
        return _ORG_CACHE[org_id]

    try:
        org = Org.objects.get(id=org_id)
    except Org.DoesNotExist:
        return None

    _ORG_CACHE[org_id] = {"id": org.id, "name": org.name}
    return _ORG_CACHE[org_id]


def get_or_create_org(org_name: str) -> dict:
    """
    获取或创建组织
    """
    org_info = get_org_by_name(org_name)
    if org_info:
        return org_info

    try:
        org = Org.objects.create(name=org_name)

        # 创建内置角色
        editor_role_uid = generate_uid(exclude_model=Role)
        viewer_role_uid = generate_uid(exclude_uids=[editor_role_uid], exclude_model=Role)
        Role.objects.bulk_create(
            [
                Role(
                    org_id=org.id,
                    name="managed:builtins:editor:permissions",
                    uid=editor_role_uid,
                ),
                Role(
                    org_id=org.id,
                    name="managed:builtins:viewer:permissions",
                    uid=viewer_role_uid,
                ),
            ]
        )
        BuiltinRole.objects.bulk_create(
            [
                BuiltinRole(org_id=org.id, role="Viewer", role_id=Role.objects.get(uid=viewer_role_uid).id),
                BuiltinRole(org_id=org.id, role="Editor", role_id=Role.objects.get(uid=editor_role_uid).id),
            ]
        )
    except IntegrityError:
        org = Org.objects.get(name=org_name)

    # 确保admin用户存在
    user = get_or_create_user("admin")
    sync_user_role(org.id, user["id"], "Admin")

    return {"id": org.id, "name": org.name}


def get_dashboard_tree(
    org_id: int, user_id: int = None, with_dashboard_data: bool = False, ignore_empty_folder: bool = False
) -> List[dict]:
    """
    获取仪表盘树
    """
    fields = ["id", "uid", "title", "folder_id", "slug"]
    if with_dashboard_data:
        fields.append("data")
    dash_or_folders = Dashboard.objects.filter(org_id=org_id).only(*fields).order_by("-is_folder")

    # 查询用户仪表盘权限
    if user_id:
        dashboard_actions, is_admin = _get_user_dashboard_actions(org_id, user_id)
    else:
        dashboard_actions = {}
        is_admin = True

    folders = {0: {"id": 0, "uid": "", "title": "General", "slug": "", "dashboards": [], "folders": [], "folder_id": 0}}
    for dash_or_folder in dash_or_folders:
        if dash_or_folder.is_folder:
            if dash_or_folder.id in folders:
                continue
            folders[dash_or_folder.id] = {
                "id": dash_or_folder.id,
                "uid": dash_or_folder.uid,
                "title": dash_or_folder.title,
                "slug": dash_or_folder.slug,
                "dashboards": [],
                "folders": [],
                "folder_id": dash_or_folder.folder_id or 0,
            }
        else:
            # 如果仪表盘所属的文件夹不存在，则设置为General
            if dash_or_folder.folder_id not in folders:
                dash_or_folder.folder_id = 0

            # 如果用户不是管理员，且没有仪表盘权限，则跳过
            if not is_admin and dash_or_folder.uid not in dashboard_actions:
                continue
            folders[dash_or_folder.folder_id]["dashboards"].append(
                {
                    "id": dash_or_folder.id,
                    "uid": dash_or_folder.uid,
                    "title": dash_or_folder.title,
                    "slug": dash_or_folder.slug,
                    "folder_id": dash_or_folder.folder_id,
                }
            )
            # 如果需要获取仪表盘数据，则获取
            if with_dashboard_data:
                folders[dash_or_folder.folder_id]["dashboards"][-1]["data"] = json.loads(dash_or_folder.data)

    # 如果文件夹不存在，则设置为General
    for folder in folders.values():
        if folder["folder_id"] not in folders:
            folder["folder_id"] = 0

    # 如果需要忽略空文件夹，则过滤掉空文件夹
    if ignore_empty_folder:
        folders = {folder["id"]: folder for folder in folders.values() if folder["dashboards"] or folder["folders"]}

    return [folder for folder in folders.values() if folder["folder_id"] == 0]


def get_org_or_user_preferences(org_id: int = 0, user_id: int = 0, team_id: int = 0) -> dict:
    """
    获取组织配置
    """
    assert org_id or user_id or team_id, "org_id or user_id or team_id must be provided"

    if org_id:
        preference = Preferences.objects.get(org_id=org_id)
    elif user_id:
        preference = Preferences.objects.get(user_id=user_id)
    else:
        preference = Preferences.objects.get(team_id=team_id)

    return {
        "theme": preference.theme,
        "home_dashboard_id": preference.home_dashboard_id,
        "timezone": preference.timezone,
    }


def sync_user_role(org_id: int, user_id: int, role: str):
    """
    同步用户角色
    """
    # 如果用户没有角色权限，则设置为匿名用户
    if not role:
        role = "Anonymous"

    # 获取或新建组织用户关系表
    try:
        org_user = OrgUser.objects.get(org_id=org_id, user_id=user_id)
    except OrgUser.DoesNotExist:
        org_user = OrgUser.objects.create(org_id=org_id, user_id=user_id, role=role)

    # 如果用户角色不一致，则更新
    if org_user.role != role:
        org_user.role = role
        org_user.save()


def sync_dashboard_permission(
    org_id: int, user_id: int, role: Union[str, GrafanaRole], dashboard_permissions: Dict[str, GrafanaPermission]
):
    """
    同步用户权限
    """
    # 将角色转换为枚举类型
    if isinstance(role, str):
        try:
            role = GrafanaRole[role]
        except KeyError:
            role = GrafanaRole.Anonymous

    # 如果用户是Admin角色，则跳过后续操作
    if role == GrafanaRole.Admin:
        return

    # 过滤掉低于用户角色的单仪表盘权限
    dashboard_permissions = {
        uid: permission for uid, permission in dashboard_permissions.items() if permission.value > role.value
    }

    # 如果没有需要同步的单仪表盘权限，跳过后续操作
    if not dashboard_permissions:
        return

    # 获取或新建单用户权限角色
    user_role = Role.objects.filter(org_id=org_id, name=f"managed:users:{user_id}:permissions").first()
    if not user_role:
        try:
            user_role = Role.objects.create(
                org_id=org_id,
                name=f"managed:users:{user_id}:permissions",
                uid=generate_uid(exclude_model=Role),
            )
            UserRole.objects.create(
                org_id=org_id,
                user_id=user_id,
                role_id=user_role.id,
            )
        except IntegrityError:
            user_role = Role.objects.get(org_id=org_id, name=f"managed:users:{user_id}:permissions")

    # 获取存量用户仪表盘权限
    dashboard_actions, _ = _get_user_dashboard_actions(org_id, user_id, ignore_org_role=True)
    exists_dashboard_permissions = set()
    for uid, actions in dashboard_actions.items():
        exists_dashboard_permissions.update([(uid, action) for action in actions])
    # 获取存量仪表盘
    exists_dashboard_uids = set(Dashboard.objects.filter(org_id=org_id).values_list("uid", flat=True))

    # 生成期望的仪表盘权限
    expected_dashboard_permissions = set()
    for uid, permission in dashboard_permissions.items():
        # 如果仪表盘不存在，则跳过
        if uid not in exists_dashboard_uids:
            continue

        # 如果权限不在预期范围内，则跳过
        if permission not in DashboardPermissionActions:
            continue

        # 生成期望的仪表盘权限
        for action in DashboardPermissionActions[permission]:
            expected_dashboard_permissions.add((uid, action))

    need_create_objs = []
    for uid, action in expected_dashboard_permissions - exists_dashboard_permissions:
        need_create_objs.append(
            Permission(
                role_id=user_role.id,
                action=action,
                scope=f"dashboards:uid:{uid}",
            )
        )

    need_delete_query = []
    for uid, action in exists_dashboard_permissions - expected_dashboard_permissions:
        need_delete_query.append(
            Q(
                role_id=user_role.id,
                action=action,
                scope=f"dashboards:uid:{uid}",
            )
        )

    if need_create_objs:
        Permission.objects.bulk_create(need_create_objs, batch_size=200)
    if need_delete_query:
        Permission.objects.filter(reduce(lambda x, y: x | y, need_delete_query)).delete()


def _get_user_dashboard_actions(org_id: int, user_id: int, ignore_org_role: False) -> Tuple[Dict[str, Set[str]], bool]:
    """
    获取用户仪表盘/文件夹权限
    1. 基于用户的组织角色权限获取仪表盘权限
    2. 基于用户的单仪表盘权限获取仪表盘权限
    """
    role_ids = []

    # 查询组织角色
    org_user = None
    if not ignore_org_role:
        org_user = OrgUser.objects.filter(org_id=org_id, user_id=user_id).first()

    if org_user:
        try:
            org_role = GrafanaRole[org_user.role]
        except KeyError:
            org_role = GrafanaRole.Anonymous
            org_user.role = org_role.name
            org_user.save()

        # 如果是Admin角色，则直接返回
        if org_role == GrafanaRole.Admin:
            return {}, True

        if org_role != GrafanaRole.Anonymous:
            # 查询内置角色
            builtin_role = BuiltinRole.objects.filter(org_id=org_id, role=org_role.name).first()
            if builtin_role:
                role_ids.append(builtin_role.role_id)

    # 查询用户角色
    user_role = UserRole.objects.filter(org_id=org_id, user_id=user_id).first()
    if user_role:
        role_ids.append(user_role.role_id)

    # 如果用户没有任何角色，则返回空
    if not role_ids:
        return {}, False

    permissions = Permission.objects.filter(role_id__in=role_ids).values("action", "scope")
    dashboard_permissions = defaultdict(set)
    for permission in permissions:
        action = permission["action"]
        scope = permission["scope"]
        if scope.startswith("dashboards:uid:"):
            # 仪表盘权限
            uid = scope[15:]
            dashboard_permissions[uid].add(action)

    return dashboard_permissions, False


def get_grafana_panel_query(bk_biz_id: int, dasboard_uid: str, panel_id: int, ref_id: str) -> Dict:
    """
    获取grafana的panel中的数据源配置
    """
    org_id = get_or_create_org(bk_biz_id)["id"]
    dashboard = Dashboard.objects.filter(org_id=org_id, uid=dasboard_uid).first()
    if not dashboard:
        return None

    try:
        dashboard_data = json.loads(dashboard.data)
    except json.JSONDecodeError:
        return None

    for panel in dashboard_data["panels"]:
        # 查找panel
        if panel["id"] != panel_id:
            continue

        for target in panel.get("targets", []):
            # 查找ref_id
            if target.get("refId") == ref_id:
                return target

        return None

    return None
