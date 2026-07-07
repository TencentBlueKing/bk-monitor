from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

from apps.exceptions import TenantIdIsNoneError, TenantIdNotMatchError, UserNotExistsError


class TenantValidationMiddleware(MiddlewareMixin):
    """
    租户校验中间件
    """

    # 豁免路径
    exempt_paths = [
        "/api/v1/health",
        "/api/v1/metrics",
        "/static/",
        "/media/",
    ]

    def process_view(self, request, view_func, view_args, view_kwargs):
        # 非多租户环境不用校验
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return None

        # 跳过豁免路径
        if any(request.path.startswith(p) for p in self.exempt_paths):
            return None

        # 获取请求中的空间租户ID
        bk_tenant_id = request.META.get("HTTP_X_BK_TENANT_ID", "")

        if not bk_tenant_id:
            raise TenantIdIsNoneError()

        from django.contrib.auth import get_user_model
        from apps.utils.local import get_request as get_current_request

        request = get_current_request(peaceful=True)
        user_model = get_user_model()

        user_obj = user_model.objects.filter(username=request.user.username).first()

        if not user_obj:
            raise UserNotExistsError(UserNotExistsError.MESSAGE.format(username=user_obj.username))

        if user_obj.tenant_id != bk_tenant_id:
            raise TenantIdNotMatchError(TenantIdNotMatchError.MESSAGE.format(bk_tenant_id=bk_tenant_id))

        return None
