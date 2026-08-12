"""日志采集接入 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection import GetLogCollectorResource, ListLogCollectorsResource


class CanonicalBusinessActionPermission(BusinessActionPermission):
    """权限业务必须与资源实际使用的 bk_biz_id 一致。"""

    def has_permission(self, request, view):
        canonical_biz_id = request.query_params.get("bk_biz_id")
        if canonical_biz_id is not None:
            for alias in ("biz_id", "business_id"):
                alias_biz_id = request.query_params.get(alias)
                if alias_biz_id is not None and str(alias_biz_id) != str(canonical_biz_id):
                    return False
            request_biz_id = getattr(request, "biz_id", None)
            if request_biz_id is not None and str(request_biz_id) != str(canonical_biz_id):
                return False
            request.biz_id = canonical_biz_id
        return super().has_permission(request, view)


class LogCollectionViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.VIEW_COLLECTION])]

    resource_routes = [
        ResourceRoute("GET", ListLogCollectorsResource, endpoint="list_collectors"),
        ResourceRoute("GET", GetLogCollectorResource, endpoint="get_collector"),
    ]
