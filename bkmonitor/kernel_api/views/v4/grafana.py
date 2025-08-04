from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.grafana import KernelUnifyQueryRawResource, KernelGraphUnifyQueryResource


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
        ResourceRoute("POST", resource.grafana.quick_import_dashboard, endpoint="quick_import_dashboard"),
        ResourceRoute("POST", resource.grafana.log_query, endpoint="log/query"),
        ResourceRoute("GET", resource.grafana.get_directory_tree, endpoint="get_directory_tree"),
        ResourceRoute("GET", resource.grafana.get_dashboard_detail, endpoint="get_dashboard_detail"),
        ResourceRoute("GET", resource.grafana.get_data_source_config, endpoint="get_data_source_config"),
    ]
