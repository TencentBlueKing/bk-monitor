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
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.grafana.permissions import GrafanaWritePermission


class TokenManagerViewSet(ResourceViewSet):
    """
    API 调用凭证管理
    """

    def get_permissions(self):
        manage_rule = BusinessActionPermission([ActionEnum.MANAGE_RULE])
        # grafana 类型可由仪表盘编辑者获取；as_code（默认类型）用于配置导入，仅限规则管理
        if self.request.query_params.get("type") == "grafana":
            return [GrafanaWritePermission(manage_rule)]
        return [manage_rule]

    resource_routes = [
        ResourceRoute("GET", resource.commons.get_api_token, endpoint="get_api_token"),
    ]
