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
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class EmailSubscriptionViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [
        # 订阅列表接口
        ResourceRoute("GET", resource.email_subscription.get_subscription_list, endpoint="get_subscription_list"),
        # 订阅详情接口
        ResourceRoute("GET", resource.email_subscription.get_subscription, endpoint="get_subscription"),
        # 订阅克隆接口
        ResourceRoute("GET", resource.email_subscription.clone_subscription, endpoint="clone_subscription"),
        # 创建/编辑订阅接口
        ResourceRoute(
            "POST", resource.email_subscription.create_or_update_subscription, endpoint="create_or_update_subscription"
        ),
        # 删除订阅接口
        ResourceRoute("POST", resource.email_subscription.delete_subscription, endpoint="delete_subscription"),
        # 发送订阅接口
        ResourceRoute("POST", resource.email_subscription.send_subscription, endpoint="send_subscription"),
        # 内置指标列表
        ResourceRoute("GET", resource.email_subscription.cancel_subscription, endpoint="cancel_subscription"),
        # 订阅发送记录列表
        ResourceRoute("GET", resource.email_subscription.get_send_records, endpoint="get_send_records"),
        # 订阅审批记录列表
        ResourceRoute("GET", resource.email_subscription.get_apply_records, endpoint="get_apply_records"),
        # 内部用户渠道获取用户组列表
        ResourceRoute("GET", resource.email_subscription.user_group_list, endpoint="user_group_list"),
        # 获取索引集列表
        ResourceRoute("GET", resource.email_subscription.user_group_list, endpoint="get_index_sets"),
        # 获取变量列表
        ResourceRoute("GET", resource.email_subscription.user_group_list, endpoint="get_variables"),
        # 获取已存在的相关订阅列表
        ResourceRoute("GET", resource.email_subscription.user_group_list, endpoint="get_exist_subscriptions"),
    ]
