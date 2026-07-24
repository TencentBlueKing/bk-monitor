"""日志提取 MCP 接口路由。"""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_extract import (
    CreateLogExtractTaskResource,
    GetLogExtractDownloadUrlResource,
    GetLogExtractTaskResource,
    ListLogExtractAllowedPathsResource,
    ListLogExtractTopologyResource,
    SearchLogExtractFilesResource,
    SearchLogExtractHostsResource,
)


class LogExtractViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", ListLogExtractTopologyResource, endpoint="topology"),
        ResourceRoute("POST", SearchLogExtractHostsResource, endpoint="search_hosts"),
        ResourceRoute("POST", ListLogExtractAllowedPathsResource, endpoint="allowed_paths"),
        ResourceRoute("POST", SearchLogExtractFilesResource, endpoint="search_files"),
        ResourceRoute("POST", CreateLogExtractTaskResource, endpoint="create_task"),
        ResourceRoute("GET", GetLogExtractTaskResource, endpoint="get_task"),
        ResourceRoute("POST", GetLogExtractDownloadUrlResource, endpoint="get_download_url"),
    ]
