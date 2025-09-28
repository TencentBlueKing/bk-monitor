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
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class PermissionMixin:
    iam_read_actions = ActionEnum.VIEW_HOST
    iam_write_actions = ActionEnum.VIEW_HOST

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_HOST])]


class HostPerformanceDetailViewSet(PermissionMixin, ResourceViewSet):
    """
    获取主机详情页信息
    """

    resource_routes = [ResourceRoute("POST", resource.performance.host_performance_detail)]


class HostTopoNodeDetailViewSet(PermissionMixin, ResourceViewSet):
    """
    获取主机拓扑树上的CMDB节点信息
    """

    resource_routes = [ResourceRoute("POST", resource.performance.host_topo_node_detail)]


class TopoNodeProcessStatusViewSet(PermissionMixin, ResourceViewSet):
    """
    获取拓扑节点下的进程状态信息
    """

    resource_routes = [ResourceRoute("POST", resource.performance.topo_node_process_status)]


class HostListViewSet(PermissionMixin, ResourceViewSet):
    """
    获取主机列表信息
    """

    resource_routes = [ResourceRoute("GET", resource.performance.host_performance, content_encoding="gzip")]


class SearchHostInfoViewSet(ResourceViewSet):
    """
    查询主机基本信息
    """

    resource_routes = [
        ResourceRoute("POST", resource.performance.search_host_info, content_encoding="gzip"),
    ]


class SearchHostMetricViewSet(ResourceViewSet):
    """
    查询主机指标
    """

    resource_routes = [
        ResourceRoute("POST", resource.performance.search_host_metric),
    ]
