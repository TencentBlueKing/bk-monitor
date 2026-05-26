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

from django.utils.translation import ugettext_lazy as _lazy
from rest_framework import permissions

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import IAMPermission


class GlobalSettingPermission(IAMPermission):
    """
    全局配置管理权限

    用于资源注册、链路管理等平台设置类接口。这类接口在前端仅出现在「平台设置」页面，
    可能返回/写入集群密码等敏感信息，需与前端页面一致，仅管理员（具备全局配置编辑权限）可用。
    直接使用 IAMPermission 而非 BusinessActionPermission，避免在缺少 bk_biz_id 时被短路放行。
    """

    def __init__(self):
        super().__init__([ActionEnum.MANAGE_GLOBAL_SETTING])


class SuperuserWritePermission(permissions.BasePermission):
    """
    超级管理员写权限
    """

    message = _lazy("当前用户无变更权限")

    def check_permission(self, request):
        if request.method in permissions.SAFE_METHODS:
            # 安全方法无需校验
            return True
        user = request.user
        return user and user.is_superuser

    def has_permission(self, request, view):
        return self.check_permission(request)

    def has_object_permission(self, request, view, obj):
        return self.check_permission(request)


class BusinessViewPermission(permissions.BasePermission):
    """
    业务访问权限判断
    """

    def has_permission(self, request, view):
        if request.biz_id is None:
            return True

        return Permission().is_allowed_by_biz(
            bk_biz_id=request.biz_id,
            action=ActionEnum.VIEW_BUSINESS,
            raise_exception=True,
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class ApiTokenPermission(permissions.BasePermission):
    """
    业务访问权限判断
    """

    def has_permission(self, request, view):
        return True
