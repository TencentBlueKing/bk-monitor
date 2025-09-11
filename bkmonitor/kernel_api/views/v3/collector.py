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


from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.drf_resource import resource
from kernel_api.resource.uptimecheck import ImportUptimeCheckNodeResource, ImportUptimeCheckTaskResource


class UptimeCheckNodeViewSet(ResourceViewSet):
    """
    拨测节点
    """

    resource_routes = [
        ResourceRoute("POST", ImportUptimeCheckNodeResource, endpoint="import"),
        ResourceRoute("GET", resource.uptime_check.export_uptime_check_node_conf, endpoint="export"),
    ]


class UptimeCheckTaskViewSet(ResourceViewSet):
    """
    拨测任务
    """

    resource_routes = [
        ResourceRoute("POST", ImportUptimeCheckTaskResource, endpoint="import"),
        ResourceRoute("GET", resource.uptime_check.export_uptime_check_conf, endpoint="export"),
    ]
