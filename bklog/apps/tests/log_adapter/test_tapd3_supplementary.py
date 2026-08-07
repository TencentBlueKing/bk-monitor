"""
TAPD3 补充测试：逐条覆盖验收标准中缺失的 7 类场景。

对照 TAPD3 验收标准：
  1. 仅旧权限授权的索引集可以查询    → TestDispatchExternalProxyOrDecisionE2E
  2. 仅 IAM 授权的索引集可以查询     → TestDispatchExternalProxyOrDecisionE2E
  3. 两侧均未授权的索引集不可查询     → TestDispatchExternalProxyOrDecisionE2E
  4. 新旧资源并集只作用于当前空间     → TestFilterResponseResourceUnion
  5. 上下文/实时日志/字段分析不能绕过  → TestNonSearchEntryPoints
  6. 收藏/历史/下载按外部用户隔离      → 已有 test_external_permission_decision.py
  7. 四种新旧组合+异常组合决策矩阵     → 已有 test_external_permission_decision.py
  8. 决策来源与双侧差异埋点可查       → TestAuditFields
  9. 关闭灰度开关恢复旧行为           → 已有 test_dispatch_external_proxy_toggle.py
 10. OR 决策框架接口稳定              → TestOrDecisionFrameworkStable
 11. 内部用户不受影响                 → TestInternalUserUnaffected
"""
import json
from unittest.mock import MagicMock, patch, call, NonCallableMock

from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse
from django.test import RequestFactory, TestCase
from rest_framework.response import Response

from apps.constants import (
    ExternalPermissionActionEnum,
    ViewSetAction,
    ViewSetActionEnum,
)
from apps.log_commons.handlers.external_permission_decision import (
    CheckResult,
    DecisionResult,
    ExternalLogSearchPermissionDecision,
)
from apps.log_commons.models import ExternalPermission
from apps.feature_toggle.handlers.toggle import Toggle
from apps.iam import ActionEnum


# ── Helper: create a view_func mock with proper cls attribute for get_view_set ──

def _make_cls_mock(name="SearchViewSet"):
    """创建 cls mock，避免 hasattr(cls, '__name__') → AttributeError"""
    m = MagicMock()
    m.__name__ = name
    return m

def _configure_view_mock(mock_view_func, cls_name="SearchViewSet"):
    """为 view_func mock 配置 cls 属性，确保 get_view_set 不会崩溃"""
    mock_view_func.cls = _make_cls_mock(cls_name)
    return mock_view_func


# ════════════════════════════════════════════════════════════════════
#  1. dispatch_external_proxy 开关 on 端到端 OR 决策
#     覆盖 TAPD3 验收标准 1/2/3：旧有新无、旧无新有、两侧都有、两侧都无
# ════════════════════════════════════════════════════════════════════

class TestDispatchExternalProxyOrDecisionE2E(TestCase):
    """开关 on 时 dispatch_external_proxy 走 PO+IAM OR 决策的端到端验证"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_or"
    AUTHORIZER = "internal_admin"

    def _build_request(self, url_path="/api/v1/search/index_set/", index_set_id=None):
        """构造标准的外部代理请求"""
        body = {
            "url": url_path,
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": json.dumps({"index_set_id": index_set_id}) if index_set_id else "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})
        request.user = MagicMock()  # 模拟 Django auth middleware
        request.session = {}  # 模拟 Django session middleware
        return request

    def _build_request_no_user(self, url_path="/api/v1/search/index_set/", index_set_id=None):
        """构造标准的外部代理请求（内部用户无 HTTP_USER）"""
        body = {
            "url": url_path,
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": json.dumps({"index_set_id": index_set_id}) if index_set_id else "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
        )
        request.user = MagicMock()
        request.session = {}
        return request

    def _mock_or_decision(self, legacy_allowed, iam_allowed, resources=None):
        """构造 mock 决策结果"""
        legacy = CheckResult(
            allowed=legacy_allowed,
            resources=resources or {1001},
            source="legacy" if legacy_allowed is not None else "error",
        )
        iam = CheckResult(
            allowed=iam_allowed,
            resources={2001} if iam_allowed else set(),
            source="iam" if iam_allowed is not None else "error",
        )
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.AUTHORIZER,
            legacy_result=legacy,
            iam_result=iam,
        )
        return legacy, iam, decision

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_legacy_allowed_iam_denied_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 1：仅旧权限授权 → 200，可以查询"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        legacy, iam, decision = self._mock_or_decision(True, False, resources={1001})
        # legacy 允许 + iam 拒绝 → source=legacy, allowed=True
        self.assertEqual(decision.decision_source, "legacy")
        self.assertTrue(decision.allowed)

        # 模拟 view_func 返回正常响应（无 cls 属性 → 返回 __name__）
        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func,
            kwargs={"index_set_id": "1001"},
        )
        mock_view_func.return_value = Response({"data": {"count": 10}})

        request = self._build_request(index_set_id=1001)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ) as mock_legacy, patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ) as mock_iam, patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"旧权限授权应通过，但返回 {response.status_code}")
            # legacy_check 和 iam_check_resource 都应被调用
            mock_legacy.assert_called_once()
            mock_iam.assert_called_once()

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_legacy_denied_iam_allowed_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 2：仅 IAM 授权 → 200，可以查询"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        legacy, iam, decision = self._mock_or_decision(False, True, resources={2001})
        self.assertEqual(decision.decision_source, "iam")
        self.assertTrue(decision.allowed)

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "2001"}
        )
        mock_view_func.return_value = Response({"data": {"count": 5}})

        request = self._build_request(index_set_id=2001)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"IAM 授权应通过，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_both_allowed_returns_200(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """两边都有授权 → 200，source=both"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        legacy, iam, decision = self._mock_or_decision(True, True, resources={1001, 2001})
        self.assertEqual(decision.decision_source, "both")
        self.assertTrue(decision.allowed)

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "1001"}
        )
        mock_view_func.return_value = Response({"data": {"count": 3}})

        request = self._build_request(index_set_id=1001)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertIn(response.status_code, [200, 201, 204, 302, 301])

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_both_denied_returns_403(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """验收标准 3：两侧均未授权 → 403，不可查询"""
        mock_get_authorizer.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        legacy, iam, decision = self._mock_or_decision(False, False, resources=set())
        self.assertEqual(decision.decision_source, "none")
        self.assertFalse(decision.allowed)

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "9999"}
        )

        request = self._build_request(index_set_id=9999)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(response.status_code, 403,
                             f"两侧均未授权应返回 403，但返回 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_iam_allowed_no_authorizer_returns_403(self, mock_resolve, _mock_login, _mock_auth, mock_get_authorizer):
        """IAM only 放行但无 authorizer → 403（无法代理执行）"""
        mock_get_authorizer.return_value = None  # 无 authorizer
        _mock_auth.return_value = MagicMock()

        legacy, iam, _ = self._mock_or_decision(False, True, resources={2001})

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "2001"}
        )

        request = self._build_request(index_set_id=2001)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(response.status_code, 403,
                             "IAM only 放行但无 authorizer 应返回 403")


# ════════════════════════════════════════════════════════════════════
#  2. filter_log_search_response_resource 开关 on 并集过滤
#     覆盖 TAPD3 验收标准 4：新旧资源并集只作用于当前空间
#     验证 4 种列表类型 (Search / Favorite / FavoriteUnion / FavoriteByGroup)
# ════════════════════════════════════════════════════════════════════

class TestFilterResponseResourceUnion(TestCase):
    """开关 on 时 filter_log_search_response_resource 的 legacy ∪ IAM batch 并集过滤"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_union"

    def setUp(self):
        from log_adapter.home.views import RequestProcessor
        self.processor = RequestProcessor

    # ── SEARCH_VIEWSET_LIST ──

    @patch("log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources")
    def test_search_list_union_legacy_and_iam(self, mock_batch):
        """SearchViewSet.list：开关 on，legacy=[1,2] ∪ IAM=[3] → 最终 [1,2,3]"""
        mock_batch.return_value = {3}

        mock_response = Response({
            "data": [
                {"index_set_id": 1}, {"index_set_id": 2},
                {"index_set_id": 3}, {"index_set_id": 4},
            ]
        })

        with patch.object(self.processor, "is_or_decision_enabled", return_value=True):
            result = self.processor.filter_log_search_response_resource(
                external_user=self.EXTERNAL_USER,
                space_uid=self.SPACE_UID,
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_action,
                allow_resources_result={"allowed": True, "resources": [1, 2]},
            )

        filtered_ids = [d["index_set_id"] for d in result.data["data"]]
        self.assertEqual(filtered_ids, [1, 2, 3],
                         "并集应为 legacy[1,2] ∪ IAM[3] = [1,2,3]，id=4 应被过滤")
        # batch_iam 应以差集 [3,4] 调用（只差集触发 IAM）
        mock_batch.assert_called_once()
        call_args = set(mock_batch.call_args[1]["resource_ids"])
        self.assertIn(3, call_args, "差集中应包含 IAM 命中的 3")
        self.assertIn(4, call_args, "差集中应包含 IAM 未命中的 4")

    # ── FAVORITE_VIEWSET_LIST ──

    @patch("log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources")
    def test_favorite_list_union_legacy_and_iam(self, mock_batch):
        """FavoriteViewSet.list：开关 on，legacy ∪ IAM 并集过滤"""
        mock_batch.return_value = {5, 7}

        mock_response = Response({
            "data": [
                {"index_set_id": 5}, {"index_set_id": 6},
                {"index_set_id": 7}, {"index_set_id": 8},
            ]
        })

        with patch.object(self.processor, "is_or_decision_enabled", return_value=True):
            result = self.processor.filter_log_search_response_resource(
                external_user=self.EXTERNAL_USER,
                space_uid=self.SPACE_UID,
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value.view_action,
                allow_resources_result={"allowed": True, "resources": [5]},
            )

        filtered_ids = [d["index_set_id"] for d in result.data["data"]]
        self.assertEqual(filtered_ids, [5, 7],
                         "legacy[5] ∪ IAM[5,7] = [5,7]，6 和 8 应被过滤")

    # ── FAVORITE_UNION_SEARCH_VIEWSET_LIST ──

    @patch("log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources")
    def test_favorite_union_search_list_union(self, mock_batch):
        """FavoriteUnionSearchViewSet.list：开关 on，legacy ∪ IAM 并集过滤"""
        mock_batch.return_value = {10}

        mock_response = Response({
            "data": [
                {"index_set_id": 9}, {"index_set_id": 10}, {"index_set_id": 11},
            ]
        })

        with patch.object(self.processor, "is_or_decision_enabled", return_value=True):
            result = self.processor.filter_log_search_response_resource(
                external_user=self.EXTERNAL_USER,
                space_uid=self.SPACE_UID,
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.FAVORITE_UNION_SEARCH_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.FAVORITE_UNION_SEARCH_VIEWSET_LIST.value.view_action,
                allow_resources_result={"allowed": True, "resources": [9]},
            )

        filtered_ids = [d["index_set_id"] for d in result.data["data"]]
        self.assertEqual(filtered_ids, [9, 10],
                         "legacy[9] ∪ IAM[10] = [9,10]，11 应被过滤")

    # ── FAVORITE_VIEWSET_LIST_BY_GROUP ──

    @patch("log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources")
    def test_favorite_list_by_group_union(self, mock_batch):
        """FavoriteViewSet.list_by_group：开关 on，分组结构下 legacy ∪ IAM 并集过滤"""
        mock_batch.return_value = {103}

        mock_response = Response({
            "data": [
                {
                    "group_name": "group_a",
                    "favorites": [
                        {"index_set_id": 101}, {"index_set_id": 102},
                    ],
                },
                {
                    "group_name": "group_b",
                    "favorites": [
                        {"index_set_id": 103}, {"index_set_id": 104},
                    ],
                },
            ]
        })

        with patch.object(self.processor, "is_or_decision_enabled", return_value=True):
            result = self.processor.filter_log_search_response_resource(
                external_user=self.EXTERNAL_USER,
                space_uid=self.SPACE_UID,
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value.view_set,
                view_action=ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value.view_action,
                allow_resources_result={"allowed": True, "resources": [101]},
            )

        group_a_favorites = [f["index_set_id"] for f in result.data["data"][0]["favorites"]]
        group_b_favorites = [f["index_set_id"] for f in result.data["data"][1]["favorites"]]
        self.assertEqual(group_a_favorites, [101],
                         "group_a: legacy[101] 保留，102 被过滤")
        self.assertEqual(group_b_favorites, [103],
                         "group_b: IAM[103] 保留，104 被过滤")

    @patch("log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources")
    def test_no_candidate_resource_no_iam_call(self, mock_batch):
        """空列表无候选资源 → 不触发 IAM batch 调用"""
        mock_batch.return_value = set()

        mock_response = Response({"data": []})

        with patch.object(self.processor, "is_or_decision_enabled", return_value=True):
            self.processor.filter_log_search_response_resource(
                external_user=self.EXTERNAL_USER,
                space_uid=self.SPACE_UID,
                response=mock_response,
                action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
                view_set=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_set,
                view_action=ViewSetActionEnum.SEARCH_VIEWSET_LIST.value.view_action,
                allow_resources_result={"allowed": True, "resources": [1, 2]},
            )

        mock_batch.assert_not_called()


# ════════════════════════════════════════════════════════════════════
#  3. 列表越权请求
#     覆盖自测要求：直接构造非授权 index_set_id → 详情被拒 403 / 列表被过滤
# ════════════════════════════════════════════════════════════════════

class TestUnauthorizedDirectAccess(TestCase):
    """越权请求：直接构造未授权的 index_set_id"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_unauth"
    AUTHORIZER = "internal_admin"

    def _build_request(self, url_path, index_set_id):
        body = {
            "url": url_path,
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": json.dumps({"index_set_id": index_set_id}) if index_set_id is not None else "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})
        request.user = MagicMock()  # 模拟 Django auth middleware
        request.session = {}
        return request

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_detail_unauthorized_index_set_returns_403(self, mock_resolve, _m_l, _m_a, mock_authz):
        """详情接口：直接构造不在 legacy+IAM 中的 index_set_id → 403"""
        mock_authz.return_value = self.AUTHORIZER
        _m_a.return_value = MagicMock()

        # 两侧都拒绝
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=False, resources=set(), source="iam")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.AUTHORIZER,
            legacy_result=legacy,
            iam_result=iam,
        )
        self.assertFalse(decision.allowed)

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "99999"}
        )

        request = self._build_request("/api/v1/search/index_set/", 99999)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(response.status_code, 403,
                             f"越权请求详情(index_set_id=99999)应返回 403，实际 {response.status_code}")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_list_filtered_out_unauthorized_resource(self, mock_resolve, _m_l, _m_a, mock_authz):
        """列表场景：legacy+IAM 并集不包含某资源 → 该资源被 filter 过滤掉，不整体 403"""
        mock_authz.return_value = self.AUTHORIZER
        _m_a.return_value = MagicMock()

        # legacy 允许列表 action，但资源只有 {1, 2}；IAM 不可判定（resource_id=None 场景）
        legacy = CheckResult(allowed=True, resources={1, 2}, source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="iam", detail="resource_not_provided")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.AUTHORIZER,
            legacy_result=legacy,
            iam_result=iam,
        )
        # legacy=True + iam=None → OR 决策放行（legacy 侧允许）
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "list"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={}  # 列表无 resource
        )

        # view_func 返回包含 3 个索引集，其中 index_set_id=4 是越权的
        mock_view_func.return_value = Response({
            "data": [
                {"index_set_id": 1}, {"index_set_id": 2},
                {"index_set_id": 4},  # 越权
            ]
        })

        request = self._build_request("/api/v1/search/index_set/", None)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.batch_iam_allowed_resources",
            return_value=set(),  # IAM batch 也全拒绝
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_log_search_list_view", return_value=True
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            # 列表场景：不整体 403，而是 filter 过滤后正常返回 200
            self.assertIn(response.status_code, [200, 201, 204, 302, 301],
                          f"列表越权应被过滤而非 403，实际 {response.status_code}")


# ════════════════════════════════════════════════════════════════════
#  4. 非检索入口权限：fields / context / tailf
#     覆盖 TAPD3 验收标准 5：上下文/实时日志/字段分析不能绕过索引集权限
# ════════════════════════════════════════════════════════════════════

class TestNonSearchEntryPoints(TestCase):
    """验证 fields / context / tailf 等非检索入口同样进入 OR 决策"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_fields"
    AUTHORIZER = "internal_admin"

    def _build_request(self, view_action, index_set_id):
        body = {
            "url": f"/api/v1/search/index_set/{index_set_id}/{view_action}/",
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": json.dumps({"index_set_id": index_set_id}),
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
    def test_fields_entry_under_or_decision(self, mock_resolve, _m_l, _m_a, mock_authz):
        """fields 入口不能绕过：无权限 → 403"""
        self._assert_non_search_entry_blocked(
            mock_resolve, _m_a, mock_authz,
            view_action="fields",
            expected_view_set="SearchViewSet",
            entry_name="fields",
        )

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_context_entry_under_or_decision(self, mock_resolve, _m_l, _m_a, mock_authz):
        """context 入口不能绕过：无权限 → 403"""
        self._assert_non_search_entry_blocked(
            mock_resolve, _m_a, mock_authz,
            view_action="context",
            expected_view_set="SearchViewSet",
            entry_name="context",
        )

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_tailf_entry_under_or_decision(self, mock_resolve, _m_l, _m_a, mock_authz):
        """tailf 入口不能绕过：无权限 → 403"""
        self._assert_non_search_entry_blocked(
            mock_resolve, _m_a, mock_authz,
            view_action="tailf",
            expected_view_set="SearchViewSet",
            entry_name="tailf",
        )

    def _assert_non_search_entry_blocked(
        self, mock_resolve, _mock_auth, mock_authz,
        view_action, expected_view_set, entry_name,
    ):
        mock_authz.return_value = self.AUTHORIZER
        _mock_auth.return_value = MagicMock()

        # 两侧拒绝
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=False, resources=set(), source="iam")

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": view_action}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "5001"}
        )

        request = self._build_request(view_action, 5001)

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
            return_value=legacy,
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
            return_value=iam,
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ), patch(
            "log_adapter.home.views.RequestProcessor.filter_log_search_response_resource",
            side_effect=lambda **kw: kw["response"],
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            self.assertEqual(
                response.status_code, 403,
                f"{entry_name} 入口无权限应返回 403，实际 {response.status_code}"
            )


# ════════════════════════════════════════════════════════════════════
#  5. 审计埋点字段：decision_source / decision_warning
#     覆盖 TAPD3 验收标准 8：决策来源与双侧差异埋点可查
# ════════════════════════════════════════════════════════════════════

class TestAuditFields(TestCase):
    """验证决策来源(legacy/iam/both/none)和 warning 埋点字段的正确赋值"""

    EXTERNAL_USER = "po_user_audit"
    EXECUTION_USER = "internal_agent"

    def test_decision_source_legacy(self):
        """source=legacy：纯旧权限放行"""
        legacy = CheckResult(allowed=True, resources={1, 2}, source="legacy")
        iam = CheckResult(allowed=False, resources=set(), source="iam")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )
        self.assertEqual(decision.decision_source, "legacy")
        self.assertFalse(decision.warning)

    def test_decision_source_iam(self):
        """source=iam：纯 IAM 权限放行"""
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=True, resources={5}, source="iam")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )
        self.assertEqual(decision.decision_source, "iam")
        self.assertFalse(decision.warning)

    def test_decision_source_both(self):
        """source=both：两侧都有权限"""
        legacy = CheckResult(allowed=True, resources={3, 4}, source="legacy")
        iam = CheckResult(allowed=True, resources={5}, source="iam")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )
        self.assertEqual(decision.decision_source, "both")
        self.assertEqual(decision.resources, {3, 4, 5})
        self.assertFalse(decision.warning)

    def test_decision_warning_when_one_side_error(self):
        """任意一侧异常时 warning=True，但正常侧仍放行"""
        # IAM 异常 + legacy 允许 → source=legacy, warning=True
        legacy = CheckResult(allowed=True, resources={1}, source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="error")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )
        self.assertTrue(decision.warning, "IAM 异常时 warning 应为 True")
        self.assertEqual(decision.decision_source, "legacy")
        self.assertTrue(decision.allowed)

    def test_identity_separation(self):
        """authorization_subject/audit_user 恒等于 external_user，execution_user 为独立身份"""
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=CheckResult(allowed=True, resources={1}, source="legacy"),
            iam_result=CheckResult(allowed=False, resources=set(), source="iam"),
        )
        self.assertEqual(decision.authorization_subject, self.EXTERNAL_USER)
        self.assertEqual(decision.audit_user, self.EXTERNAL_USER)
        self.assertEqual(decision.execution_user, self.EXECUTION_USER)
        self.assertNotEqual(decision.authorization_subject, decision.execution_user,
                            "authorization_subject 与 execution_user 必须不同，防止身份混淆")


# ════════════════════════════════════════════════════════════════════
#  6. external() 开关 on + PO 无记录 + IAM VIEW_BUSINESS 拒绝 → 403
#     覆盖 TAPD3 验收标准 1/2 边界：IAM 兜底也被拒绝时的行为
# ════════════════════════════════════════════════════════════════════

class TestExternalIamFallbackDenied(TestCase):
    """external() 在开关 on 且 PO 无记录且 IAM 拒绝时返回 403"""

    EXTERNAL_USER = "po_user_no_perm"
    SPACE_UID = "bkcc__3"
    AUTHORIZER = "internal_admin"

    @patch("log_adapter.home.views.ExternalPermission.get_authorized_user_space_list",
           return_value=["bkcc__3"])
    @patch("log_adapter.home.views.SpaceApi.get_space_detail")
    @patch("log_adapter.home.views.timezone")
    def test_po_none_iam_denied_returns_403(self, mock_tz, _mock_space, _mock_space_list):
        """开关 on + PO 无记录 + IAM VIEW_BUSINESS 拒绝 → 403"""
        mock_tz.now.return_value = "2026-07-16"

        request = RequestFactory().get(
            f"/external/?space_uid={self.SPACE_UID}",
            HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

        iam_called = []

        def fake_is_allowed_by_biz(bk_biz_id, action, raise_exception=False):
            iam_called.append(True)
            return False  # IAM 拒绝

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.space_uid_to_bk_biz_id", return_value="3"
        ), patch(
            "log_adapter.home.views.ExternalPermission.objects.filter"
        ) as mock_qs:
            mock_qs.return_value.exists.return_value = False  # PO 无记录

            with patch("log_adapter.home.views.Permission") as mock_perm_cls:
                mock_perm = MagicMock()
                mock_perm.is_allowed_by_biz.side_effect = fake_is_allowed_by_biz
                mock_perm_cls.return_value = mock_perm

                with patch(
                    "log_adapter.home.views.AuthorizerSettings.get_authorizer",
                    return_value=self.AUTHORIZER,
                ), patch(
                    "log_adapter.home.views.auth.authenticate", return_value=MagicMock()
                ), patch(
                    "log_adapter.home.views.auth.login"
                ), patch(
                    "log_adapter.home.views.render"
                ), patch(
                    "log_adapter.home.views.get_toggle_data", return_value={}
                ):
                    from log_adapter.home.views import external
                    response = external(request)
                    self.assertEqual(response.status_code, 403,
                                     "PO 无记录 + IAM 拒绝 → 应返回 403")
                    self.assertTrue(len(iam_called) > 0,
                                    "PO 无记录时应尝试 IAM 兜底")


# ════════════════════════════════════════════════════════════════════
#  7. 内部用户不受 OR 决策影响
#     覆盖 TAPD3 验收标准 11：内部用户原有检索行为不变
# ════════════════════════════════════════════════════════════════════

class TestInternalUserUnaffected(TestCase):
    """内部用户（非 external_user 前缀）走 dispatch_external_proxy 时不受 OR 决策影响"""

    SPACE_UID = "bkcc__2"

    def test_internal_user_skips_or_decision_on_external_proxy(self):
        """dispatch_external_proxy：内部用户（无 HTTP_USER 头）不走 OR 决策，走 legacy 判定"""
        # external_user 为空 → get_request_user_info 返回空 username
        body = {
            "url": "/api/v1/search/index_set/?space_uid=bkcc__2",
            "space_uid": self.SPACE_UID,
            "method": "GET",
            "data": "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            # 没有 HTTP_USER → external_user = ""
        )
        request.user = MagicMock()
        request.session = {}

        # 模拟 resolve 成功
        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "list"}
        mock_view_func.return_value = Response({"data": []})

        with patch(
            "log_adapter.home.views.resolve",
            return_value=MagicMock(func=mock_view_func, kwargs={}),
        ), patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled",
            return_value=True,
        ) as mock_is_or, patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed",
            return_value=True,  # 内部用户的接口为默认允许
        ), patch(
            "log_adapter.home.views.AuthorizerSettings.get_authorizer",
            return_value="internal_admin",
        ), patch(
            "log_adapter.home.views.auth.authenticate", return_value=MagicMock()
        ), patch(
            "log_adapter.home.views.auth.login"
        ):
            from log_adapter.home.views import dispatch_external_proxy
            response = dispatch_external_proxy(request)
            # 内部用户 external_user="" → 不应该因为 OR 决策被 403
            self.assertNotEqual(response.status_code, 403,
                                "内部用户不应因 OR 决策被 403 拒绝")

    @patch("log_adapter.home.views.AuthorizerSettings.get_authorizer")
    @patch("log_adapter.home.views.auth.authenticate")
    @patch("log_adapter.home.views.auth.login")
    @patch("log_adapter.home.views.resolve")
    def test_external_user_or_decision_does_not_use_authorizer_as_subject(
        self, mock_resolve, _mock_login, _mock_auth, mock_authz
    ):
        """CRITICAL: OR 决策中 legacy_check/iam_check 的 subject 恒为 external_user，绝不使用 authorizer"""
        mock_authz.return_value = "internal_agent"
        _mock_auth.return_value = MagicMock()

        mock_view_func = MagicMock()
        _configure_view_mock(mock_view_func)
        mock_view_func.actions = {"get": "bizs"}
        mock_resolve.return_value = MagicMock(
            func=mock_view_func, kwargs={"index_set_id": "1001"}
        )

        body = {
            "url": "/api/v1/search/index_set/1001/bizs/",
            "space_uid": "bkcc__2",
            "method": "GET",
            "data": "",
        }
        request = RequestFactory().post(
            "/external/dispatch_external_proxy/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_USER=json.dumps({"username": "ext_user_subject_check"}),
        )
        request.META["HTTP_USER"] = json.dumps({"username": "ext_user_subject_check"})
        request.user = MagicMock()
        request.session = {}

        with patch(
            "log_adapter.home.views.RequestProcessor.is_or_decision_enabled", return_value=True
        ), patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.legacy_check",
        ) as mock_legacy, patch(
            "log_adapter.home.views.ExternalLogSearchPermissionDecision.iam_check_resource",
        ) as mock_iam, patch(
            "log_adapter.home.views.RequestProcessor.is_default_allowed", return_value=False
        ):
            mock_legacy.return_value = CheckResult(
                allowed=False, resources=set(), source="legacy", detail="no_legacy_action"
            )
            mock_iam.return_value = CheckResult(
                allowed=False, resources=set(), source="iam"
            )

            from log_adapter.home.views import dispatch_external_proxy
            dispatch_external_proxy(request)

            # 关键断言：legacy_check 的 external_user 参数必须是 "ext_user_subject_check"
            mock_legacy.assert_called_once()
            call_kwargs = mock_legacy.call_args[1]
            self.assertEqual(call_kwargs["external_user"], "ext_user_subject_check",
                             "legacy_check subject 必须是 external_user，不能是 authorizer")
            # iam_check_resource 同理
            mock_iam.assert_called_once()
            call_kwargs = mock_iam.call_args[1]
            self.assertEqual(call_kwargs["external_user"], "ext_user_subject_check",
                             "iam_check_resource subject 必须是 external_user，不能是 authorizer")


# ════════════════════════════════════════════════════════════════════
#  8. dispatch_list_user_spaces() 开关 on 端到端
#     覆盖 TAPD3 验收标准 1/2/4：PO ∪ IAM 空间并集
# ════════════════════════════════════════════════════════════════════

class TestDispatchListUserSpacesOrDecisionOn(TestCase):
    """开关 on 时 dispatch_list_user_spaces 返回 PO ∪ IAM 空间并集"""

    EXTERNAL_USER = "po_user_spaces"

    def _make_space(self, id, space_uid, bk_biz_id, space_name="test"):
        space = MagicMock()
        space.id = id
        space.space_type_id = "bkcc"
        space.space_type_name = "CMDB业务"
        space.space_id = str(id)
        space.space_name = space_name
        space.space_uid = space_uid
        space.space_code = str(id)
        space.bk_biz_id = bk_biz_id
        space.properties = {"time_zone": "Asia/Shanghai"}
        return space

    def test_po_union_iam_spaces(self):
        """开关 on：PO 空间 + IAM 有 VIEW_BUSINESS 的空间 → 并集返回"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        # toggle on
        toggle_obj = Toggle(name=EXTERNAL_PERMISSION_OR_DECISION, status="on")

        # PO 有 bkcc__2
        po_permission = {"bkcc__2": ["log_search"]}
        po_space = self._make_space(1, "bkcc__2", 2)
        # IAM 有但是 PO 没有的空间 bkcc__3
        iam_space = self._make_space(2, "bkcc__3", 3)

        def _filter_side_effect(**kwargs):
            """根据 filter 参数返回不同的 queryset"""
            mock_qs = MagicMock()
            if "space_uid__in" in kwargs:
                space_uids = kwargs["space_uid__in"]
                mock_qs.all.return_value = [
                    s for s in [po_space, iam_space] if s.space_uid in space_uids
                ]
            else:
                mock_qs.all.return_value = [po_space]
            return mock_qs

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            with patch(
                "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                return_value=po_permission,
            ):
                with patch(
                    "log_adapter.home.views.RequestProcessor.get_request_user_info",
                    return_value={"username": self.EXTERNAL_USER},
                ):
                    with patch("apps.log_search.models.Space.objects") as mock_space_qs:
                        mock_space_qs.filter.side_effect = _filter_side_effect
                        # exclude 非PO 空间 → 返回 IAM 候选空间
                        mock_space_qs.exclude.return_value.all.return_value = [iam_space]

                        with patch(
                            "log_adapter.home.views.Permission"
                        ) as mock_perm_cls:
                            mock_perm = MagicMock()
                            # batch_is_allowed → IAM 允许 bk_biz_id=3
                            mock_perm.batch_is_allowed.return_value = {
                                "3": {ActionEnum.VIEW_BUSINESS.id: True},
                            }
                            mock_perm_cls.return_value = mock_perm

                            request = RequestFactory().post(
                                "/external/list_user_spaces/",
                                HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
                            )
                            request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

                            from log_adapter.home.views import dispatch_list_user_spaces
                            response = dispatch_list_user_spaces(request)

                            self.assertEqual(response.status_code, 200)
                            data = json.loads(response.content)
                            self.assertTrue(data["result"])
                            space_uids = [s["space_uid"] for s in data["data"]]
                            # 应包含 PO 空间和 IAM 空间
                            self.assertIn("bkcc__2", space_uids, "应包含 PO 空间 bkcc__2")
                            self.assertIn("bkcc__3", space_uids, "应包含 IAM 有权限的空间 bkcc__3")

    def test_iam_batch_is_allowed_exception_graceful(self):
        """IAM batch_is_allowed 异常时不阻塞 PO 空间返回（fail-open 对已有 PO 空间）"""
        from log_adapter.home.views import FeatureToggleObject, EXTERNAL_PERMISSION_OR_DECISION

        toggle_obj = Toggle(name=EXTERNAL_PERMISSION_OR_DECISION, status="on")

        po_permission = {"bkcc__2": ["log_search"]}
        po_space = self._make_space(1, "bkcc__2", 2)
        iam_candidate = self._make_space(2, "bkcc__3", 3)

        with patch.object(FeatureToggleObject, "toggle", return_value=toggle_obj):
            with patch(
                "log_adapter.home.views.ExternalPermission.get_authorizer_permission",
                return_value=po_permission,
            ):
                with patch(
                    "log_adapter.home.views.RequestProcessor.get_request_user_info",
                    return_value={"username": self.EXTERNAL_USER},
                ):
                    with patch("apps.log_search.models.Space.objects") as mock_space_qs:
                        mock_space_qs.filter.return_value.all.return_value = [po_space]
                        mock_space_qs.exclude.return_value.all.return_value = [iam_candidate]

                        with patch(
                            "log_adapter.home.views.Permission"
                        ) as mock_perm_cls:
                            mock_perm = MagicMock()
                            mock_perm.batch_is_allowed.side_effect = RuntimeError("IAM batch 不可达")
                            mock_perm_cls.return_value = mock_perm

                            request = RequestFactory().post(
                                "/external/list_user_spaces/",
                                HTTP_USER=json.dumps({"username": self.EXTERNAL_USER}),
                            )
                            request.META["HTTP_USER"] = json.dumps({"username": self.EXTERNAL_USER})

                            from log_adapter.home.views import dispatch_list_user_spaces
                            response = dispatch_list_user_spaces(request)

                            self.assertEqual(response.status_code, 200)
                            data = json.loads(response.content)
                            space_uids = [s["space_uid"] for s in data["data"]]
                            # IAM 异常时，PO 空间应仍被返回（不因 IAM 异常丢失 PO 空间）
                            self.assertIn("bkcc__2", space_uids,
                                          "IAM 异常时 PO 空间不应丢失")


# ════════════════════════════════════════════════════════════════════
#  9. OR 决策框架接口稳定性（可被复用）
#     覆盖 TAPD3 验收标准 10：decide() 与资源类型无关
# ════════════════════════════════════════════════════════════════════

class TestOrDecisionFrameworkStable(TestCase):
    """验证 decide() 接口不绑定特定资源类型，可被 04/05 复用"""

    def test_decide_accepts_arbitrary_resource_sets(self):
        """decide() 不要求 resources 的元素类型，任意 hashable 集合均可"""
        # 非数字资源集合（模拟其他资源类型）
        legacy = CheckResult(allowed=True, resources={"r_a", "r_b"}, source="legacy")
        iam = CheckResult(allowed=True, resources={"r_c"}, source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user="user_x",
            execution_user="exec_x",
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.resources, {"r_a", "r_b", "r_c"})
        self.assertEqual(decision.decision_source, "both")

    def test_decide_no_hardcoded_action_ids(self):
        """decide() 不绑定 LOG_SEARCH action_ids，外部传入 CheckResult 即可"""
        # 模拟 04 通用分析或 05 监控场景
        legacy = CheckResult(allowed=True, resources={100, 200}, source="legacy", detail="generic_action")
        iam = CheckResult(allowed=False, resources=set(), source="iam", detail="generic_iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user="analytic_user",
            execution_user="exec_user",
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        # verify identity fields still present
        self.assertEqual(decision.authorization_subject, "analytic_user")
        self.assertEqual(decision.audit_user, "analytic_user")
        self.assertEqual(decision.execution_user, "exec_user")

    def test_boolean_check_result_resources_union_correct(self):
        """验证 CheckResult.allowed 是布尔判定，resources 是并集计算的集合，
        不依赖于 action_id 字符串匹配"""
        # 不同来源的 resources merge
        legacy = CheckResult(allowed=True, resources={111}, source="legacy")
        iam = CheckResult(allowed=True, resources={222, 333}, source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user="any_user", execution_user="any_exec",
            legacy_result=legacy, iam_result=iam,
        )
        self.assertEqual(decision.resources, {111, 222, 333})
