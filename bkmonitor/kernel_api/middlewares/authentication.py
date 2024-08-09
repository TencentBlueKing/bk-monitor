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
import functools
import logging
import time

from apigw_manager.apigw.utils import get_configuration
from apigw_manager.core.fetch import Fetcher
from bkoauth.jwt_client import JWTClient
from blueapps.account.middlewares import LoginRequiredMiddleware
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import caches
from django.http import HttpResponseForbidden
from rest_framework.authentication import SessionAuthentication

from bkmonitor.models import ApiAuthToken, AuthType

logger = logging.getLogger(__name__)


APP_CODE_TOKENS = {}
APP_CODE_UPDATE_TIME = None


def is_match_api_token(request, app_code: str, token: str) -> bool:
    """
    校验API鉴权
    """
    global APP_CODE_TOKENS
    global APP_CODE_UPDATE_TIME

    # 更新缓存
    if time.time() - APP_CODE_UPDATE_TIME > 300:
        result = {}
        records = ApiAuthToken.objects.filter(type=AuthType.API)
        for record in records:
            app_code = token.params.get("app_code")
            if not app_code:
                continue
            result[app_code] = (record.token, record.namespaces)
        APP_CODE_UPDATE_TIME = time.time()
        APP_CODE_TOKENS = result

    # 如果app_code不在缓存中，则直接返回True
    if app_code not in APP_CODE_TOKENS:
        return True

    # 如果app_code在缓存中，则校验token
    auth_token, namespaces = APP_CODE_TOKENS[app_code]
    if token != auth_token:
        return False

    # 校验命名空间
    if "biz#all" in namespaces or f"biz#{request.biz_id}" in namespaces:
        return True

    return False


class KernelSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        request.csrf_processing_done = True


class AppWhiteListModelBackend(ModelBackend):
    # 经过esb 鉴权， bktoken已经丢失，因此不再对用户名进行校验。
    def authenticate(self, request=None, username=None, password=None, **kwargs):
        if username is None:
            return None
        try:
            user_model = get_user_model()
            user, _ = user_model.objects.get_or_create(username=username, defaults={"nickname": username})
        except Exception:
            logger.exception("Auto create & update UserModel fail")
            return None

        if self.user_can_authenticate(user):
            return user

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None


class AuthenticationMiddleware(LoginRequiredMiddleware):
    @staticmethod
    @functools.lru_cache(maxsize=1)
    def get_apigw_public_key():
        cache = caches["login_db"]
        # 从缓存中获取
        public_key = cache.get("apigw_public_key")
        if public_key:
            return public_key

        # 从apigw获取
        m = Fetcher(get_configuration(bk_app_code=settings.APP_CODE, bk_app_secret=settings.APP_TOKEN))
        public_key = m.get_public_key(api_name=settings.BK_APIGW_NAME)["public_key"]

        # 设置缓存
        cache.set("apigw_public_key", public_key)
        return public_key

    def process_view(self, request, view, *args, **kwargs):
        # 登录豁免
        if getattr(view, "login_exempt", False):
            return None

        # 后台仪表盘渲染豁免
        if "/grafana/" in request.path:
            request.user = auth.authenticate(username="admin")
            return

        if request.META.get(JWTClient.JWT_KEY_NAME):
            request.META[JWTClient.JWT_PUBLIC_KEY_HEADER_NAME] = self.get_apigw_public_key()
            request.jwt = JWTClient(request)
            if not request.jwt.is_valid:
                return HttpResponseForbidden()

            app_code = request.jwt.app.app_code
            username = request.jwt.user.username
        else:
            app_code = request.META.get("HTTP_BK_APP_CODE")
            username = request.META.get("HTTP_BK_USERNAME")

        # 校验app_code及token
        token = request.GET.get("HTTP_X_BKMONITOR_TOKEN")
        if app_code and is_match_api_token(request, app_code, token):
            request.user = auth.authenticate(username=username)
            return

        return HttpResponseForbidden()
