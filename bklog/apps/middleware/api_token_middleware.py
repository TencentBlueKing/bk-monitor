import json

from blueapps.account import get_user_model
from blueapps.account.middlewares import LoginRequiredMiddleware
from django.contrib import auth
from django.contrib.auth.backends import ModelBackend
from django.http import HttpResponseForbidden

from apps.log_commons.models import ApiAuthToken
from bkm_space.utils import bk_biz_id_to_space_uid


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
        token = request.META.get("HTTP_X_BKLOG_TOKEN")
        if not token:
            return super().process_view(request, view, *args, **kwargs)

        # 构建查询条件
        query_kwargs = {"token": token}
        space_uid = request.META.get("HTTP_X_BKLOG_SPACE_UID")
        if space_uid:
            query_kwargs["space_uid"] = space_uid

        record = ApiAuthToken.objects.filter(**query_kwargs).first()
        if not record:
            return HttpResponseForbidden("not valid token")
        if record.is_expired():
            return HttpResponseForbidden("token has expired")
        if not self._is_view_allowed(view, record):
            return HttpResponseForbidden("token not allowed for this view")
        if not self._is_biz_allowed(request, record):
            return HttpResponseForbidden("token not allowed for this business")

        # 统一处理认证逻辑
        self._handle_authentication(request, record, token)
        return

    @staticmethod
    def _is_view_allowed(view, record):
        """Grafana 类型 token 限定只能访问 grafana 视图"""
        if record.type.lower() != "grafana":
            return True
        view_cls = getattr(view, "cls", None)
        return getattr(view_cls, "__module__", "") == "apps.grafana.views"

    @staticmethod
    def _get_request_biz_id(request):
        """从查询参数或 JSON 请求体中获取 bk_biz_id"""
        biz_id = request.GET.get("bk_biz_id") or request.POST.get("bk_biz_id")
        if biz_id:
            return biz_id
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        try:
            body = json.loads(request.body or b"{}")
        except (TypeError, ValueError):
            return None
        return body.get("bk_biz_id") if isinstance(body, dict) else None

    @classmethod
    def _is_biz_allowed(cls, request, record):
        """校验请求业务与 token 绑定空间一致，避免跨业务访问"""
        if not record.space_uid:
            return True
        biz_id = cls._get_request_biz_id(request)
        # 不涉及业务数据的接口不携带 bk_biz_id，无需校验
        if biz_id is None:
            return True
        try:
            return str(bk_biz_id_to_space_uid(biz_id)) == str(record.space_uid)
        except Exception:  # pylint: disable=broad-except
            return False

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
