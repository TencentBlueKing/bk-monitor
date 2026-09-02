"""日志采集清洗配置修改 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_clean_config import UpdateLogCollectorCleanConfigResource
from kernel_api.views.v4.log_collection_permissions import CanonicalBusinessActionPermission


class LogCollectionCleanConfigViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])]

    resource_routes = [
        ResourceRoute("POST", UpdateLogCollectorCleanConfigResource, endpoint="update_clean_config"),
    ]
