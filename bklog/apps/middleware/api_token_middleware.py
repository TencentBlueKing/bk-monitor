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

        # 统一处理认证逻辑
        self._handle_authentication(request, record, token)
        return

    def _handle_authentication(self, request, record, token):
        """处理认证逻辑"""
        backend = "apps.middleware.api_token_middleware.ApiTokenAuthBackend"
        auth_type = record.type.lower()
        # 字典映射
        auth_handlers = {
            "grafana": self._handle_grafana_auth,
            "codecc": self._handle_codecc_auth,
        }

        handler = auth_handlers.get(auth_type, self._handle_default_auth)
        handler(request, record, backend, token)

    def _handle_grafana_auth(self, request, record, backend, token):
        """处理Grafana认证：替换请求用户为system并跳过权限检查"""
        user = auth.authenticate(username="system")
        auth.login(request, user, backend=backend)
        request.skip_check = True

    def _handle_codecc_auth(self, request, record, backend, token):
        """处理CodeCC认证：使用token创建者作为用户"""
        user = auth.authenticate(username=record.created_by)
        auth.login(request, user, backend=backend)
        request.token = token

    def _handle_default_auth(self, request, record, backend, token):
        """处理默认认证：仅设置token"""
        request.token = token
