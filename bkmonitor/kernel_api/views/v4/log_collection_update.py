"""日志采集 Fast Update MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_update import FastUpdateLogCollectorResource
from kernel_api.resource.log_collection_special_update import (
    UpdateCustomReportResource,
    UpdateThirdPartyESResource,
)


class LogCollectionUpdateViewSet(ResourceViewSet):
    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.MANAGE_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", FastUpdateLogCollectorResource, endpoint="fast_update"),
        ResourceRoute("POST", UpdateCustomReportResource, endpoint="update_custom_report"),
        ResourceRoute("POST", UpdateThirdPartyESResource, endpoint="update_third_party_es"),
    ]
