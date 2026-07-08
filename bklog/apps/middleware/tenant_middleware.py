import json

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.exceptions import TenantIdNotMatchException, UserNotExistsException
from apps.utils.local import get_local_username, get_request_username


class TenantValidationMiddleware(MiddlewareMixin):
    """
    租户校验中间件
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # 非多租户环境不用校验
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return None

        if request.method in {"GET"}:
            bk_biz_id = request.GET.get("bk_biz_id")
            space_uid = request.GET.get("space_uid")
        else:
            raw_body = request.body
            body_data = json.loads(raw_body) if raw_body else {}
            bk_biz_id = body_data.get("bk_biz_id")
            space_uid = body_data.get("space_uid")

        from apps.log_search.models import Space

        if bk_biz_id:
            bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id, is_exception=True)
        elif space_uid:
            bk_tenant_id = Space.get_tenant_id(space_uid=space_uid, is_exception=True)
        else:
            return None

        user_model = get_user_model()
        username = get_request_username() or get_local_username()

        user_obj = user_model.objects.filter(username=username).first()

        if not user_obj:
            raise UserNotExistsException(UserNotExistsException.MESSAGE.format(username=username))

        if user_obj.tenant_id != bk_tenant_id:
            raise TenantIdNotMatchException(TenantIdNotMatchException.MESSAGE.format(bk_tenant_id=bk_tenant_id))

        return None
