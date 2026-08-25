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

from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import IAMPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.models.collecting import CollectConfigMeta


class CollectConfigActionPermission(IAMPermission):
    """按采集配置所属业务做权限校验，缺少 collect_config_id 时拒绝。"""

    def has_permission(self, request, view):
        data = request.query_params if request.method == "GET" else request.data
        collect_config_id = data.get("collect_config_id")
        if collect_config_id in (None, ""):
            return False
        try:
            collect_config = CollectConfigMeta.objects.only("id", "bk_biz_id").get(id=collect_config_id)
        except CollectConfigMeta.DoesNotExist:
            return False
        if not collect_config.bk_biz_id:
            return False
        self.resources = [ResourceEnum.BUSINESS.create_instance(collect_config.bk_biz_id)]
        return super(CollectConfigActionPermission, self).has_permission(request, view)


class DatalinkStatusViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action == "update_alert_user_groups":
            return [CollectConfigActionPermission([ActionEnum.MANAGE_COLLECTION])]
        return [CollectConfigActionPermission([ActionEnum.VIEW_COLLECTION])]

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
