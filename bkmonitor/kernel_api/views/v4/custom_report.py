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


class CustomEventViewSet(ResourceViewSet):
    """
    自定义事件
    """

    resource_routes = [
        # 获取自定义上报的proxy主机信息
        ResourceRoute("GET", resource.custom_report.proxy_host_info, endpoint="proxy_host_info"),
        # 获取业务下自定义事件列表
        ResourceRoute("GET", resource.custom_report.query_custom_event_group, endpoint="query_custom_event_group"),
        # 获取自定义事件详情
        ResourceRoute("GET", resource.custom_report.get_custom_event_group, endpoint="get_custom_event_group"),
        # 校验自定义事件名称是否合法
        ResourceRoute(
            "GET", resource.custom_report.validate_custom_event_group_name, endpoint="validate_custom_event_group_name"
        ),
        # 创建自定义事件
        ResourceRoute("POST", resource.custom_report.create_custom_event_group, endpoint="create_custom_event_group"),
        # 修改自定义事件
        ResourceRoute("POST", resource.custom_report.modify_custom_event_group, endpoint="modify_custom_event_group"),
        # 删除自定义事件
        ResourceRoute("POST", resource.custom_report.delete_custom_event_group, endpoint="delete_custom_event_group"),
    ]


class CustomMetricViewSet(ResourceViewSet):
    """
    自定义指标
    """

    resource_routes = [
        # 自定义指标列表
        ResourceRoute("GET", resource.custom_report.custom_time_series_list, endpoint="custom_time_series"),
        # 自定义指标详情
        ResourceRoute("GET", resource.custom_report.custom_time_series_detail, endpoint="custom_time_series_detail"),
        # 校验自定义指标名称是否合法
        ResourceRoute(
            "GET", resource.custom_report.validate_custom_ts_group_name, endpoint="validate_custom_ts_group_name"
        ),
        # 创建自定义指标
        ResourceRoute("POST", resource.custom_report.create_custom_time_series, endpoint="create_custom_time_series"),
        # 修改自定义指标
        ResourceRoute("POST", resource.custom_report.modify_custom_time_series, endpoint="modify_custom_time_series"),
        # 删除自定义指标
        ResourceRoute("POST", resource.custom_report.delete_custom_time_series, endpoint="delete_custom_time_series"),
    ]
