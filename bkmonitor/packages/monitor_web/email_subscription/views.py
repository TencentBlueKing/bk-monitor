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
        # 获取订阅列表
        ResourceRoute("POST", resource.email_subscription.get_subscription_list, endpoint="get_subscription_list"),
        # 获取订阅详情
        ResourceRoute("GET", resource.email_subscription.get_subscription, endpoint="get_subscription"),
        # 克隆订阅
        ResourceRoute("POST", resource.email_subscription.clone_subscription, endpoint="clone_subscription"),
        # 创建/编辑订阅
        ResourceRoute(
            "POST", resource.email_subscription.create_or_update_subscription, endpoint="create_or_update_subscription"
        ),
        # 删除订阅
        ResourceRoute("POST", resource.email_subscription.delete_subscription, endpoint="delete_subscription"),
        # 发送订阅
        ResourceRoute("POST", resource.email_subscription.send_subscription, endpoint="send_subscription"),
        # 根据用户取消订阅
        ResourceRoute("POST", resource.email_subscription.cancel_subscription, endpoint="cancel_subscription"),
        # 获取订阅发送记录列表
        ResourceRoute("GET", resource.email_subscription.get_send_records, endpoint="get_send_records"),
        # 根据用户获取订阅审批记录列表
        ResourceRoute("GET", resource.email_subscription.get_apply_records, endpoint="get_apply_records"),
        # 获取变量列表
        ResourceRoute("GET", resource.email_subscription.get_variables, endpoint="get_variables"),
        # 根据查询条件获取已存在的订阅列表
        ResourceRoute("GET", resource.email_subscription.get_exist_subscriptions, endpoint="get_exist_subscriptions"),
    ]
