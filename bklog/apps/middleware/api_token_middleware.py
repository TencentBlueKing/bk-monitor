from blueapps.account import get_user_model
from blueapps.account.middlewares import LoginRequiredMiddleware
from django.contrib import auth
from django.contrib.auth.backends import ModelBackend
from django.http import HttpResponseForbidden

from apps.log_commons.models import ApiAuthToken


class ApiTokenAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, **kwargs):
        if not username:
            return None
        try:
            user_model = get_user_model()
            user, _ = user_model.objects.get_or_create(username=username, defaults={"nickname": username})
        except Exception:
            return None
        return user


class ApiTokenAuthenticationMiddleware(LoginRequiredMiddleware):
    def process_view(self, request, view, *args, **kwargs):
        # 支持两种方式：1. 同时传 space_uid 和 token；2. 只传 token
        if "HTTP_X_BKLOG_TOKEN" not in request.META:
            return super().process_view(request, view, *args, **kwargs)

        token = request.META["HTTP_X_BKLOG_TOKEN"]

        # 构建查询条件
        query_kwargs = {"token": token}
        if "HTTP_X_BKLOG_SPACE_UID" in request.META:
            query_kwargs["space_uid"] = request.META["HTTP_X_BKLOG_SPACE_UID"]

        # 统一查询逻辑
        try:
            record = ApiAuthToken.objects.get(**query_kwargs)
        except ApiAuthToken.DoesNotExist:
            return HttpResponseForbidden("not valid token")

        if record.is_expired():
            return HttpResponseForbidden("token has expired")

        # grafana、as_code场景权限模式：替换请求用户为令牌创建者
        if record.type.lower() in ["grafana"]:
            user = auth.authenticate(username="system")
            auth.login(request, user, backend="apps.middleware.api_token_middleware.ApiTokenAuthBackend")
            request.skip_check = True
        # 新增 codecc_token 支持
        elif record.type.lower() == "codecc":
            request.codecc_token_info = {
                "token": record.token,
                "space_uid": record.space_uid,
                "index_set_id": record.params.get("index_set_id"),
                "params": record.params,
                "expire_time": record.expire_time,
            }
            return
        else:
            request.token = token
        return
