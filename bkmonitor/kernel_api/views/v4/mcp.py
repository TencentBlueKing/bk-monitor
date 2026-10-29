"""User MCP read endpoints; application APIs retain their original backend URLs."""

from apm_web.metric.resources import CalculateByRangeResource
from apm_web.service.resources import ServiceListResource

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from metadata.resources import GetTimeSeriesMetricsResource, ListSpacesResource
from monitor_web.grafana.resources.manage import GetDashboardDetail, GetDirectoryTree


class MCPViewSet(ResourceViewSet):
    # AuthenticationMiddleware resolves these routes through the same YAML tool
    # catalog as Unified MCP and executes its user/resource permission checks.
    resource_routes = [
        ResourceRoute("GET", resource.alert.alert_detail, endpoint="get_alert_info"),
        ResourceRoute("GET", GetTimeSeriesMetricsResource, endpoint="list_time_series_metrics"),
        ResourceRoute("GET", ListSpacesResource, endpoint="search_spaces"),
        ResourceRoute("GET", GetDirectoryTree, endpoint="get_dashboard_tree_list"),
        ResourceRoute("GET", GetDashboardDetail, endpoint="get_dashboard_detail_by_uid"),
        ResourceRoute("POST", ServiceListResource, endpoint="list_apm_services"),
        ResourceRoute("POST", CalculateByRangeResource, endpoint="calculate_by_range"),
    ]
