"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import permissions

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class CustomEventReportViewSet(ResourceViewSet):
    """
    自定义事件
    """

    def get_permissions(self):
        if self.action == "proxy_host_info":
            return []
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_CUSTOM_EVENT])]
        return [BusinessActionPermission([ActionEnum.MANAGE_CUSTOM_EVENT])]

    resource_routes = [
        ResourceRoute("GET", resource.custom_report.proxy_host_info, endpoint="proxy_host_info"),
        ResourceRoute("GET", resource.custom_report.query_custom_event_group, endpoint="query_custom_event_group"),
        ResourceRoute("GET", resource.custom_report.get_custom_event_group, endpoint="get_custom_event_group"),
        ResourceRoute(
            "GET", resource.custom_report.validate_custom_event_group_name, endpoint="validate_custom_event_group_name"
        ),
        ResourceRoute(
            "GET",
            resource.custom_report.validate_custom_event_group_label,
            endpoint="validate_custom_event_group_label",
        ),
        ResourceRoute("POST", resource.custom_report.create_custom_event_group, endpoint="create_custom_event_group"),
        ResourceRoute("POST", resource.custom_report.modify_custom_event_group, endpoint="modify_custom_event_group"),
        ResourceRoute("POST", resource.custom_report.delete_custom_event_group, endpoint="delete_custom_event_group"),
        ResourceRoute("GET", resource.custom_report.query_custom_event_target, endpoint="query_custom_event_target"),
    ]


class CustomMetricReportViewSet(ResourceViewSet):
    query_post_actions = ["get_custom_report_dashboard_config"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS or self.action in self.query_post_actions:
            return [BusinessActionPermission([ActionEnum.VIEW_CUSTOM_METRIC])]
        return [BusinessActionPermission([ActionEnum.MANAGE_CUSTOM_METRIC])]

    resource_routes = [
        ResourceRoute("GET", resource.custom_report.custom_time_series_list, endpoint="custom_time_series"),
        # 自定义指标详情
        ResourceRoute("GET", resource.custom_report.custom_time_series_detail, endpoint="custom_time_series_detail"),
        # 校验自定义指标名称是否合法
        ResourceRoute(
            "GET", resource.custom_report.validate_custom_ts_group_name, endpoint="validate_custom_ts_group_name"
        ),
        # 校验自定义指标数据名称是否合法
        ResourceRoute(
            "GET", resource.custom_report.validate_custom_ts_group_label, endpoint="validate_custom_ts_group_label"
        ),
        # 创建自定义指标
        ResourceRoute("POST", resource.custom_report.create_custom_time_series, endpoint="create_custom_time_series"),
        # 修改自定义指标
        ResourceRoute("POST", resource.custom_report.modify_custom_time_series, endpoint="modify_custom_time_series"),
        # 删除自定义指标
        ResourceRoute("POST", resource.custom_report.delete_custom_time_series, endpoint="delete_custom_time_series"),
        # 添加自定义指标
        ResourceRoute("POST", resource.custom_report.add_custom_metric, endpoint="add_custom_metric"),
        # 指标字段 API
        ResourceRoute("GET", resource.custom_report.get_custom_ts_fields, endpoint="get_custom_ts_fields"),
        ResourceRoute("POST", resource.custom_report.modify_custom_ts_fields, endpoint="modify_custom_ts_fields"),
        ResourceRoute(
            "POST",
            resource.custom_report.import_custom_time_series_fields,
            endpoint="import_custom_time_series_fields",
        ),
        ResourceRoute(
            "GET",
            resource.custom_report.export_custom_time_series_fields,
            endpoint="export_custom_time_series_fields",
        ),
        # 分组规则 API
        # 创建或更新分组规则
        ResourceRoute(
            "POST", resource.custom_report.create_or_update_grouping_rule, endpoint="create_or_update_grouping_rule"
        ),
        # 自定义指标分组规则列表
        ResourceRoute(
            "GET", resource.custom_report.custom_ts_grouping_rule_list, endpoint="custom_ts_grouping_rule_list"
        ),
        # 预览分组规则
        ResourceRoute("POST", resource.custom_report.preview_grouping_rule, endpoint="preview_grouping_rule"),
        # 删除分组规则
        ResourceRoute("POST", resource.custom_report.delete_grouping_rule, endpoint="delete_grouping_rule"),
        # 更新分组规则排序
        ResourceRoute("POST", resource.custom_report.update_grouping_rule_order, endpoint="update_grouping_rule_order"),
        # 待删除API
        ResourceRoute(
            "POST",
            resource.custom_report.modify_custom_ts_grouping_rule_list,
            endpoint="modify_custom_ts_grouping_rule_list",
        ),
        ResourceRoute(
            "POST",
            resource.custom_report.get_custom_time_series_latest_data_by_fields,
            endpoint="get_custom_time_series_latest_data_by_fields",
        ),
        ResourceRoute(
            "POST", resource.custom_report.modify_custom_time_series_desc, endpoint="modify_custom_time_series_desc"
        ),
    ]
