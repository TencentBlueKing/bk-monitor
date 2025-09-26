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

from bkmonitor.views.renderers import MonitorJSONRenderer


class ActionInstanceViewSet(ResourceViewSet):
    """
    处理事件后台接口
    """

    renderer_classes = [MonitorJSONRenderer]

    resource_routes = [
        ResourceRoute("POST", resource.action.itsm_callback, endpoint="itsm_callback"),
        ResourceRoute("POST", resource.action.batch_create_action, endpoint="batch_create_action"),
        ResourceRoute("POST", resource.action.get_action_params_by_config, endpoint="get_action_params_by_config"),
    ]


class SearchActionViewSet(ResourceViewSet):
    """
    查询处理记录
    """

    resource_routes = [
        ResourceRoute("POST", resource.alert.search_action, endpoint="search_action"),
    ]
