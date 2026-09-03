from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_admin_resource.permissions import AdminResourceAppWhiteListPermission
from apps.log_admin_resource.registry import AdminResourceRegistry, wrap_result
from apps.utils.drf import list_route
from apps.utils.local import get_request_id


class AdminResourceViewSet(APIViewSet):
    permission_classes = (AdminResourceAppWhiteListPermission,)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["X-Request-Id"] = getattr(request, "request_id", None) or get_request_id()
        return response

    @list_route(methods=["POST"], url_path="call")
    def call(self, request):
        func_name = request.data.get("func_name")
        params = request.data.get("params") or {}
        result = AdminResourceRegistry.call(
            func_name=func_name,
            params=params,
            app_code=getattr(request, "resource_app_code", None),
        )
        return Response(wrap_result(func_name=func_name, result=result))
