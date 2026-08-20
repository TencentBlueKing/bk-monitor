from django.conf import settings
from rest_framework import permissions

from apps.exceptions import PermissionError as BklogPermissionError
from apps.log_esquery.permission import Permission


class AdminResourceAppWhiteListPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        jwt_info = getattr(request, "jwt", None)
        if not jwt_info or not getattr(jwt_info, "gateway_name", None):
            raise BklogPermissionError("admin resource call only accepts APIGW requests from white-list apps")

        auth_info = Permission.get_auth_info(request, raise_exception=False)
        app_code = auth_info.get("bk_app_code") if auth_info else None
        if not app_code or app_code not in settings.ESQUERY_WHITE_LIST:
            raise BklogPermissionError("admin resource call only accepts APIGW requests from white-list apps")

        payload = request.data if isinstance(request.data, dict) else {}
        func_name = payload.get("func_name")
        from apps.log_admin_resource.registry import AdminResourceRegistry

        definition = AdminResourceRegistry.get_definition(func_name)
        if definition and definition.get("safety_level") in {"write", "destructive"}:
            if app_code not in settings.ADMIN_RESOURCE_WRITE_APP_WHITE_LIST:
                raise BklogPermissionError("admin resource mutation only accepts APIGW requests from write-list apps")

        return True
