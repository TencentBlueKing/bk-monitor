"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

import jwt
from blueapps.account.models import User
from django.conf import settings
from django.contrib import auth
from django.contrib.auth.backends import ModelBackend
from django.core.cache import caches
from django.http import HttpRequest, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from rest_framework.authentication import SessionAuthentication

from bkmonitor.models import ApiAuthToken, AuthType
from bkmonitor.utils.user import get_admin_username
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)

APP_CODE_TOKENS: dict[str, list[str]] = {}
APP_CODE_UPDATE_TIME = None
APP_CODE_TOKEN_CACHE_TIME = 300 + random.randint(0, 100)


def is_match_api_token(request, bk_tenant_id: str, app_code: str) -> bool:
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
        records = ApiAuthToken.objects.filter(type=AuthType.API, bk_tenant_id=bk_tenant_id)
        for record in records:
            if not record.params.get("app_code"):
                continue
            result[record.params["app_code"]] = record.namespaces
        APP_CODE_UPDATE_TIME = time.time()
        APP_CODE_TOKENS = result

    # 如果app_code没有对应的token，直接放行
    if app_code not in APP_CODE_TOKENS:
        return True

    namespaces = APP_CODE_TOKENS[app_code]

    # 校验命名空间
    if "biz#all" in namespaces or f"biz#{request.biz_id}" in namespaces:
        return True

    return False


class BkJWTClient:
    """
    jwt鉴权客户端
    """

    JWT_KEY_NAME = "HTTP_X_BKAPI_JWT"
    ALGORITHM = "RS512"

    class AttrDict(dict):
        def __getattr__(self, item):
            return self[item]

    def __init__(self, request: HttpRequest, public_keys: dict[str, str]):
        self.request = request
        self.public_keys = public_keys

        self.is_valid = False
        self.app = None
        self.user = None

    def validate(self) -> tuple[bool, str]:
        # jwt内容
        raw_content = self.request.META.get(self.JWT_KEY_NAME, "")
        if not raw_content:
            return False, "request headers jwt content is empty"

        # jwt headers解析
        try:
            headers: dict[str, str] = jwt.get_unverified_header(raw_content)
        except Exception as e:  # pylint: disable=broad-except
            return False, f"jwt content parse header error: {e}"

        # jwt算法
        algorithm = headers.get("alg") or self.ALGORITHM

        # 根据app_code获取公钥
        public_key = self.public_keys.get(headers.get("kid", ""))
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

        # # 验证app是否经过验证
        # if self.app.get("verified") is not True:
        #     return False, "app_code not verified"

        self.user = self.AttrDict(result.get("user", {}))

        return True, ""


class KernelSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        request.csrf_processing_done = True


class AppWhiteListModelBackend(ModelBackend):
    # 经过esb 鉴权， bktoken已经丢失，因此不再对用户名进行校验。
    def authenticate(self, request=None, username=None, bk_tenant_id: str = DEFAULT_TENANT_ID, **kwargs):  # pyright: ignore[reportIncompatibleMethodOverride]
        if username is None:
            return None

        try:
            user, _ = User.objects.get_or_create(
                username=username, defaults={"nickname": username, "tenant_id": bk_tenant_id}
            )

            # 如果未开启多租户，默认使用system租户
            if not settings.ENABLE_MULTI_TENANT_MODE and user.tenant_id != DEFAULT_TENANT_ID:
                user.tenant_id = DEFAULT_TENANT_ID
                user.save()

            # 如果开启了多租户，且用户租户id不匹配，则尝试更新用户租户id
            # NOTE: apigw在应用态下不会校验用户名与租户ID是否对应，因此需要通过查询api确认用户属于当前租户
            # 如果确认用户属于当前租户下的虚拟管理用户或从当前租户下查询到了用户，则更新用户租户id为当前租户id
            if settings.ENABLE_MULTI_TENANT_MODE and user.tenant_id != bk_tenant_id:
                if user.username == get_admin_username(bk_tenant_id) or api.bk_login.batch_query_user_display_info(
                    bk_tenant_id=bk_tenant_id, bk_usernames=[user.username]
                ):
                    user.tenant_id = bk_tenant_id
                    user.save()

        except Exception as e:
            logger.error(f"Auto create & update UserModel fail, username: {username}, error: {e}")
            return None

        if self.user_can_authenticate(user):
            return user

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None


class AuthenticationMiddleware(MiddlewareMixin):
    @staticmethod
    @functools.lru_cache(maxsize=1)
    def get_apigw_public_keys() -> dict[str, str]:
        cache = caches["login_db"]

        api_names = settings.FROM_APIGW_NAME.split(",")
        if not api_names:
            return {}

        # 获取API公钥
        public_keys = {}
        for api_name in api_names:
            cache_key = f"apigw_public_key:{api_name}"
            public_key = cache.get(cache_key)
            if public_key is None:
                try:
                    public_key = api.bk_apigateway.get_public_key(api_name=api_name, bk_tenant_id=DEFAULT_TENANT_ID)[
                        "public_key"
                    ]
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

    @staticmethod
    def use_apigw_auth(request) -> bool:
        """
        使用apigw鉴权
        """
        # 如果请求来自apigw，并且携带了jwt，则使用apigw鉴权
        return request.META.get("HTTP_X_BKAPI_FROM") == "apigw" and request.META.get(BkJWTClient.JWT_KEY_NAME)

    @staticmethod
    def use_mcp_auth(request):
        """
        是否是MCP请求
        """
        return request.META.get("X-Bk-Request-Origin") == settings.AIDEV_AGENT_MCP_REQUEST_HEADER_VALUE

    def _handle_mcp_auth(self, request, username=None):
        """
        处理MCP权限校验
        MCP请求已经通过API网关认证，这里只需要额外的MCP权限校验
        """
        # 导入放在这里避免循环依赖
        from bkmonitor.iam.drf import MCPPermission

        logger.info("MCPAuthentication: Handling MCP authentication")

        # 获取业务ID（从GET或POST参数中获取）
        bk_biz_id = request.GET.get("bk_biz_id")
        if not bk_biz_id and request.method == "POST":
            # 尝试从POST数据中获取
            try:
                bk_biz_id = request.POST.get("bk_biz_id")
            except Exception as e:  # pylint: disable=broad-except
                logger.error("MCPAuthentication: Failed to get bk_biz_id from POST data, error: %s", e)
                pass

        if not bk_biz_id:
            logger.error("MCPAuthentication: Missing bk_biz_id in request parameters")
            return HttpResponseForbidden("Missing bk_biz_id in request parameters")

        try:
            request.biz_id = int(bk_biz_id)
        except (ValueError, TypeError):
            logger.error(f"MCPAuthentication: Invalid bk_biz_id format: {bk_biz_id}")
            return HttpResponseForbidden(f"Invalid bk_biz_id format: {bk_biz_id}")

        # 使用 MCPPermission 进行权限校验
        try:
            permission = MCPPermission()
            # 创建一个简单的 mock view 对象
            mock_view = type("MockView", (), {"kwargs": {}})()

            if not permission.has_permission(request, mock_view):
                logger.warning(f"MCPAuthentication: Permission denied for user={username}, bk_biz_id={request.biz_id}")
                return HttpResponseForbidden("Permission denied: insufficient MCP permissions")
        except Exception as e:
            logger.error(f"MCPAuthentication: Permission check failed: {e}")
            return HttpResponseForbidden(f"Permission denied: {e}")

        logger.info(f"MCPAuthentication: Authentication Success: user={username}, bk_biz_id={request.biz_id}")
        return None

    def process_view(self, request, view, *args, **kwargs):
        # 登录豁免
        if getattr(view, "login_exempt", False):
            return None

        if self.use_apigw_auth(request):
            request.jwt = BkJWTClient(request, self.get_apigw_public_keys())
            result, error_message = request.jwt.validate()
            if not result:
                return HttpResponseForbidden(error_message)

            app_code = request.jwt.app.app_code
            username = request.jwt.user.username
            if settings.ENABLE_MULTI_TENANT_MODE:
                bk_tenant_id = request.META.get("HTTP_X_BK_TENANT_ID")
                if not bk_tenant_id:
                    return HttpResponseForbidden("lack of tenant_id")
            else:
                bk_tenant_id = DEFAULT_TENANT_ID
        else:
            app_code = request.META.get("HTTP_BK_APP_CODE")
            username = request.META.get("HTTP_BK_USERNAME")
            bk_tenant_id = DEFAULT_TENANT_ID

        # MCP权限校验（在用户认证完成后）
        if self.use_mcp_auth(request):
            logger.info("=" * 80)
            logger.info("MCPAuthentication: Handling MCP authentication")

            # 打印认证信息
            logger.info(f"MCPAuthentication: app_code={app_code}, username={username}, tenant_id={bk_tenant_id}")

            # 打印请求基本信息
            logger.info(f"MCPAuthentication: method={request.method}, path={request.path}")

            # 打印关键请求头
            logger.info("MCPAuthentication: Request Headers:")
            key_headers = [
                "X-Bk-Request-Origin",
                "HTTP_X_BKAPI_FROM",
                "HTTP_X_BK_TENANT_ID",
                "HTTP_BK_USERNAME",
                "HTTP_BK_APP_CODE",
                "Content-Type",
            ]
            for header_key in key_headers:
                header_value = request.META.get(header_key, "N/A")
                logger.info(f"MCPAuthentication: Header - {header_key}: {header_value}")

            # 打印GET参数
            if request.GET:
                logger.info(f"MCPAuthentication: GET params: {dict(request.GET)}")
            else:
                logger.info("MCPAuthentication: GET params: (empty)")

            # 打印POST参数
            if request.method == "POST":
                try:
                    if request.POST:
                        logger.info(f"MCPAuthentication: POST params: {dict(request.POST)}")
                    else:
                        logger.info("MCPAuthentication: POST params: (empty)")
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(f"MCPAuthentication: Failed to read POST params: {e}")

            logger.info("=" * 80)

            return self._handle_mcp_auth(request, username=username)

        # 后台仪表盘渲染豁免
        # TODO: 多租户支持验证
        if "/grafana/" in request.path and not app_code:
            bk_tenant_id = request.META.get("HTTP_X_BK_TENANT_ID") or DEFAULT_TENANT_ID
            request.user = auth.authenticate(username="admin", bk_tenant_id=bk_tenant_id)
            return

        # 校验app_code权限范围
        if not app_code or is_match_api_token(request, bk_tenant_id, app_code):
            request.user = auth.authenticate(username=username, bk_tenant_id=bk_tenant_id)
            if settings.ENABLE_MULTI_TENANT_MODE and request.user and request.user.tenant_id != bk_tenant_id:
                return HttpResponseForbidden(f"user tenant_id is {request.user.tenant_id} not match {bk_tenant_id}")
            return

        return HttpResponseForbidden()
