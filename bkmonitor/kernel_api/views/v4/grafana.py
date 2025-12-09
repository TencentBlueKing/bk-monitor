from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.grafana import (
    KernelUnifyQueryRawResource,
    KernelGraphUnifyQueryResource,
    CreateDashboardResource,
    UpdateDashboardResource,
)


class GrafanaViewSet(ResourceViewSet):
    """
    Grafana API
    """

    resource_routes = [
        ResourceRoute(
            "POST", resource.grafana.time_series_metric, endpoint="time_series/metric", content_encoding="gzip"
        ),
        ResourceRoute("GET", resource.grafana.get_functions, endpoint="time_series/functions"),
        ResourceRoute("POST", resource.grafana.get_variable_value, endpoint="get_variable_value"),
        ResourceRoute("GET", resource.grafana.get_variable_field, endpoint="get_variable_field"),
        ResourceRoute("POST", resource.grafana.time_series_metric_level, endpoint="time_series/metric_level"),
        ResourceRoute(
            "POST", KernelGraphUnifyQueryResource(), endpoint="time_series/unify_query", content_encoding="gzip"
        ),
        # 创建仪表盘（MCP）- 不覆盖同名配置
        ResourceRoute("POST", CreateDashboardResource, endpoint="create_dashboard"),
        # 更新仪表盘（MCP）- 覆盖同名配置
        ResourceRoute("POST", UpdateDashboardResource, endpoint="update_dashboard"),
        ResourceRoute(
            "POST", KernelUnifyQueryRawResource(), endpoint="time_series/unify_query_raw", content_encoding="gzip"
        ),
        ResourceRoute("POST", resource.grafana.graph_promql_query, endpoint="graph_promql_query"),
        ResourceRoute(
            "POST",
            resource.grafana.graph_trace_query,
            endpoint="time_series/unify_query_trace",
            content_encoding="gzip",
        ),
        ResourceRoute("POST", resource.grafana.log_query, endpoint="log/query"),
        # 告警事件查询
        ResourceRoute("POST", resource.grafana.query_alarm_event_graph, endpoint="query_alarm_event_graph"),
        ResourceRoute("GET", resource.grafana.get_alarm_event_field, endpoint="get_alarm_event_field"),
        ResourceRoute(
            "GET", resource.grafana.get_alarm_event_dimension_value, endpoint="get_alarm_event_dimension_value"
        ),
        # 仪表盘管理
        ResourceRoute("GET", resource.grafana.get_directory_tree, endpoint="get_directory_tree"),
        ResourceRoute("POST", resource.grafana.quick_import_dashboard, endpoint="quick_import_dashboard"),
        ResourceRoute("GET", resource.grafana.get_dashboard_detail, endpoint="get_dashboard_detail"),
        ResourceRoute("POST", resource.grafana.create_dashboard_or_folder, endpoint="create_dashboard_or_folder"),
        ResourceRoute("DELETE", resource.grafana.delete_dashboard, endpoint="delete_dashboard"),
        ResourceRoute("POST", resource.grafana.star_dashboard, endpoint="star_dashboard"),
        ResourceRoute("DELETE", resource.grafana.unstar_dashboard, endpoint="unstar_dashboard"),
        ResourceRoute("DELETE", resource.grafana.delete_folder, endpoint="delete_folder"),
        ResourceRoute("PUT", resource.grafana.rename_folder, endpoint="rename_folder"),
        ResourceRoute("POST", resource.data_explorer.save_to_dashboard, endpoint="save_to_dashboard"),
    ]
