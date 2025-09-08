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


class ReportViewSet(ResourceViewSet):
    def get_permissions(self):
        return []

    resource_routes = [
        # 已订阅列表接口
        ResourceRoute("GET", resource.report.report_list, endpoint="report_list"),
        # 已订阅列表接口
        ResourceRoute("GET", resource.report.status_list, endpoint="status_list"),
        # 每个业务下的图表列表接口
        ResourceRoute("GET", resource.report.graphs_list_by_biz, endpoint="graphs_list_by_biz"),
        # 获取仪表盘下的所有panel信息
        ResourceRoute("GET", resource.report.get_panels_by_dashboard, endpoint="get_panels_by_dashboard"),
        # 创建/编辑订阅报表
        ResourceRoute("POST", resource.report.report_create_or_update, endpoint="report_create_or_update"),
        # 测试订阅报表
        ResourceRoute("POST", resource.report.report_test, endpoint="report_test"),
        # 内置指标列表
        ResourceRoute("GET", resource.report.build_in_metric, endpoint="build_in_metric"),
        # 订阅报表内容列表
        ResourceRoute("GET", resource.report.report_content, endpoint="report_content"),
        # 删除订阅报表
        ResourceRoute("POST", resource.report.report_delete, endpoint="report_delete"),
        # 用户组列表
        ResourceRoute("GET", resource.report.group_list, endpoint="group_list"),
        # 克隆
        ResourceRoute("GET", resource.report.report_clone, endpoint="report_clone"),
    ]
