"""日志采集接入 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection import (
    GetLogCollectorResource,
    GetLogIndexSetResource,
    ListLogCollectorsResource,
)
from kernel_api.resource.log_index_set import ListLogIndexSetGroupsResource
from kernel_api.views.v4.log_collection_permissions import (
    CanonicalBusinessActionPermission as BaseCanonicalBusinessActionPermission,
)


class CanonicalBusinessActionPermission(BaseCanonicalBusinessActionPermission):
    request_data_source = "query"


class LogCollectionViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])]

    resource_routes = [
        ResourceRoute("GET", ListLogCollectorsResource, endpoint="list_collectors"),
        ResourceRoute("GET", GetLogCollectorResource, endpoint="get_collector"),
        ResourceRoute("GET", GetLogIndexSetResource, endpoint="get_index_set"),
        ResourceRoute("GET", ListLogIndexSetGroupsResource, endpoint="list_index_set_groups"),
    ]
