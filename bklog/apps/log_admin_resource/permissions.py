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
        app_code = auth_info["bk_app_code"]
        request.resource_app_code = app_code

        # DRF wraps the original Django request. UserLocalMiddleware stores that
        # original request in thread-local state, which is what asynchronous
        # inspection handlers use to bind task ownership. Keep the verified
        # identity on both request objects so the handler sees the same app that
        # passed the entry permission check.
        raw_request = getattr(request, "_request", None)
        if raw_request is not None:
            raw_request.resource_app_code = app_code

        return True
