from django.conf import settings
from rest_framework.response import Response

from apps.exceptions import PermissionError as BklogPermissionError
from apps.generic import APIViewSet
from apps.log_admin_resource.registry import AdminResourceRegistry, wrap_result
from apps.log_esquery.permission import Permission
from apps.utils.drf import list_route


class AdminResourceViewSet(APIViewSet):
    @staticmethod
    def _is_apigw_request(request):
        jwt_info = getattr(request, "jwt", None)
        return bool(jwt_info and getattr(jwt_info, "gateway_name", None))

    @classmethod
    def _is_white_list_apigw_request(cls, request):
        if not cls._is_apigw_request(request):
            return False

        auth_info = Permission.get_auth_info(request, raise_exception=False)
        return bool(auth_info and auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST)

    @list_route(methods=["POST"], url_path="call")
    def call(self, request):
        if not self._is_white_list_apigw_request(request):
            raise BklogPermissionError("admin resource call only accepts APIGW requests from white-list apps")

        func_name = request.data.get("func_name")
        params = request.data.get("params") or {}
        result = AdminResourceRegistry.call(func_name=func_name, params=params)
        return Response(wrap_result(func_name=func_name, result=result))
