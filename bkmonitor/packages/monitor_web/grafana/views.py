"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework.authentication import SessionAuthentication

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.middlewares.authentication import NoCsrfSessionAuthentication
from core.drf_resource import api, resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.grafana.permissions import (
    GrafanaReadPermission,
    GrafanaWritePermission,
)


class GrafanaViewSet(ResourceViewSet):
    """
    时序数据DataSource
    """

    def get_authenticators(self):
        authenticators = super().get_authenticators()
        authenticators = [
            authenticator for authenticator in authenticators if not isinstance(authenticator, SessionAuthentication)
        ]
        authenticators.append(NoCsrfSessionAuthentication())
        return authenticators

    def get_permissions(self):
        if self.action == "save_to_dashboard":
            return [GrafanaWritePermission()]

        if self.action in [
            "time_series/query",
            "time_series/unify_query",
            "time_series/unify_query_raw",
            "time_series/dimension_query",
            "time_series/functions",
            "time_series/dimension_count",
            "bk_log_search/grafana/query",
            "bk_log_search/grafana/query_log",
            "bk_log_search/grafana/get_variable_value",
        ]:
            return [
                GrafanaReadPermission(
                    BusinessActionPermission(
                        [
                            ActionEnum.VIEW_HOST,
                            ActionEnum.VIEW_COLLECTION,
                            ActionEnum.EXPLORE_METRIC,
                            ActionEnum.VIEW_RULE,
                        ]
                    )
                ),
            ]

        return [GrafanaReadPermission()]

    resource_routes = [
        # 插件接口
        ResourceRoute("GET", resource.grafana.test),
        ResourceRoute("POST", api.log_search.bk_log_search_query, endpoint="bk_log_search/grafana/query"),
        ResourceRoute("GET", api.log_search.bk_log_search_metric, endpoint="bk_log_search/grafana/metric"),
        ResourceRoute("GET", api.log_search.bk_log_search_dimension, endpoint="bk_log_search/grafana/dimension"),
        ResourceRoute("GET", api.log_search.bk_log_search_target_tree, endpoint="bk_log_search/grafana/target_tree"),
        ResourceRoute("POST", api.log_search.bk_log_search_query_log, endpoint="bk_log_search/grafana/query_log"),
        ResourceRoute(
            "GET", api.log_search.bk_log_search_get_variable_field, endpoint="bk_log_search/grafana/get_variable_field"
        ),
        ResourceRoute(
            "POST", api.log_search.bk_log_search_get_variable_value, endpoint="bk_log_search/grafana/get_variable_value"
        ),
        ResourceRoute("GET", resource.commons.get_label, endpoint="get_label"),
        ResourceRoute("GET", resource.commons.get_topo_tree, endpoint="topo_tree"),
        ResourceRoute(
            "POST", resource.strategies.get_metric_list_v2, endpoint="get_metric_list", content_encoding="gzip"
        ),
        ResourceRoute("GET", resource.grafana.get_data_source_config, endpoint="get_data_source_config"),
        ResourceRoute("POST", resource.grafana.get_variable_value, endpoint="get_variable_value"),
        ResourceRoute("GET", resource.grafana.get_variable_field, endpoint="get_variable_field"),
        ResourceRoute(
            "POST", resource.grafana.time_series_metric, endpoint="time_series/metric", content_encoding="gzip"
        ),
        ResourceRoute("GET", resource.grafana.get_related_strategy, endpoint="get_related_strategy"),
        ResourceRoute("POST", resource.grafana.time_series_metric_level, endpoint="time_series/metric_level"),
        ResourceRoute("POST", resource.grafana.log_query, endpoint="log/query"),
        # 设置默认仪表盘
        ResourceRoute("GET", resource.grafana.get_dashboard_list, endpoint="dashboards"),
        ResourceRoute("POST", resource.grafana.set_default_dashboard, endpoint="set_default_dashboard"),
        ResourceRoute("GET", resource.grafana.get_default_dashboard, endpoint="get_default_dashboard"),
        # 仪表盘管理
        ResourceRoute("GET", resource.grafana.get_directory_tree, endpoint="get_directory_tree"),
        ResourceRoute("POST", resource.grafana.create_dashboard_or_folder, endpoint="create_dashboard_or_folder"),
        ResourceRoute("DELETE", resource.grafana.delete_dashboard, endpoint="delete_dashboard"),
        ResourceRoute("POST", resource.grafana.star_dashboard, endpoint="star_dashboard"),
        ResourceRoute("DELETE", resource.grafana.unstar_dashboard, endpoint="unstar_dashboard"),
        ResourceRoute("DELETE", resource.grafana.delete_folder, endpoint="delete_folder"),
        ResourceRoute("PUT", resource.grafana.rename_folder, endpoint="rename_folder"),
        ResourceRoute("POST", resource.grafana.quick_import_dashboard, endpoint="quick_import_dashboard"),
        ResourceRoute("POST", resource.grafana.copy_dashboard_to_folder, endpoint="copy_dashboard_to_folder"),
        ResourceRoute("POST", resource.grafana.migrate_old_panels, endpoint="migrate_old_panels"),
        ResourceRoute("POST", resource.grafana.migrate_old_panels_by_biz, endpoint="migrate_old_panels_by_biz"),
        ResourceRoute("POST", resource.grafana.migrate_panels_info, endpoint="migrate_panels_info"),
        ResourceRoute("POST", resource.data_explorer.save_to_dashboard, endpoint="save_to_dashboard"),
        # 统一数据查询
        ResourceRoute("GET", resource.grafana.get_functions, endpoint="time_series/functions"),
        ResourceRoute(
            "POST", resource.grafana.graph_unify_query, endpoint="time_series/unify_query", content_encoding="gzip"
        ),
        ResourceRoute(
            "POST", resource.grafana.unify_query_raw, endpoint="time_series/unify_query_raw", content_encoding="gzip"
        ),
        ResourceRoute("POST", resource.grafana.dimension_unify_query, endpoint="time_series/dimension_query"),
        ResourceRoute("POST", resource.grafana.dimension_count_unify_query, endpoint="time_series/dimension_count"),
        # 查询配置转换为PromQL
        ResourceRoute("POST", resource.strategies.query_config_to_promql, endpoint="query_config_to_promql"),
        # PromQL转为查询配置
        ResourceRoute("POST", resource.strategies.promql_to_query_config, endpoint="promql_to_query_config"),
        # PromQL原生查询
        ResourceRoute("POST", resource.grafana.graph_promql_query, endpoint="graph_promql_query"),
        ResourceRoute("POST", resource.grafana.dimension_promql_query, endpoint="dimension_promql_query"),
        ResourceRoute("POST", resource.grafana.get_drill_dimensions, endpoint="get_drill_dimensions"),
        ResourceRoute(
            "POST", resource.grafana.convert_grafana_promql_dashboard, endpoint="convert_grafana_promql_dashboard"
        ),
        ResourceRoute(
            "POST",
            resource.grafana.graph_trace_query,
            endpoint="time_series/unify_trace_query",
            content_encoding="gzip",
        ),
        ResourceRoute("POST", resource.strategies.update_metric_list_by_biz, endpoint="update_metric_list_by_biz"),
        ResourceRoute("GET", resource.commons.query_async_task_result, endpoint="query_async_task_result"),
        # 添加自定义指标
        ResourceRoute("POST", resource.custom_report.add_custom_metric, endpoint="add_custom_metric"),
        # 告警事件查询
        ResourceRoute("POST", resource.grafana.query_alarm_event_graph, endpoint="query_alarm_event_graph"),
        ResourceRoute("GET", resource.grafana.get_alarm_event_field, endpoint="get_alarm_event_field"),
        ResourceRoute(
            "GET", resource.grafana.get_alarm_event_dimension_value, endpoint="get_alarm_event_dimension_value"
        ),
        # Trace panel
        ResourceRoute("POST", resource.grafana.list_application_info, endpoint="apm/list_application_info"),
        ResourceRoute("POST", resource.grafana.get_field_option_values, endpoint="apm/get_field_option_values"),
        ResourceRoute("POST", resource.grafana.list_trace, endpoint="apm/list_trace"),
        ResourceRoute("POST", resource.grafana.trace_detail, endpoint="apm/trace_detail"),
        # profile 查询
        ResourceRoute("POST", resource.apm_web.grafana_query_profile, endpoint="query_graph_profile"),
        # 应用服务列表
        ResourceRoute("GET", resource.apm_web.list_application_services, endpoint="get_profile_application_service"),
        # profile 数据类型
        ResourceRoute("GET", resource.apm_web.query_services_detail, endpoint="get_profile_type"),
        # profile label
        ResourceRoute("GET", resource.apm_web.grafana_query_profile_label, endpoint="get_profile_label"),
        # profile label_values
        ResourceRoute("GET", resource.apm_web.grafana_query_profile_label_values, endpoint="get_profile_label_values"),
        # 获取仪表盘图表关联的策略
        ResourceRoute("POST", resource.grafana.get_related_strategy, endpoint="get_related_strategy"),
    ]
