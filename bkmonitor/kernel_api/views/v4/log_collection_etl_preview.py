"""日志清洗结果预览 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_etl_preview import PreviewLogEtlResource


class EtlPreviewBusinessActionPermission(BusinessActionPermission):
    """权限校验业务必须与请求体实际预览业务一致。"""

    def has_permission(self, request, view):
        canonical_biz_id = request.data.get("bk_biz_id")
        if canonical_biz_id is not None:
            query_biz_id = request.query_params.get("bk_biz_id")
            if query_biz_id is not None and str(query_biz_id) != str(canonical_biz_id):
                return False
            request_biz_id = getattr(request, "biz_id", None)
            if request_biz_id is not None and str(request_biz_id) != str(canonical_biz_id):
                return False
            request.biz_id = canonical_biz_id
        return super().has_permission(request, view)


class LogCollectionEtlPreviewViewSet(ResourceViewSet):
    def get_permissions(self):
        return [EtlPreviewBusinessActionPermission([ActionEnum.VIEW_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", PreviewLogEtlResource, endpoint="preview"),
    ]
