from rest_framework.response import Response

from apps.exceptions import PermissionError as BklogPermissionError
from apps.generic import APIViewSet
from apps.log_admin_resource.registry import AdminResourceRegistry, wrap_result
from apps.utils.drf import list_route


class AdminResourceViewSet(APIViewSet):
    @staticmethod
    def _is_apigw_request(request):
        jwt_info = getattr(request, "jwt", None)
        return bool(jwt_info and getattr(jwt_info, "gateway_name", None))

    @list_route(methods=["POST"], url_path="call")
    def call(self, request):
        if not self._is_apigw_request(request):
            raise BklogPermissionError("admin resource call only accepts APIGW requests")

        func_name = request.data.get("func_name")
        params = request.data.get("params") or {}
        result = AdminResourceRegistry.call(func_name=func_name, params=params)
        return Response(wrap_result(func_name=func_name, result=result))
