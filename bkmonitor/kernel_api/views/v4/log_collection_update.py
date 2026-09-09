"""日志采集 Fast Update MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_update import FastUpdateLogCollectorResource
from kernel_api.resource.log_collection_special_update import (
    UpdateBkDataResource,
    UpdateCustomReportResource,
    UpdateThirdPartyESResource,
)
from kernel_api.views.v4.log_collection_permissions import CanonicalBusinessActionPermission


class LogCollectionUpdateViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.MANAGE_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", FastUpdateLogCollectorResource, endpoint="fast_update"),
        ResourceRoute("POST", UpdateCustomReportResource, endpoint="update_custom_report"),
        ResourceRoute("POST", UpdateThirdPartyESResource, endpoint="update_third_party_es"),
        ResourceRoute("POST", UpdateBkDataResource, endpoint="update_bkdata_index_set"),
    ]
