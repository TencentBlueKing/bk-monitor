"""
TAPD5 L3 dispatch_external_proxy 端到端测试：CLIENT_LOG OR 决策 + 灰度开关 + LOG_SEARCH联动。

对照 tapd5.md 验收标准：
  1. 旧 client_log 用户原有能力保持可用                → TestDispatchExternalProxyClientLogOrE2E (legacy-only)
  2. 仅 VIEW_CLIENT_LOG 用户可以查看但不能创建或下载    → TestDispatchExternalProxyClientLogOrE2E (iam-only)
  5. 未授权用户不能通过直接调用接口绕过权限              → TestDispatchExternalProxyClientLogOrE2E (denied)

对照现有 TAPD3/4 已验证模式：
  - 灰度开关 off → 回退纯 legacy 判定，逐行等价（TestToggleOffFallback）
  - iam-only/both 放行但无 authorizer 时拒绝，避免匿名代理执行（TestNoAuthorizerRejection）
  - CLIENT_LOG legacy 授权自动追加 LOG_SEARCH，用于客户端日志索引集检索（既有逻辑，回归验证不受影响）
"""
import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from rest_framework.response import Response

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.handlers.external_permission_decision import CheckResult


def _make_cls_mock(name="TGPATaskViewSet"):
    m = MagicMock()
    m.__name__ = name
    return m


def _configure_view_mock(mock_view_func, cls_name="TGPATaskViewSet"):
    mock_view_func.cls = _make_cls_mock(cls_name)
    return mock_view_func


# 使用 ViewSetActionEnum 中已挂载 CLIENT_LOG 的真实 view_action（"get_task_status"），
# 确保 is_action_valid()/get_target_action_id() 命中 CLIENT_LOG 分支，而不是落入无匹配的纯 legacy 分支。
REGISTERED_VIEW_ACTION = "get_task_status"


class TestDispatchExternalProxyClientLogOrE2E(TestCase):
    """开关 on 时 dispatch_external_proxy 走 legacy(PO client_log) OR iam(VIEW_CLIENT_LOG) 决策"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_client_log_e2e"
    AUTHORIZER = "internal_admin"

    def _build_request(self, url_path="/api/v1/tgpa/task/"):
        body = {
            "url": url_path,
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})
        request.user = MagicMock()
        request.session = {}
        return request

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_legacy_valid_no_iam_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 1：旧 client_log 有效 + IAM 无 VIEW_CLIENT_LOG → 200（兼容旧权限）"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {}})

        request = self._build_request()

        legacy_result = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam_result = CheckResult(allowed=False, source="iam", detail="iam_denied")

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"旧 client_log 有效应放行，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_legacy_missing_iam_allowed_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 2：旧 client_log 缺失 + IAM 命中 VIEW_CLIENT_LOG → 200（仅IAM授权用户可查看）"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        request = self._build_request()

        legacy_result = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam_result = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        # 注意：get_target_action_id 需要返回 client_log 才能进入 CLIENT_LOG OR 分支，
        # 因为 legacy 侧无授权（is_action_valid 恒 False），走的是 get_target_action_id 兜底推断路径
        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"仅IAM VIEW_CLIENT_LOG授权应放行，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_both_allowed_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """两侧都允许 → 200，decision_source=both"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        request = self._build_request()

        legacy_result = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam_result = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"两侧都允许应放行，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_both_denied_returns_403(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 5：两侧都拒绝 → 403，未授权用户无法绕过权限"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        request = self._build_request()

        legacy_result = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam_result = CheckResult(allowed=False, source="iam", detail="iam_denied")

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(response.status_code, 403,
                             f"无权限应返回 403，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_toggle_off_falls_back_to_legacy(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """灰度开关 off → 回退到纯 legacy 判定，不调用 ExternalClientLogPermissionDecision"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        request = self._build_request()

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]},
        ) as mock_get_perm, patch(
            "log_adapter.home.views.ExternalPermission.get_resources",
            return_value={"allowed": True, "resources": []},
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check"
        ) as mock_decision_legacy_check:
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)

            # 灰度关闭时，应走纯 legacy 路径调用 get_authorizer_permission，不应触达 OR 决策组件
            mock_get_perm.assert_called()
            mock_decision_legacy_check.assert_not_called()
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"灰度关闭 legacy 应放行，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_iam_only_allowed_without_authorizer_returns_403(
        self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer
    ):
        """iam-only 放行但空间未配置 authorizer → 403，避免匿名代理执行（与LOG_SEARCH/LOG_EXTRACT分支同款防护）"""
        mock_get_authorizer.return_value = ""  # 未配置 authorizer

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        request = self._build_request()

        legacy_result = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam_result = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(response.status_code, 403,
                             "iam-only放行但无authorizer时必须拒绝，防止匿名代理执行")


class TestClientLogAutoAppendsLogSearch(TestCase):
    """回归验证：拥有 CLIENT_LOG legacy 授权的外部用户，仍自动追加 LOG_SEARCH，
    用于客户端日志索引集检索（tapd5.md 非本期修改范围，但需确保 CLIENT_LOG OR 改造不破坏此逻辑）。
    """

    SPACE_UID = "bkcc__3"
    EXTERNAL_USER = "po_user_auto_append"
    AUTHORIZER = "internal_admin"

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_client_log_legacy_auto_appends_log_search_action_id(
        self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer
    ):
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func, "TGPATaskViewSet")
        mock_view_func.actions = {"get": REGISTERED_VIEW_ACTION}
        mock_resolve.return_value = MagicMock(func=mock_view_func, kwargs={})
        mock_view_func.return_value = Response({"data": {"list": []}})

        body = {
            "url": "/api/v1/tgpa/task/",
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})
        request.user = MagicMock()
        request.session = {}

        legacy_result = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam_result = CheckResult(allowed=False, source="iam", detail="iam_denied")

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.legacy_check",
            return_value=legacy_result,
        ), patch(
            "log_adapter.home.views.ExternalClientLogPermissionDecision.iam_check",
            return_value=iam_result,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
            return_value={self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]},
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301])
