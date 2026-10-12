"""日志清洗结果预览 MCP 接口路由。"""

from bkmonitor.iam import ActionEnum
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.log_collection_etl_preview import PreviewLogEtlResource
from kernel_api.views.v4.log_collection_permissions import CanonicalBusinessActionPermission


class EtlPreviewBusinessActionPermission(CanonicalBusinessActionPermission):
    check_query_biz_id = True


class LogCollectionEtlPreviewViewSet(ResourceViewSet):
    def get_permissions(self):
        return [EtlPreviewBusinessActionPermission([ActionEnum.VIEW_COLLECTION])]

    resource_routes = [
        ResourceRoute("POST", PreviewLogEtlResource, endpoint="preview"),
    ]
