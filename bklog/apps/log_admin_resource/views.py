from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_admin_resource.permissions import AdminResourceAppWhiteListPermission
from apps.log_admin_resource.registry import AdminResourceRegistry, wrap_result
from apps.utils.drf import list_route


class AdminResourceViewSet(APIViewSet):
    permission_classes = (AdminResourceAppWhiteListPermission,)

    @list_route(methods=["POST"], url_path="call")
    def call(self, request):
        func_name = request.data.get("func_name")
        params = request.data.get("params") or {}
        result = AdminResourceRegistry.call(func_name=func_name, params=params)
        return Response(wrap_result(func_name=func_name, result=result))
