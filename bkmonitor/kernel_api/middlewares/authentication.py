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
import json
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
from core.prometheus import metrics

logger = logging.getLogger(__name__)

# MCP auth logs: grep by tag, e.g. `grep '\[MCP_AUTH\]'` or `event=permission_denied`
MCP_AUTH_LOG_TAG = "MCP_AUTH"

APP_CODE_TOKENS: dict[str, list[str]] = {}
APP_CODE_UPDATE_TIME = None
APP_CODE_TOKEN_CACHE_TIME = 300 + random.randint(0, 100)

OPENCLAW_RECOVERING_MCP_TOOLS = {
    "search_openclaw_spans",
    "get_openclaw_trace_detail",
    "search_openclaw_logs",
}


def is_match_api_token(request, bk_tenant_id: str, app_code: str) -> bool:
    """
    校验API鉴权
    """
    # 如果没有biz_id，直接放行
    if not getattr(request, "biz_id") and not app_code == settings.AIDEV_AGENT_MCP_REQUEST_AGENT_CODE:
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
                    bk_usernames=[user.username], bk_tenant_id=bk_tenant_id
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
    def use_mcp_auth(request, app_code):
        """
        是否是MCP请求
        通过检查请求头中是否包含 HTTP_X_BKAPI_MCP_SERVER_NAME 来判断
        兼容旧的判断方式：
        1. 请求头中包含X-BK-REQUEST-SOURCE,且为对应MCP的配置头
        2. app_code为对应MCP的应用
        """
        # 新的判断方式：检查是否包含 MCP Server Name 请求头
        if request.META.get("HTTP_X_BKAPI_MCP_SERVER_NAME"):
            return True

        # 兼容旧的判断方式
        return (
            request.META.get("HTTP_X_BK_REQUEST_SOURCE") == settings.AIDEV_AGENT_MCP_REQUEST_HEADER_VALUE
            or app_code == settings.AIDEV_AGENT_MCP_REQUEST_AGENT_CODE
        )

    @staticmethod
    def use_api_token_auth(request):
        return "HTTP_AUTHORIZATION" in request.META and request.META["HTTP_AUTHORIZATION"].startswith("Bearer ")

    @staticmethod
    def extract_tool_name_from_path(path: str) -> str:
        """
        从请求路径中提取工具名称
        路径格式: /xxx/xx/xxx/tool_name/ -> 提取 tool_name
        """
        if not path:
            return ""
        # 防御 nginx rewrite 等场景下 path 携带 query string / fragment 的情况
        path = path.split("?", 1)[0].split("#", 1)[0]
        # 去除末尾的斜杠，然后按斜杠分割，取最后一个非空部分
        path = path.rstrip("/")
        parts = path.split("/")
        return parts[-1] if parts else ""

    def _report_mcp_metric(self, tool_name, bk_biz_id, username, status, permission_action, mcp_server_name):
        """
        上报MCP调用指标
        @param tool_name: 工具名称
        @param bk_biz_id: 业务ID
        @param username: 用户名
        @param status: 调用状态 (accessed/permission_denied/invalid_params/error/exempt)
        @param permission_action: 权限动作ID
        @param mcp_server_name: MCP服务名称
        """
        try:
            # 标签值处理，避免空值
            labels = {
                "tool_name": tool_name or "unknown",
                "bk_biz_id": str(bk_biz_id) if bk_biz_id else "unknown",
                "username": username or "unknown",
                "status": status,
                "permission_action": permission_action or "unknown",
                "mcp_server_name": mcp_server_name or "unknown",
            }

            # 上报请求计数
            metrics.MCP_REQUESTS_TOTAL.labels(**labels).inc()

            # 立即推送指标
            metrics.report_all()
        except Exception as err:  # pylint: disable=broad-except
            logger.exception("[%s] event=metrics_report_failed error=%s", MCP_AUTH_LOG_TAG, err)

    def _handle_mcp_auth(self, request, username=None):
        """
        处理MCP权限校验
        MCP请求已经通过API网关认证，这里只需要额外的MCP权限校验
        """
        # 导入放在这里避免循环依赖
        from bkmonitor.iam.action import get_action_by_id
        from bkmonitor.iam.drf import MCPPermission
        from constants.mcp import get_mcp_permission_action_by_server_name

        # 提取MCP服务名称（用于指标上报）
        mcp_server_name = request.META.get("HTTP_X_BKAPI_MCP_SERVER_NAME", "")
        tool_name = self.extract_tool_name_from_path(request.path)
        logger.info(
            "[%s] event=auth_begin tool=%s mcp_server=%s username=%s method=%s path=%s",
            MCP_AUTH_LOG_TAG,
            tool_name,
            mcp_server_name,
            username,
            request.method,
            request.path,
        )

        openclaw_mcp_server_name = getattr(settings, "OPENCLAW_RECOVERING_MCP_SERVER_NAME", "")
        if openclaw_mcp_server_name and mcp_server_name == openclaw_mcp_server_name:
            if not username:
                logger.warning(
                    "[%s] event=openclaw_denied reason=missing_username mcp_server=%s",
                    MCP_AUTH_LOG_TAG,
                    mcp_server_name,
                )
                return HttpResponseForbidden("Missing username in request")

            if tool_name not in OPENCLAW_RECOVERING_MCP_TOOLS:
                logger.warning(
                    "[%s] event=openclaw_denied reason=invalid_tool tool=%s mcp_server=%s username=%s",
                    MCP_AUTH_LOG_TAG,
                    tool_name,
                    mcp_server_name,
                    username,
                )
                return HttpResponseForbidden("Invalid OpenClaw MCP tool")

            # OpenClaw 数据统一上报到一个业务，入口只固定业务上下文；
            # 用户级数据边界由 OpenClaw Resource 基于 username 继续收敛。
            request.biz_id = int(getattr(settings, "OPENCLAW_RECOVERING_BK_BIZ_ID", 0) or 0)
            request.skip_check = True
            request.openclaw_identity_scoped = True
            logger.info(
                "[%s] event=openclaw_allowed tool=%s mcp_server=%s username=%s bk_biz_id=%s",
                MCP_AUTH_LOG_TAG,
                tool_name,
                mcp_server_name,
                username,
                request.biz_id,
            )
            self._report_mcp_metric(
                tool_name=tool_name,
                bk_biz_id=request.biz_id,
                username=username,
                status="accessed",
                permission_action="identity_scoped",
                mcp_server_name=mcp_server_name,
            )
            return None

        # 获取权限动作ID
        # 优先从 MCP Server Name 映射中获取，如果没有则从旧的请求头中获取
        permission_action_id = ""

        permission_action_source = ""
        if mcp_server_name:
            permission_action_id = get_mcp_permission_action_by_server_name(mcp_server_name)
            if permission_action_id:
                permission_action_source = "server_name_map"

        # 如果没有从 MCP Server Name 获取到，则尝试从旧的请求头中获取
        if not permission_action_id:
            permission_action_id = request.META.get("HTTP_X_BKAPI_PERMISSION_ACTION", "")
            if permission_action_id:
                permission_action_source = "permission_action_header"

        logger.info(
            "[%s] event=permission_action_resolved mcp_server=%s permission_action=%s source=%s",
            MCP_AUTH_LOG_TAG,
            mcp_server_name,
            permission_action_id,
            permission_action_source or "none",
        )

        if tool_name and tool_name in settings.MCP_PERMISSION_EXEMPT_TOOLS:
            logger.info(
                "[%s] event=tool_exempt tool=%s permission_action=%s",
                MCP_AUTH_LOG_TAG,
                tool_name,
                permission_action_id,
            )
            request.skip_check = True
            # 上报豁免工具的调用指标
            self._report_mcp_metric(
                tool_name=tool_name,
                bk_biz_id=None,
                username=username,
                status="exempt",
                permission_action=permission_action_id,
                mcp_server_name=mcp_server_name,
            )
            return None

        # 获取业务ID（从GET或POST参数中获取）
        bk_biz_id = request.GET.get("bk_biz_id")
        request.skip_check = False  # 手动设置需要进行权限校验

        if not bk_biz_id and request.method == "POST":
            # 尝试从POST表单数据中获取
            try:
                bk_biz_id = request.POST.get("bk_biz_id")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "[%s] event=bk_biz_id_parse_failed source=post_form error=%s",
                    MCP_AUTH_LOG_TAG,
                    e,
                )

            # 如果表单数据中没有，尝试从JSON body中获取
            if not bk_biz_id:
                try:
                    body = request.body.decode("utf-8")
                    if body:
                        data = json.loads(body)
                        bk_biz_id = data.get("bk_biz_id")
                        if bk_biz_id:
                            logger.info(
                                "[%s] event=bk_biz_id_resolved source=json_body bk_biz_id=%s",
                                MCP_AUTH_LOG_TAG,
                                bk_biz_id,
                            )
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        "[%s] event=bk_biz_id_parse_failed source=json_body error=%s",
                        MCP_AUTH_LOG_TAG,
                        e,
                    )

        if not bk_biz_id:
            logger.error(
                "[%s] event=bk_biz_id_missing tool=%s method=%s path=%s username=%s",
                MCP_AUTH_LOG_TAG,
                tool_name,
                request.method,
                request.path,
                username,
            )
            # 上报参数缺失的调用指标
            self._report_mcp_metric(
                tool_name=tool_name,
                bk_biz_id=None,
                username=username,
                status="invalid_params",
                permission_action=permission_action_id,
                mcp_server_name=mcp_server_name,
            )
            return HttpResponseForbidden("Missing bk_biz_id in request parameters")

        try:
            request.biz_id = int(bk_biz_id)
        except (ValueError, TypeError):
            logger.error(
                "[%s] event=bk_biz_id_invalid bk_biz_id=%s username=%s",
                MCP_AUTH_LOG_TAG,
                bk_biz_id,
                username,
            )
            # 上报参数格式错误的调用指标
            self._report_mcp_metric(
                tool_name=tool_name,
                bk_biz_id=bk_biz_id,
                username=username,
                status="invalid_params",
                permission_action=permission_action_id,
                mcp_server_name=mcp_server_name,
            )
            return HttpResponseForbidden(f"Invalid bk_biz_id format: {bk_biz_id}")

        # 使用 MCPPermission 进行权限校验
        try:
            # 根据请求头动态获取权限动作
            action = None
            if permission_action_id:
                try:
                    action = get_action_by_id(permission_action_id)
                    logger.info(
                        "[%s] event=iam_action_resolved permission_action=%s permission_action_name=%s",
                        MCP_AUTH_LOG_TAG,
                        action.id,
                        action.name,
                    )
                except Exception as e:
                    logger.warning(
                        "[%s] event=iam_action_resolve_failed permission_action=%s error=%s",
                        MCP_AUTH_LOG_TAG,
                        permission_action_id,
                        e,
                    )
                    # 如果找不到对应的权限，使用默认权限

            permission = MCPPermission(action=action)
            # 创建一个简单的 mock view 对象
            mock_view = type("MockView", (), {"kwargs": {}})()

            if not permission.has_permission(request, mock_view):
                logger.warning(
                    "[%s] event=permission_denied username=%s bk_biz_id=%s permission_action=%s tool=%s mcp_server=%s",
                    MCP_AUTH_LOG_TAG,
                    username,
                    request.biz_id,
                    permission_action_id,
                    tool_name,
                    mcp_server_name,
                )
                # 上报权限拒绝的调用指标
                self._report_mcp_metric(
                    tool_name=tool_name,
                    bk_biz_id=request.biz_id,
                    username=username,
                    status="permission_denied",
                    permission_action=permission_action_id,
                    mcp_server_name=mcp_server_name,
                )
                return HttpResponseForbidden("Permission denied: insufficient MCP permissions")
        except Exception as e:
            logger.exception("[%s] event=permission_check_failed error=%s", MCP_AUTH_LOG_TAG, e)
            # 上报异常的调用指标
            self._report_mcp_metric(
                tool_name=tool_name,
                bk_biz_id=request.biz_id,
                username=username,
                status="error",
                permission_action=permission_action_id,
                mcp_server_name=mcp_server_name,
            )
            return HttpResponseForbidden(f"Permission denied: {e}")

        logger.info(
            "[%s] event=auth_success username=%s bk_biz_id=%s permission_action=%s tool=%s mcp_server=%s",
            MCP_AUTH_LOG_TAG,
            username,
            request.biz_id,
            permission_action_id,
            tool_name,
            mcp_server_name,
        )
        # 上报成功的调用指标
        self._report_mcp_metric(
            tool_name=tool_name,
            bk_biz_id=request.biz_id,
            username=username,
            status="accessed",
            permission_action=permission_action_id,
            mcp_server_name=mcp_server_name,
        )
        return None

    def _handle_api_token_auth(self, request, view):
        token = request.META["HTTP_AUTHORIZATION"][7:]
        try:
            record = ApiAuthToken.objects.get(token=token)
        except ApiAuthToken.DoesNotExist:
            record = None

        if not record:
            return HttpResponseForbidden("API Token is invalid")

        if record.is_expired():
            return HttpResponseForbidden("API Token has expired")

        if not record.is_allowed_view(view):
            return HttpResponseForbidden("API Token is not allowed")

        # TODO: 检查命名空间与租户id是否匹配
        if not record.is_allowed_namespace(f"biz#{request.biz_id}"):
            if not request.biz_id:
                return HttpResponseForbidden("params `bk_biz_id` is required")
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
        else:
            # 观测场景、告警事件场景权限模式：保留原用户信息,判定action是否符合token鉴权场景
            request.token = token
        return

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
        if self.use_mcp_auth(request, app_code):
            request.user = auth.authenticate(username=username, bk_tenant_id=bk_tenant_id)
            mcp_key_headers = (
                "HTTP_X_BK_REQUEST_SOURCE",
                "HTTP_X_BKAPI_FROM",
                "HTTP_X_BK_TENANT_ID",
                "HTTP_BK_USERNAME",
                "HTTP_BK_APP_CODE",
                "HTTP_X_BKAPI_MCP_SERVER_NAME",
                "HTTP_X_BKAPI_PERMISSION_ACTION",
                "Content-Type",
            )
            headers = {key: request.META.get(key, "N/A") for key in mcp_key_headers}
            logger.info(
                "[%s] event=request_received app_code=%s username=%s tenant_id=%s method=%s path=%s "
                "headers=%s get_params=%s",
                MCP_AUTH_LOG_TAG,
                app_code,
                username,
                bk_tenant_id,
                request.method,
                request.path,
                json.dumps(headers, ensure_ascii=False),
                json.dumps(dict(request.GET), ensure_ascii=False) if request.GET else "",
            )
            if request.method == "POST":
                try:
                    post_params = dict(request.POST) if request.POST else {}
                    logger.info(
                        "[%s] event=request_post_params path=%s post_params=%s",
                        MCP_AUTH_LOG_TAG,
                        request.path,
                        json.dumps(post_params, ensure_ascii=False) if post_params else "(empty)",
                    )
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        "[%s] event=request_post_params_read_failed path=%s error=%s",
                        MCP_AUTH_LOG_TAG,
                        request.path,
                        e,
                    )
            return self._handle_mcp_auth(request, username=username)

        if self.use_api_token_auth(request):
            return self._handle_api_token_auth(request, view)

        # 后台仪表盘渲染豁免
        # TODO: 多租户支持验证
        if "/grafana/" in request.path and not app_code:
            bk_tenant_id = request.META.get("HTTP_X_BK_TENANT_ID") or DEFAULT_TENANT_ID
            request.user = auth.authenticate(username="admin", bk_tenant_id=bk_tenant_id)
            return

        # 校验app_code权限范围
        if not app_code or is_match_api_token(request, bk_tenant_id, app_code):
            if not username or username == "admin":
                username = get_admin_username(bk_tenant_id)
            request.user = auth.authenticate(username=username, bk_tenant_id=bk_tenant_id)
            user = request.user
            if settings.ENABLE_MULTI_TENANT_MODE and user and user.tenant_id != bk_tenant_id:
                logger.error(f"user({user.username}) tenant_id is {user.tenant_id} not match {bk_tenant_id}")
                return HttpResponseForbidden(
                    f"user({user.username}) tenant_id is {user.tenant_id} not match {bk_tenant_id}"
                )
            return

        return HttpResponseForbidden()
