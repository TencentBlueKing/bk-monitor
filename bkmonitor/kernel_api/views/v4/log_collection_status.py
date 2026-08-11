"""日志采集任务与订阅状态 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_status import GetLogCollectorStatusResource


class LogCollectionStatusViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", GetLogCollectorStatusResource, endpoint="get_status"),
    ]
