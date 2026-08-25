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
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import IAMPermission
from bkmonitor.models import Report
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ReportManagePermission(IAMPermission):
    def __init__(self):
        super().__init__([ActionEnum.MANAGE_REPORT])

    def has_permission(self, request, view):
        try:
            report_id = int(request.data.get("report_id"))
        except (AttributeError, TypeError, ValueError):
            return False
        if report_id <= 0:
            return False
        bk_biz_id = Report.objects.filter(id=report_id).values_list("bk_biz_id", flat=True).first()
        if bk_biz_id is None:
            return False
        self.resources = [ResourceEnum.BUSINESS.create_instance(bk_biz_id)]
        return super().has_permission(request, view)


class NewReportViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ("clone_report", "delete_report"):
            return [ReportManagePermission()]
        return []

    resource_routes = [
        # 获取订阅列表
        ResourceRoute("POST", resource.new_report.get_report_list, endpoint="get_report_list"),
        # 获取订阅详情
        ResourceRoute("GET", resource.new_report.get_report, endpoint="get_report"),
        # 克隆订阅
        ResourceRoute("POST", resource.new_report.clone_report, endpoint="clone_report"),
        # 创建/编辑订阅
        ResourceRoute("POST", resource.new_report.create_or_update_report, endpoint="create_or_update_report"),
        # 删除订阅
        ResourceRoute("POST", resource.new_report.delete_report, endpoint="delete_report"),
        # 发送订阅
        ResourceRoute("POST", resource.new_report.send_report, endpoint="send_report"),
        # 根据用户取消/重新订阅
        ResourceRoute(
            "POST", resource.new_report.cancel_or_resubscribe_report, endpoint="cancel_or_resubscribe_report"
        ),
        # 获取订阅发送记录列表
        ResourceRoute("GET", resource.new_report.get_send_records, endpoint="get_send_records"),
        # 根据用户获取订阅审批记录列表
        ResourceRoute("GET", resource.new_report.get_apply_records, endpoint="get_apply_records"),
        # 获取变量列表
        ResourceRoute("GET", resource.new_report.get_variables, endpoint="get_variables"),
        # 根据查询条件获取已存在的订阅列表
        ResourceRoute("GET", resource.new_report.get_exist_reports, endpoint="get_exist_reports"),
    ]
