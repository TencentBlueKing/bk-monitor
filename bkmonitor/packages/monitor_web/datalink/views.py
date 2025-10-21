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

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class DatalinkStatusViewSet(ResourceViewSet):
    resource_routes = [
        # 获取采集状态信息
        ResourceRoute("GET", resource.datalink.alert_status, endpoint="alert_status"),
        # 更新采集订阅用户组
        ResourceRoute("POST", resource.datalink.update_alert_user_groups, endpoint="update_alert_user_groups"),
        # 获取采集主机状态信息
        ResourceRoute("GET", resource.datalink.collecting_target_status, endpoint="collecting_target_status"),
        # 获取链路数据量
        ResourceRoute("GET", resource.datalink.transfer_count_series, endpoint="transfer_count_series"),
        # 获取链路最新数据
        ResourceRoute("GET", resource.datalink.transfer_latest_msg, endpoint="transfer_latest_msg"),
        # 获取存储状态信息
        ResourceRoute("GET", resource.datalink.storage_status, endpoint="storage_status"),
    ]
