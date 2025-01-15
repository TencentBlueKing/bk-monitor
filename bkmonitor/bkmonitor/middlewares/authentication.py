# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
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


class NoCsrfSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        request.csrf_processing_done = True


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
        from bkmonitor.models import ApiAuthToken

        if "HTTP_AUTHORIZATION" in request.META and request.META["HTTP_AUTHORIZATION"].startswith("Bearer "):
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

            if not record.is_allowed_namespace(f"biz#{request.biz_id}"):
                return HttpResponseForbidden(
                    f"namespace biz#{request.biz_id} is not allowed in [{','.join(record.namespaces)}]"
                )

            # grafana、as_code场景权限模式：替换请求用户为令牌创建者
            if record.type.lower() in ["as_code", "grafana"]:
                username = "system" if record.type.lower() == "as_code" else "admin"
                user = auth.authenticate(username=username)
                auth.login(request, user)
                request.skip_check = True
            else:
                # 观测场景、告警事件场景权限模式：保留原用户信息,判定action是否符合token鉴权场景
                request.token = token
            return

        return super(ApiTokenAuthenticationMiddleware, self).process_view(request, view, *args, **kwargs)


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
