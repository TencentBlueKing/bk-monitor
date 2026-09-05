"""日志采集任务与订阅状态 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_status import GetLogCollectorStatusResource
from kernel_api.views.v4.log_collection_permissions import CanonicalBusinessActionPermission


class LogCollectionStatusViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.VIEW_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", GetLogCollectorStatusResource, endpoint="get_status"),
    ]
