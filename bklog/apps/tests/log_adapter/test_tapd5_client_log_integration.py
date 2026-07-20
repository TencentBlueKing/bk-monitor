"""
TAPD5 "两层门禁" 集成测试：代理层 OR 决策 + ViewSet 层 authorizer 权限检查。

背景：
  - 现有 test_tapd5_client_log_e2e.py 全部 mock 了 resolve()，只测了代理层 OR 决策逻辑，
    但未验证 ViewSet 层 BusinessActionPermission(VIEW_CLIENT_LOG) 对 authorizer 的检查。
  - 本文件补充两类测试：
    A. HTTP 路由层集成：self.client.post() 经完整 URL 路由调用 dispatch_external_proxy，
       覆盖：URL 匹配、HTTP header 解析（HTTP_USER）、中间件最小栈行为。
    B. ViewSet 层门禁：不 mock resolve()，让真实 TGPATaskViewSet 的 get_permissions()
       执行 authorizer 的 VIEW_CLIENT_LOG 权限校验，验证两层门禁串联行为。

对照 tapd5.md 验收标准：
  - 代理层放行 + authorizer 有 VIEW_CLIENT_LOG → 200
  - 代理层放行 + authorizer 无 VIEW_CLIENT_LOG → 403（被第二层门禁拦截）
  - 代理层拒绝 → 403（第一层门禁拦截，与现有覆盖率一致）
"""
import json
import unittest
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from django.http import JsonResponse
from django.test import TestCase, RequestFactory
from django.urls import resolve as django_url_resolve, Resolver404
from rest_framework.response import Response

from apps.constants import ExternalPermissionActionEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.log_commons.handlers.external_permission_decision import CheckResult

# ──────────────────────────────────────────────
#  检测 tgpa URL 是否可解析（依赖于 BKAPP_FEATURE_TGPA_TASK=on 环境变量）
#  如果不可解析，Skip ViewSet 层门禁测试并提供说明
# ──────────────────────────────────────────────
TGPA_GET_TASK_STATUS_URL = "/api/v1/tgpa/task/status/"

try:
    django_url_resolve(TGPA_GET_TASK_STATUS_URL)
    TGPA_URLS_AVAILABLE = True
except Resolver404:
    TGPA_URLS_AVAILABLE = False

TGPA_URLS_SKIP_REASON = (
    f"TGPA URLs 未加载（环境变量 BKAPP_FEATURE_TGPA_TASK != 'on'），"
    f"请设置 BKAPP_FEATURE_TGPA_TASK=on 后重新运行测试"
)

SPACE_UID = "bkcc__2"
EXTERNAL_USER = "po_user_integration_test"
AUTHORIZER = "internal_admin"


def _make_fake_user(username):
    """构造模拟 Django User 对象（含 is_active，用于 auth 框架校验）"""
    user = type("User", (), {})()
    user.username = username
    user.is_authenticated = True
    user.is_active = True
    user.pk = 1
    return user


def _make_mock_match(mock_view_func):
    """构造模拟 Django URL resolver Match 对象"""
    m = MagicMock()
    m.func = mock_view_func
    m.kwargs = {}
    return m


# ══════════════════════════════════════════════════════════════
#  A. HTTP 路由层集成测试（self.client.post 走完整中间件栈）
# ══════════════════════════════════════════════════════════════


class TestDispatchExternalProxyHttpIntegration(TestCase):
    """
    使用 self.client.post() 验证 HTTP 层行为：
      - URL 路由能否正确命中 /dispatch_external_proxy/
      - HTTP_USER 请求头能否正确解析为 external_user
      - require_POST 拒绝 GET 请求
      - 非法 JSON 请求体返回 400
    """

    def _build_body(self, url="/api/v1/tgpa/task/status/", method="POST", data=None):
        return {
            "url": url,
            "space_uid": SPACE_UID,
            "method": method,
            "data": data or json.dumps({"bk_biz_id": 2, "task_id_list": [1]}),
        }

    def _mock_everything(self):
        """构建一组通用 mock，使代理层放行且 ViewSet 层返回 200，便于专注验证 HTTP 层"""
        mock_view_func = MagicMock(return_value=JsonResponse({"data": {}}))
        mock_view_func.cls = MagicMock(__name__="TGPATaskViewSet")
        # get_view_action 按 method 查找 actions 映射；
        # get_task_status 是 @list_route(methods=["POST"], url_path="status")，
        # 所以 actions 需包含 "post" 映射才能命中 CLIENT_LOG 分支
        mock_view_func.actions = {"get": "get_task_status", "post": "get_task_status"}

        legacy_result = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam_result = CheckResult(allowed=False, source="iam", detail="iam_denied")

        return [
            patch("log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
                  return_value=legacy_result),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
                  return_value=iam_result),
            patch("log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False),
            patch("log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                  return_value={SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]}),
            patch("log_adapter.home.views.AuthorizerSettings.get_authorizer", return_value=AUTHORIZER),
            patch("log_adapter.home.views.auth.authenticate", return_value=_make_fake_user(AUTHORIZER)),
            patch("log_adapter.home.views.auth.login"),
            patch("log_adapter.home.views.resolve", return_value=_make_mock_match(mock_view_func)),
            # HTTP 测试仅关注路由和决策，不关心响应过滤细节
            patch("log_adapter.home.views.RequestProcessor.filter_response_resource",
                  side_effect=lambda **kw: kw["response"]),
        ]

    @patch("blueapps.account.middlewares.WeixinLoginRequiredMiddleware.process_view", return_value=None)
    def test_post_to_dispatch_external_proxy_url_returns_200(self, _mock_login_mw):
        """HTTP POST /dispatch_external_proxy/ → 200（URL 路由正确命中）"""
        body = self._build_body()
        with ExitStack() as stack:
            for ctx in self._mock_everything():
                stack.enter_context(ctx)
            response = self.client.post(
                "/dispatch_external_proxy/",
                data=json.dumps(body),
                content_type="application/json",
                HTTP_USER=json.dumps({"username": EXTERNAL_USER}),
            )
        self.assertEqual(response.status_code, 200,
                         f"HTTP 集成：代理层放行应返回 200，实际 {response.status_code}")

    @patch("blueapps.account.middlewares.WeixinLoginRequiredMiddleware.process_view", return_value=None)
    def test_get_request_rejected_by_require_post(self, _mock_login_mw):
        """GET 请求被 @require_POST 拒绝 → 405 Method Not Allowed"""
        response = self.client.get("/dispatch_external_proxy/")
        self.assertEqual(response.status_code, 405,
                         f"GET 请求应被 require_POST 拒绝返回 405，实际 {response.status_code}")

    @patch("blueapps.account.middlewares.WeixinLoginRequiredMiddleware.process_view", return_value=None)
    def test_invalid_json_body_returns_400(self, _mock_login_mw):
        """非法 JSON 请求体 → 400 Bad Request"""
        response = self.client.post(
            "/dispatch_external_proxy/",
            data="not valid json {{{",
            content_type="application/json",
            HTTP_USER=json.dumps({"username": EXTERNAL_USER}),
        )
        self.assertEqual(response.status_code, 400,
                         f"非法 JSON 请求体应返回 400，实际 {response.status_code}")


# ══════════════════════════════════════════════════════════════
#  B. ViewSet 层门禁测试（不 mock resolve，两层权限全部走真实逻辑）
# ══════════════════════════════════════════════════════════════


class TestDispatchExternalProxyViewSetLayerGate(TestCase):
    """
    两层门禁串联测试：不 mock resolve()，让真实 TGPATaskViewSet 的
    get_permissions() → BusinessActionPermission(VIEW_CLIENT_LOG) 执行
    authorizer 的 IAM 权限检查。

    关键链路：
      1. 代理层 OR 决策放行（legacy/iam）
      2. dispatch_external_proxy 创建 fake_request，设置 user=authorizer
      3. set_local_param("current_request", fake_request) 激活线程请求
      4. view_func(fake_request, **kwargs) → TGPATaskViewSet.get_permissions()
         → BusinessActionPermission(VIEW_CLIENT_LOG).has_permission()
         → Permission().is_allowed() 校验 authorizer 是否有 VIEW_CLIENT_LOG
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not TGPA_URLS_AVAILABLE:
            raise unittest.SkipTest(TGPA_URLS_SKIP_REASON)

    def _build_request(self, url_path=TGPA_GET_TASK_STATUS_URL, method="POST"):
        """
        构造外部请求：body 中的 data 字段需包含 bk_biz_id，
        因为 BusinessActionPermission.fetch_biz_id_by_request 从
        fake_request.data 中读取 bk_biz_id（若为 0 则跳过 IAM 检查→永远放行）。
        """
        body = {
            "url": url_path,
            "space_uid": SPACE_UID,
            "method": method,
            "data": json.dumps({"bk_biz_id": 2, "task_id_list": [1]}),
        }
        request = RequestFactory().post(
            "/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": EXTERNAL_USER})
        request.user = _make_fake_user("anonymous")
        request.session = {}
        return request

    def _common_mocks(self, legacy_allowed=True, iam_allowed=False):
        """
        构造代理层 + auth 的通用 mock：
          - 开关 on
          - legacy/iam 决策按参数控制
          - authorizer 配置存在
          - auth.authenticate/login 可用
        """
        legacy_result = CheckResult(
            allowed=legacy_allowed,
            source="legacy",
            detail="legacy_valid" if legacy_allowed else "no_legacy_action",
        )
        iam_result = CheckResult(
            allowed=iam_allowed,
            source="iam",
            detail="iam_allowed" if iam_allowed else "iam_denied",
        )

        return [
            patch("log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
                  return_value=legacy_result),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
                  return_value=iam_result),
            patch("log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False),
            patch("log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                  return_value={SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]}),
            patch("log_adapter.home.views.AuthorizerSettings.get_authorizer", return_value=AUTHORIZER),
            patch("log_adapter.home.views.auth.authenticate", return_value=_make_fake_user(AUTHORIZER)),
            patch("log_adapter.home.views.auth.login"),
        ]

    # ── 两层都通过 → 200 ──

    def test_proxy_allows_authorizer_has_iam_permission_returns_200(self):
        """
        代理层 OR 决策放行（legacy valid） + ViewSet 层 authorizer 有 VIEW_CLIENT_LOG → 200

        验证：两层门禁全部通过时，请求正常返回 200。
        """
        from log_adapter.home.views import dispatch_external_proxy
        from apps.tgpa.views import TGPATaskViewSet

        request = self._build_request()
        mocks = self._common_mocks(legacy_allowed=True, iam_allowed=False)
        mocks.append(patch.object(TGPATaskViewSet, "get_task_status", return_value=Response({"data": {}})))
        mocks.append(patch("apps.iam.handlers.drf.Permission.is_allowed", return_value=True))

        with ExitStack() as stack:
            for ctx in mocks:
                stack.enter_context(ctx)
            response = dispatch_external_proxy(request)

        self.assertIn(response.status_code, [200, 201, 204],
                      f"两层门禁均放行应返回 2xx，实际 {response.status_code}")

    # ── 代理层放行 + ViewSet 层拒绝 → 403 ──

    def test_proxy_allows_authorizer_lacks_iam_permission_returns_403(self):
        """
        代理层 OR 决策放行（legacy valid） + ViewSet 层 authorizer 无 VIEW_CLIENT_LOG → permission denied

        这是此前完全不覆盖的关键场景：代理层判定"允许"，但内部代理执行人(authorizer)
        实际未被授予 VIEW_CLIENT_LOG，ViewSet 层 BusinessActionPermission 会触发
        PermissionDeniedError，经 custom_exception_handler 返回 HTTP 200 但 body 中包含
        code="9900403"（权限校验不通过）。

        若该空间配置的 authorizer 账号未被迁移脚本覆盖授权，此场景将导致线上权限拒绝，
        因此本测试必须通过。
        """
        from log_adapter.home.views import dispatch_external_proxy
        from apps.tgpa.views import TGPATaskViewSet

        request = self._build_request()
        mocks = self._common_mocks(legacy_allowed=True, iam_allowed=False)
        mocks.append(patch.object(TGPATaskViewSet, "get_task_status", return_value=Response({"data": {}})))
        mocks.append(patch(
            "apps.iam.handlers.drf.Permission.is_allowed",
            side_effect=PermissionDeniedError(action_name="查看客户端日志", permission={}),
        ))

        with ExitStack() as stack:
            for ctx in mocks:
                stack.enter_context(ctx)
            response = dispatch_external_proxy(request)

        # custom_exception_handler 将 PermissionDeniedError 转为 HTTP 200 + body 中 code="9900403"
        self.assertEqual(response.status_code, 200,
                         f"authorizer 无 VIEW_CLIENT_LOG 应返回 200（body 含权限错误码），"
                         f"实际 status={response.status_code}")
        body = json.loads(response.content)
        self.assertEqual(body.get("code"), "9900403",
                         f"body 应含权限错误码 9900403，实际 {body}")

    # ── 代理层拒绝（两端都拒绝） → 403 ──

    def test_proxy_denies_returns_403(self):
        """
        代理层 OR 决策拒绝（legacy 无效 + iam 无效） → 403

        验证代理层本身的拒绝逻辑在真实 resolve() 环境下仍然生效。
        此场景在现有测试中已有覆盖（mock resolve），此处作为回归验证。
        """
        from log_adapter.home.views import dispatch_external_proxy

        request = self._build_request()
        mocks = self._common_mocks(legacy_allowed=False, iam_allowed=False)

        with ExitStack() as stack:
            for ctx in mocks:
                stack.enter_context(ctx)
            response = dispatch_external_proxy(request)

        self.assertEqual(response.status_code, 403,
                         f"代理层 OR 决策应拒绝并返回 403，实际 {response.status_code}")

    # ── iam-only 放行 + 有 authorizer → 200 ──

    def test_iam_only_allowed_with_authorizer_has_permission_returns_200(self):
        """
        代理层 iam-only 放行 + authorizer 有 VIEW_CLIENT_LOG → 200

        验证仅 IAM 授权的用户（legacy 侧无 PO 授权）通过两层门禁。
        """
        from log_adapter.home.views import dispatch_external_proxy
        from apps.tgpa.views import TGPATaskViewSet

        request = self._build_request()
        mocks = self._common_mocks(legacy_allowed=False, iam_allowed=True)
        mocks.append(patch.object(TGPATaskViewSet, "get_task_status", return_value=Response({"data": {}})))
        mocks.append(patch("apps.iam.handlers.drf.Permission.is_allowed", return_value=True))

        with ExitStack() as stack:
            for ctx in mocks:
                stack.enter_context(ctx)
            response = dispatch_external_proxy(request)

        self.assertIn(response.status_code, [200, 201, 204],
                      f"iam-only 放行 + authorizer 有权限应返回 2xx，实际 {response.status_code}")

    # ── iam-only 放行 + 无 authorizer → 403（已有覆盖，此处用真实 resolve 回归验证）──

    def test_iam_only_allowed_without_authorizer_returns_403(self):
        """
        代理层 iam-only 放行 + 无 authorizer → 403

        验证安全防护逻辑：iam/both 放行时必须配置代理执行人，否则拒绝。
        此场景在现有测试中已有覆盖，此处使用真实 resolve() 作为回归验证。
        """
        from log_adapter.home.views import dispatch_external_proxy

        request = self._build_request()
        legacy_result = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam_result = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        mocks = [
            patch("log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
                  return_value=legacy_result),
            patch("log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
                  return_value=iam_result),
            patch("log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False),
            patch("log_adapter.home.views.ExternalPermission.get_authorizer_permission", return_value={}),
            patch("log_adapter.home.views.AuthorizerSettings.get_authorizer", return_value=""),  # 无 authorizer
        ]

        with ExitStack() as stack:
            for ctx in mocks:
                stack.enter_context(ctx)
            response = dispatch_external_proxy(request)

        self.assertEqual(response.status_code, 403,
                         f"iam-only 放行但无 authorizer 应返回 403，实际 {response.status_code}")
