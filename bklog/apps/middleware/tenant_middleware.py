import json

from django.utils.translation import gettext_lazy as _
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse

from apps.utils.local import get_local_username, get_request_username


class TenantValidationMiddleware(MiddlewareMixin):
    """
    租户校验中间件
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # 非多租户环境不用校验
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return None

        # api 请求豁免
        if settings.BKAPP_IS_BKLOG_API:
            return None

        if request.method in {"GET"}:
            bk_biz_id = request.GET.get("bk_biz_id")
            space_uid = request.GET.get("space_uid")
        else:
            raw_body = request.body

            try:
                body_data = json.loads(raw_body) if raw_body else {}
            except (ValueError, TypeError):
                # body 数据非 JSON 格式, 无从取 bk_biz_id 或 space_uid, 放行
                return None

            bk_biz_id = body_data.get("bk_biz_id")
            space_uid = body_data.get("space_uid")

        from apps.log_search.models import Space

        if bk_biz_id:
            bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id, is_need_default=False)
        elif space_uid:
            bk_tenant_id = Space.get_tenant_id(space_uid=space_uid, is_need_default=False)
        else:
            return None

        if not bk_tenant_id:
            return self.return_json_response(
                3600004,
                _("{tip}不存在: {id}").format(
                    tip="业务" if bk_biz_id else "空间", id=bk_biz_id if bk_biz_id else space_uid
                ),
            )

        user_model = get_user_model()
        username = get_request_username() or get_local_username()

        user_obj = user_model.objects.filter(username=username).first()

        if not user_obj:
            return self.return_json_response(3600007, _("用户不存在: {username}").format(username=username))

        if user_obj.tenant_id != bk_tenant_id:
            return self.return_json_response(
                3641001,
                _(
                    "您当前的企业空间是【{bk_tenant_id}】，无法访问该链接，请您尝试返回登录页面切换其他企业空间访问。"
                ).format(bk_tenant_id=bk_tenant_id),
            )

        return None

    @staticmethod
    def return_json_response(code, message, data=None, result=False):
        return JsonResponse(
            {
                "code": code,
                "message": message,
                "data": data,
                "result": result,
            },
            status=200,
        )
