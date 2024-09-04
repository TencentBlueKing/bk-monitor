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
import random
import time
from typing import Dict, Tuple

import jwt
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import caches
from django.http import HttpRequest, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from rest_framework.authentication import SessionAuthentication

from bkmonitor.models import ApiAuthToken, AuthType
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)

APP_CODE_TOKENS = {}
APP_CODE_UPDATE_TIME = None
APP_CODE_TOKEN_CACHE_TIME = 300 + random.randint(0, 100)


def is_match_api_token(request, app_code: str, token: str) -> bool:
    """
    校验API鉴权
    """
    # 如果没有biz_id，直接放行
    if not getattr(request, "biz_id"):
        return True

    global APP_CODE_TOKENS
    global APP_CODE_UPDATE_TIME

    # 更新缓存
    if APP_CODE_UPDATE_TIME is None or time.time() - APP_CODE_UPDATE_TIME > APP_CODE_TOKEN_CACHE_TIME:
        result = {}
        records = ApiAuthToken.objects.filter(type=AuthType.API)
        for record in records:
            app_code = record.params.get("app_code")
            if not app_code:
                continue
            result[app_code] = (record.token, record.namespaces)
        APP_CODE_UPDATE_TIME = time.time()
        APP_CODE_TOKENS = result

    # 如果app_code没有对应的token，直接放行
    if app_code not in APP_CODE_TOKENS:
        return True

    auth_token, namespaces = APP_CODE_TOKENS[app_code]

    # 校验token
    if token != auth_token:
        return False

    # 校验命名空间
    if "biz#all" in namespaces or f"biz#{request.biz_id}" in namespaces:
        return True

    return False


class BkJWTClient:
    """
    jwt鉴权客户端
    """

    JWT_KEY_NAME = 'HTTP_X_BKAPI_JWT'
    ALGORITHM = 'RS512'

    class AttrDict(dict):
        def __getattr__(self, item):
            return self[item]

    def __init__(self, request: HttpRequest, public_keys: Dict[str, str]):
        self.request = request
        self.public_keys = public_keys

        self.is_valid = False
        self.app = None
        self.user = None

    def validate(self) -> Tuple[bool, str]:
        # jwt内容
        raw_content = self.request.META.get(self.JWT_KEY_NAME, '')
        if not raw_content:
            return False, "request headers jwt content is empty"

        # jwt headers解析
        try:
            headers = jwt.get_unverified_header(raw_content)
        except Exception as e:  # pylint: disable=broad-except
            return False, f"jwt content parse header error: {e}"

        # jwt算法
        algorithm = headers.get("alg") or self.ALGORITHM

        # 根据app_code获取公钥
        public_key = self.public_keys.get(headers.get("kid"))
        if not public_key:
            return False, f"public key of {headers.get('kid')} not found"

        # jwt内容解析
        try:
            result = jwt.decode(raw_content, public_key, algorithms=algorithm)
        except Exception as e:  # pylint: disable=broad-except
            return False, f"jwt content decode error: {e}"

        self.is_valid = True
        self.app = self.AttrDict(result.get("app", {}))

        # 版本兼容
        if self.app.get("bk_app_code"):
            self.app["app_code"] = self.app["bk_app_code"]

        # 验证app是否经过验证
        if self.app.get("verified") is not True:
            return False, "app_code not verified"

        self.user = self.AttrDict(result.get("user", {}))

        return True, ""


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
        except Exception as e:
            logger.error("Auto create & update UserModel fail, username: {}, error: {}".format(username, e))
            return None

        if self.user_can_authenticate(user):
            return user

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None


class AuthenticationMiddleware(MiddlewareMixin):
    @staticmethod
    @functools.lru_cache(maxsize=1)
    def get_apigw_public_keys() -> Dict[str, str]:
        cache = caches["login_db"]

        api_names = settings.BK_APIGW_NAME.split(",")
        if not api_names:
            return {}

        # 获取API公钥
        public_keys = {}
        for api_name in api_names:
            cache_key = f"apigw_public_key:{api_name}"
            public_key = cache.get(cache_key)
            if public_key is None:
                try:
                    public_key = api.bk_apigateway.get_public_key(api_name=api_name)["public_key"]
                except BKAPIError as e:
                    logger.error(f"获取{api_name} apigw public_key失败，%s" % e)
                    public_key = ""

            # 如果预期的公钥为空，则设置2分钟，防止频繁请求
            if public_key:
                public_keys[api_name] = public_key
                cache.set(cache_key, public_key, timeout=None)
            else:
                cache.set(cache_key, public_key, timeout=120)

        return public_keys

    def process_view(self, request, view, *args, **kwargs):
        # 登录豁免
        if getattr(view, "login_exempt", False):
            return None

        # 后台仪表盘渲染豁免
        if "/grafana/" in request.path:
            request.user = auth.authenticate(username="admin")
            return

        if request.META.get("HTTP_X_BKAPI_FROM") == "apigw" and request.META.get(BkJWTClient.JWT_KEY_NAME):
            request.jwt = BkJWTClient(request, self.get_apigw_public_keys())
            result, error_message = request.jwt.validate()
            if not result:
                return HttpResponseForbidden(error_message)

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
