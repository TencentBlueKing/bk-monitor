from blueapps.account.decorators import login_exempt

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class BkGseSlotViewSet(ResourceViewSet):
    """
    GSE消息槽回调接口
    """

    resource_routes = [
        ResourceRoute("POST", resource.metadata.gse_slot, decorators=[login_exempt]),
    ]
