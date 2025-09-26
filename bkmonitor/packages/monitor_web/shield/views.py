# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.drf_resource import resource


class ShieldViewSet(ResourceViewSet):

    query_post_actions = ["shield_list", "frontend_shield_list", "shield_snapshot"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS or self.action in self.query_post_actions:
            return [BusinessActionPermission([ActionEnum.VIEW_DOWNTIME])]
        return [BusinessActionPermission([ActionEnum.MANAGE_DOWNTIME])]

    resource_routes = [
        # 告警屏蔽列表（通用）
        ResourceRoute("POST", resource.shield.shield_list, endpoint="shield_list"),
        # 告警屏蔽列表（前端）
        ResourceRoute("POST", resource.shield.frontend_shield_list, endpoint="frontend_shield_list"),
        # 告警屏蔽详情（通用）
        ResourceRoute("GET", resource.shield.shield_detail, endpoint="shield_detail"),
        # 告警屏蔽详情（前端）
        ResourceRoute("GET", resource.shield.frontend_shield_detail, endpoint="frontend_shield_detail"),
        # 告警屏蔽克隆详情（前端）
        ResourceRoute("GET", resource.shield.frontend_clone_info, endpoint="frontend_clone_info"),
        # 告警屏蔽详情（快照）
        ResourceRoute("POST", resource.shield.shield_snapshot, endpoint="shield_snapshot"),
        # 新增屏蔽（通用）
        ResourceRoute("POST", resource.shield.add_shield, endpoint="add_shield"),
        # 批量告警屏蔽
        ResourceRoute("POST", resource.shield.bulk_add_alert_shield, endpoint="bulk_add_alert_shield"),
        # 编辑屏蔽（通用）
        ResourceRoute("POST", resource.shield.edit_shield, endpoint="edit_shield"),
        # 解除屏蔽（通用）
        ResourceRoute("POST", resource.shield.disable_shield, endpoint="disable_shield"),
        # 测试接口，更新失效屏蔽的屏蔽内容
        ResourceRoute("GET", resource.shield.update_failure_shield_content, endpoint="update_failure_shield_content"),
    ]
