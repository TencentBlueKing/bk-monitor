"""日志采集清洗配置修改 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_clean_config import UpdateLogCollectorCleanConfigResource


class CanonicalBusinessActionPermission(BusinessActionPermission):
    """权限业务必须与实际提交的 bk_biz_id 一致。"""

    def has_permission(self, request, view):
        request_data = request.query_params if request.method == "GET" else request.data
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


class LogCollectionCleanConfigViewSet(ResourceViewSet):
    def get_permissions(self):
        return [CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])]

    resource_routes = [
        ResourceRoute("POST", UpdateLogCollectorCleanConfigResource, endpoint="update_clean_config"),
    ]
