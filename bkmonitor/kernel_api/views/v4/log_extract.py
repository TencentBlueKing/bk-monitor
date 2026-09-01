"""日志提取 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
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
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.USING_LOG_EXTRACT_MCP])]

    resource_routes = [
        ResourceRoute("POST", ListLogExtractTopologyResource, endpoint="topology"),
        ResourceRoute("POST", SearchLogExtractHostsResource, endpoint="search_hosts"),
        ResourceRoute("POST", ListLogExtractAllowedPathsResource, endpoint="allowed_paths"),
        ResourceRoute("POST", SearchLogExtractFilesResource, endpoint="search_files"),
        ResourceRoute("POST", CreateLogExtractTaskResource, endpoint="create_task"),
        ResourceRoute("GET", GetLogExtractTaskResource, endpoint="get_task"),
        ResourceRoute("POST", GetLogExtractDownloadUrlResource, endpoint="get_download_url"),
    ]
