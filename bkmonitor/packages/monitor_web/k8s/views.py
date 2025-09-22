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


class ResourcesViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]

    resource_routes = [
        # 获取集群列表
        ResourceRoute("GET", resource.k8s.list_bcs_cluster, endpoint="list_bcs_cluster"),
        # 获取场景下指标列表
        ResourceRoute("GET", resource.k8s.scenario_metric_list, endpoint="scenario_metric_list"),
        # 获取指定集群下资源列表
        ResourceRoute("POST", resource.k8s.list_k8s_resources, endpoint="list_resources"),
        # 获取指定资源的详情
        ResourceRoute("GET", resource.k8s.get_resource_detail, endpoint="get_resource_detail"),
        # 获取 Workload 总览
        ResourceRoute("GET", resource.k8s.workload_overview, endpoint="workload_overview"),
        # 获取资源性能趋势
        ResourceRoute("POST", resource.k8s.resource_trend, endpoint="resource_trend"),
        # 获取 Namespace Workload 总览
        ResourceRoute("POST", resource.k8s.namespace_workload_overview, endpoint="namespace_workload_overview"),
    ]
