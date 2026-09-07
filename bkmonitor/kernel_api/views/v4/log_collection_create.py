"""日志采集 Fast Create MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_create import FastCreateLogCollectorResource
from kernel_api.resource.log_collection_special_create import (
    CreateBkDataResource,
    CreateCustomReportResource,
    CreateThirdPartyESResource,
)
from kernel_api.views.v4.log_collection_permissions import CanonicalBusinessActionPermission


class LogCollectionCreateViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.MANAGE_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", FastCreateLogCollectorResource, endpoint="fast_create"),
        ResourceRoute("POST", CreateCustomReportResource, endpoint="create_custom_report"),
        ResourceRoute("POST", CreateThirdPartyESResource, endpoint="create_third_party_es"),
        ResourceRoute("POST", CreateBkDataResource, endpoint="create_bkdata_index_set"),
    ]
