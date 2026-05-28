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
        if not auth_info or auth_info["bk_app_code"] not in settings.ESQUERY_WHITE_LIST:
            raise BklogPermissionError("admin resource call only accepts APIGW requests from white-list apps")

        return True
