"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apigw_manager.apigw.authentication import ApiGatewayJWTMiddleware
from apigw_manager.apigw.providers import PublicKeyProvider
from blueapps.account import get_user_model
from blueapps.account.middlewares import LoginRequiredMiddleware
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.backends import ModelBackend
from django.http import HttpResponseForbidden
from rest_framework.authentication import SessionAuthentication

from bkmonitor.models import logger
from constants.common import DEFAULT_TENANT_ID


class NoCsrfSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        request.csrf_processing_done = True


class ApiTokenAuthBackend(ModelBackend):
    def authenticate(self, request, username: str, tenant_id: str, **kwargs):
        if not username:
            return None
        try:
            user_model = get_user_model()
            user, _ = user_model.objects.get_or_create(username=username, defaults={"nickname": username})
            # 如果用户没有租户id，则设置租户id
            if not user.tenant_id or (
                not settings.ENABLE_MULTI_TENANT_MODE and tenant_id and tenant_id != user.tenant_id
            ):
                user.tenant_id = tenant_id
                user.save()
        except Exception:
            logger.exception("ApiTokenAuthBackend authenticate error, username: %s, tenant_id: %s", username, tenant_id)
            return None
        return user


class ApiTokenAuthenticationMiddleware(LoginRequiredMiddleware):
    def api_token_auth(self, request, view, *args, **kwargs):
        from bkmonitor.models import ApiAuthToken

        token = request.META["HTTP_AUTHORIZATION"][7:]
        try:
            record = ApiAuthToken.objects.get(token=token)
        except ApiAuthToken.DoesNotExist:
            record = None

        if not record:
            return HttpResponseForbidden("not valid token")

        if record.is_expired():
            return HttpResponseForbidden("token has expired")

        if not record.is_allowed_view(view):
            return HttpResponseForbidden("api is not allowed")

        # TODO: 检查命名空间与租户id是否匹配
        if not record.is_allowed_namespace(f"biz#{request.biz_id}"):
            return HttpResponseForbidden(
                f"namespace biz#{request.biz_id} is not allowed in [{','.join(record.namespaces)}]"
            )

        # grafana、as_code场景权限模式：替换请求用户为令牌创建者
        if record.type.lower() in ["as_code", "grafana"]:
            username = "system" if record.type.lower() == "as_code" else "admin"
            user = auth.authenticate(username=username, tenant_id=record.bk_tenant_id)
            auth.login(request, user)
            request.skip_check = True
        elif record.type.lower() == "entity":
            # 实体关系权限模式：替换请求用户为令牌创建者
            username = record.create_user or "system"
            user = auth.authenticate(username=username, tenant_id=record.bk_tenant_id)
            auth.login(request, user)
            request.token = token
            request.skip_check = True
        elif record.type.lower() == "user":
            # 用户权限模式：替换请求用户为令牌创建者
            username = record.create_user
            user = auth.authenticate(username=username, tenant_id=record.bk_tenant_id)
            auth.login(request, user)
        else:
            # 观测场景、告警事件场景权限模式：保留原用户信息,判定action是否符合token鉴权场景
            request.token = token
        return

    def process_view(self, request, view, *args, **kwargs):
        # 如果请求头中携带了token，则进行token鉴权
        if "HTTP_AUTHORIZATION" in request.META and request.META["HTTP_AUTHORIZATION"].startswith("Bearer "):
            result = self.api_token_auth(request, view, *args, **kwargs)
        else:
            result = super().process_view(request, view, *args, **kwargs)

        if request.user:
            # 验证存储的租户ID是否正确，如果不正确则更新存储的租户ID
            if settings.ENABLE_MULTI_TENANT_MODE and hasattr(request.user, "tenant_id"):
                db_user = get_user_model().objects.get(username=request.user.username)
                if db_user.tenant_id != request.user.tenant_id:
                    logger.error(f"user tenant_id is {db_user.tenant_id} not match {request.user.tenant_id}")
                    db_user.tenant_id = request.user.tenant_id
                    db_user.save()

            # 在不开启租户的情况下，确保user.tenant_id为system，确保后续处理逻辑的统一性
            if not getattr(request.user, "tenant_id", None) or (
                not settings.ENABLE_MULTI_TENANT_MODE and request.user.tenant_id != DEFAULT_TENANT_ID
            ):
                request.user.tenant_id = DEFAULT_TENANT_ID

                if request.user.is_authenticated:
                    request.user.save()
        return result


class SettingsExternalPublicKeyProvider(PublicKeyProvider):
    def provide(self, api_name, jwt_issuer=None):
        """Return the public key specified by Settings"""
        public_key = getattr(settings, "EXTERNAL_APIGW_PUBLIC_KEY", None)
        if not public_key:
            logger.warning(
                "No `EXTERNAL_APIGW_PUBLIC_KEY` can be found in settings, you should either configure it "
                "with a valid value or remove `ApiGatewayJWTExternalMiddleware` middleware entirely"
            )
        return public_key


class ApiGatewayJWTExternalMiddleware(ApiGatewayJWTMiddleware):
    PUBLIC_KEY_PROVIDER_CLS = SettingsExternalPublicKeyProvider
