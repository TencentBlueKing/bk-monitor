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


class NoticeGroupViewSet(ResourceViewSet):
    """
    获取全部通知对象
    """

    def get_permissions(self):
        if self.action in ["get_notice_way", "get_receiver"]:
            return []
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_NOTIFY_TEAM])]
        return [BusinessActionPermission([ActionEnum.MANAGE_NOTIFY_TEAM])]

    resource_routes = [
        # 获取全部通知对象
        ResourceRoute("GET", resource.notice_group.get_receiver, endpoint="get_receiver", content_encoding="gzip"),
        # 获取全部通知方式
        ResourceRoute("GET", resource.notice_group.get_notice_way, endpoint="get_notice_way"),
        # 创建\修改通知组
        ResourceRoute("POST", resource.notice_group.notice_group_config, endpoint="notice_group_config"),
        # 删除通知组
        ResourceRoute("POST", resource.notice_group.delete_notice_group, endpoint="delete_notice_group"),
        # 获取通知组列表
        ResourceRoute("GET", resource.notice_group.notice_group_list, endpoint="notice_group_list"),
        # 获取通知组详情
        ResourceRoute("GET", resource.notice_group.notice_group_detail, endpoint="notice_group_detail"),
    ]
