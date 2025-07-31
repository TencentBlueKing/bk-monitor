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
        if "HTTP_X_BKLOG_SPACE_UID" in request.META and "HTTP_X_BKLOG_TOKEN" in request.META:
            space_uid = request.META["HTTP_X_BKLOG_SPACE_UID"]
            token = request.META["HTTP_X_BKLOG_TOKEN"]
            try:
                record = ApiAuthToken.objects.get(token=token, space_uid=space_uid)
            except ApiAuthToken.DoesNotExist:
                record = None

            if not record:
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

        return super().process_view(request, view, *args, **kwargs)
