"""Separate the seven shared read backends from their application API routes.

The application URLs keep their existing callbacks and scope checks. Only the
dedicated MCP URLs enter the user ToolRegistry; a user JWT must not downgrade to
application authorization by selecting the original URL or removing MCP headers.
"""

import re

MCP_READ_PREFIX = "/api/v4/mcp/"

APPLICATION_READ_BACKENDS = {
    "get_alert_info": ("GET", "/api/v4/alert/alert/detail/"),
    "list_time_series_metrics": ("GET", "/api/v3/meta/get_time_series_metrics/"),
    "search_spaces": ("GET", "/api/v3/meta/list_spaces/"),
    "get_dashboard_tree_list": ("GET", "/api/v4/grafana/get_directory_tree/"),
    "get_dashboard_detail_by_uid": ("GET", "/api/v4/grafana/get_dashboard_detail/"),
    "list_apm_services": ("POST", "/api/v4/service_web/service_list/"),
    "calculate_by_range": ("POST", "/api/v4/apm_metric_web/calculate_by_range/"),
}


def is_application_read_route(method: str, path: str) -> bool:
    # DRF routers accept any lowercase alphanumeric format suffix, not just JSON.
    # Cover every route alias here so none can downgrade user authentication.
    method = "GET" if method.upper() == "HEAD" else method.upper()
    path = re.sub(r"\.[a-z0-9]+$", "", path.rstrip("/")) + "/"
    return (method, path) in APPLICATION_READ_BACKENDS.values()
