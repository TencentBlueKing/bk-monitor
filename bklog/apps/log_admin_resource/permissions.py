from rest_framework import permissions

from apps.exceptions import PermissionError as BklogPermissionError
from apps.log_esquery.permission import Permission


class AdminResourceAppWhiteListPermission(permissions.BasePermission):
    """Require a trusted APIGW app identity; management elevation happens in the Registry."""

    def has_permission(self, request, view):
        jwt_info = getattr(request, "jwt", None)
        if not jwt_info or not getattr(jwt_info, "gateway_name", None):
            raise BklogPermissionError("admin resource call only accepts trusted APIGW requests")

        auth_info = Permission.get_auth_info(request, raise_exception=False)
        if not auth_info or not auth_info.get("bk_app_code"):
            raise BklogPermissionError("admin resource call requires a trusted APIGW app identity")

        # API 网关主动授权就是只读准入。这里只缓存已由鉴权链确认的应用身份；
        # Registry 再按管理白名单与 Handler safety_level 执行权限提升。
        request.resource_app_code = auth_info["bk_app_code"]

        return True
