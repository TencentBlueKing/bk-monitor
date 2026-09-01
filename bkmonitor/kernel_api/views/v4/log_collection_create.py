"""日志采集 Fast Create MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_create import FastCreateLogCollectorResource
from kernel_api.resource.log_collection_special_create import (
    CreateBkDataResource,
    CreateCustomReportResource,
    CreateThirdPartyESResource,
)


class CanonicalBusinessActionPermission(BusinessActionPermission):
    """权限业务必须与创建资源实际使用的 bk_biz_id 一致。"""

    def has_permission(self, request, view):
        request_data = request.data if hasattr(request.data, "get") else {}
        canonical_biz_id = request_data.get("bk_biz_id")
        if canonical_biz_id is not None:
            for alias in ("biz_id", "business_id"):
                alias_biz_id = request_data.get(alias)
                if alias_biz_id is not None and str(alias_biz_id) != str(canonical_biz_id):
                    return False
            request_biz_id = getattr(request, "biz_id", None)
            if request_biz_id is not None and str(request_biz_id) != str(canonical_biz_id):
                return False
            request.biz_id = canonical_biz_id
        return super().has_permission(request, view)


class LogCollectionCreateViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])]

    resource_routes = [
        ResourceRoute("POST", FastCreateLogCollectorResource, endpoint="fast_create"),
        ResourceRoute("POST", CreateCustomReportResource, endpoint="create_custom_report"),
        ResourceRoute("POST", CreateThirdPartyESResource, endpoint="create_third_party_es"),
        ResourceRoute("POST", CreateBkDataResource, endpoint="create_bkdata_index_set"),
    ]
