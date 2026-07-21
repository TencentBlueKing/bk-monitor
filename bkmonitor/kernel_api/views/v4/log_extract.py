"""Log extraction MCP API routes."""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_extract import (
    CreateLogExtractTaskMCPResource,
    GetLogExtractDownloadUrlMCPResource,
    GetLogExtractTaskMCPResource,
    SearchLogExtractFilesResource,
    SearchLogExtractHostsResource,
)


class LogExtractViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", SearchLogExtractHostsResource, endpoint="search_hosts"),
        ResourceRoute("POST", SearchLogExtractFilesResource, endpoint="search_files"),
        ResourceRoute("POST", CreateLogExtractTaskMCPResource, endpoint="create_task"),
        ResourceRoute("GET", GetLogExtractTaskMCPResource, endpoint="get_task"),
        ResourceRoute("POST", GetLogExtractDownloadUrlMCPResource, endpoint="get_download_url"),
    ]
