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
"""
data query
"""


from bkmonitor.views.renderers import MonitorJSONRenderer
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.permission import BusinessListByActions
from kernel_api.resource.query import QueryEsResource
from query_api.resources import GetTSDataResource


class GetTSDataViewSet(ResourceViewSet):
    """
    监控新链路数据查询
    """

    renderer_classes = (MonitorJSONRenderer,)

    resource_routes = [
        ResourceRoute("POST", GetTSDataResource),
    ]


class GetEsDataViewSet(ResourceViewSet):
    """
    从ES查询信息
    """

    resource_routes = [
        ResourceRoute("POST", QueryEsResource),
    ]


class PermissionViewSet(ResourceViewSet):
    """
    权限中心相关支持
    """

    resource_routes = [
        ResourceRoute("POST", BusinessListByActions),
    ]
