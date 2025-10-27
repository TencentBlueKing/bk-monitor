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


class SceneViewViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]
        return [BusinessActionPermission([ActionEnum.VIEW_BUSINESS])]

    resource_routes = [
        ResourceRoute("GET", resource.scene_view.get_scene, endpoint="get_scene"),
        ResourceRoute("GET", resource.scene_view.get_scene_view, endpoint="get_scene_view"),
        ResourceRoute("GET", resource.scene_view.get_scene_view_list, endpoint="get_scene_view_list"),
        ResourceRoute("POST", resource.scene_view.update_scene_view, endpoint="update_scene_view"),
        ResourceRoute("POST", resource.scene_view.delete_scene_view, endpoint="delete_scene_view"),
        ResourceRoute(
            "POST",
            resource.scene_view.bulk_update_scene_view_order_and_name,
            endpoint="bulk_update_scene_view_order_and_name",
        ),
        ResourceRoute("GET", resource.scene_view.get_scene_view_dimensions, endpoint="get_scene_view_dimensions"),
        ResourceRoute(
            "POST", resource.scene_view.get_scene_view_dimension_value, endpoint="get_scene_view_dimension_value"
        ),
        ResourceRoute(
            "POST", resource.scene_view.get_strategy_and_event_count, endpoint="get_strategy_and_event_count"
        ),
        ResourceRoute(
            "POST", resource.scene_view.get_host_process_port_status, endpoint="get_host_process_port_status"
        ),
        ResourceRoute(
            "POST", resource.scene_view.get_host_or_topo_node_detail, endpoint="get_host_or_topo_node_detail"
        ),
        ResourceRoute("POST", resource.scene_view.get_host_process_uptime, endpoint="get_host_process_uptime"),
        ResourceRoute("POST", resource.scene_view.get_host_process_list, endpoint="get_host_process_list"),
        ResourceRoute(
            "POST", resource.scene_view.get_custom_event_target_list, endpoint="get_custom_event_target_list"
        ),
        ResourceRoute("POST", resource.scene_view.get_uptime_check_task_list, endpoint="get_uptime_check_task_list"),
        ResourceRoute("POST", resource.scene_view.get_uptime_check_task_info, endpoint="get_uptime_check_task_info"),
        ResourceRoute("POST", resource.scene_view.get_uptime_check_task_data, endpoint="get_uptime_check_task_data"),
        ResourceRoute("POST", resource.scene_view.get_uptime_check_var_list, endpoint="get_uptime_check_var_list"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_cluster_list, endpoint="get_kubernetes_cluster_list"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_cluster, endpoint="get_kubernetes_cluster"),
        ResourceRoute(
            "GET", resource.scene_view.get_kubernetes_cluster_choices, endpoint="get_kubernetes_cluster_choices"
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_usage_ratio, endpoint="get_kubernetes_usage_ratio"),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_workload_count_by_namespace,
            endpoint="get_kubernetes_workload_count_by_namespace",
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_pod, endpoint="get_kubernetes_pod"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_pod_list, endpoint="get_kubernetes_pod_list"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_service, endpoint="get_kubernetes_service"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_service_list, endpoint="get_kubernetes_service_list"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_container, endpoint="get_kubernetes_container"),
        ResourceRoute(
            "POST", resource.scene_view.get_kubernetes_container_list, endpoint="get_kubernetes_container_list"
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_workload, endpoint="get_kubernetes_workload"),
        ResourceRoute(
            "POST", resource.scene_view.get_kubernetes_workload_list, endpoint="get_kubernetes_workload_list"
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_node, endpoint="get_kubernetes_node"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_node_list, endpoint="get_kubernetes_node_list"),
        ResourceRoute(
            "POST", resource.scene_view.get_kubernetes_service_monitor, endpoint="get_kubernetes_service_monitor"
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_service_monitor_list,
            endpoint="get_kubernetes_service_monitor_list",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_service_monitor_endpoints,
            endpoint="get_kubernetes_service_monitor_endpoints",
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_pod_monitor, endpoint="get_kubernetes_pod_monitor"),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_pod_monitor_list,
            endpoint="get_kubernetes_pod_monitor_list",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_pod_monitor_endpoints,
            endpoint="get_kubernetes_pod_monitor_endpoints",
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_events, endpoint="get_kubernetes_events"),
        ResourceRoute(
            "POST", resource.scene_view.get_kubernetes_workload_types, endpoint="get_kubernetes_workload_types"
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_workload_status_list,
            endpoint="get_kubernetes_workload_status_list",
        ),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_namespaces, endpoint="get_kubernetes_namespaces"),
        ResourceRoute("POST", resource.scene_view.get_kubernetes_object_count, endpoint="get_kubernetes_object_count"),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_control_plane_status,
            endpoint="get_kubernetes_control_plane_status",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_workload_status,
            endpoint="get_kubernetes_workload_status",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_host_list,
            endpoint="get_host_list",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_host_info,
            endpoint="get_host_info",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_plugin_collect_config_id_list,
            endpoint="get_plugin_collect_config_id_list",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_observation_scene_list,
            endpoint="get_observation_scene_list",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_observation_scene_status_list,
            endpoint="get_observation_scene_status_list",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_plugin_target_topo,
            endpoint="get_plugin_target_topo",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_plugin_info_by_result_table,
            endpoint="get_plugin_by_result_table",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_consistency_check,
            endpoint="get_kubernetes_consistency_check",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_service_monitor_panels,
            endpoint="get_kubernetes_service_monitor_panels",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_pod_monitor_panels,
            endpoint="get_kubernetes_pod_monitor_panels",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_network_time_series,
            endpoint="get_kubernetes_network_time_series",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_pre_allocatable_usage_ratio,
            endpoint="get_kubernetes_pre_allocatable_usage_ratio",
        ),  # 事件
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_event_count_by_type,
            endpoint="get_kubernetes_event_count_by_type",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_event_count_by_event_name,
            endpoint="get_kubernetes_event_count_by_event_name",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_kubernetes_event_count_by_kind,
            endpoint="get_kubernetes_event_count_by_kind",
        ),
        ResourceRoute(
            "POST", resource.scene_view.get_kubernetes_event_time_series, endpoint="get_kubernetes_event_time_series"
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_cpu_analysis,
            endpoint="get_kubernetes_cpu_analysis",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_memory_analysis,
            endpoint="get_kubernetes_memory_analysis",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_disk_analysis,
            endpoint="get_kubernetes_disk_analysis",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_over_commit_analysis,
            endpoint="get_kubernetes_over_commit_analysis",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_node_cpu_usage,
            endpoint="get_kubernetes_node_cpu_usage",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_node_memory_usage,
            endpoint="get_kubernetes_node_memory_usage",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_node_disk_space_usage,
            endpoint="get_kubernetes_node_disk_space_usage",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_kubernetes_node_disk_io_usage,
            endpoint="get_kubernetes_node_disk_io_usage",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_index_set_log_series,
            endpoint="get_index_set_log_series",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.list_index_set_log,
            endpoint="list_index_set_log",
        ),
        ResourceRoute(
            "GET",
            resource.scene_view.get_custom_ts_metric_groups,
            endpoint="get_custom_ts_metric_groups",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_custom_ts_dimension_values,
            endpoint="get_custom_ts_dimension_values",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_custom_ts_graph_config,
            endpoint="get_custom_ts_graph_config",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.graph_drill_down,
            endpoint="graph_drill_down",
        ),
        ResourceRoute(
            "POST",
            resource.scene_view.get_custom_metric_target_list,
            endpoint="get_custom_metric_target_list",
        ),
    ]
