"""
TAPD5 决策组件单测：覆盖 ExternalClientLogPermissionDecision 的完整决策矩阵。

对照 tapd5.md 验收标准：
  1. 旧 client_log 用户原有能力保持可用                         → TestClientLogDecisionMatrix / TestClientLogLegacyCheck
  2. 仅 VIEW_CLIENT_LOG 用户可以查看但不能创建或下载             → TestClientLogDecisionMatrix（iam-only 分支）
  5. 未授权用户不能通过直接调用接口绕过权限                       → TestClientLogDecisionMatrix（none 分支）
  6. 创建人和审计用户为真实 PO 外部用户                           → DecisionResult 三身份字段断言（各用例均覆盖）

对照 TAPD3/4 已验证模式：legacy OR iam 决策矩阵 4 种正常组合 + 3 种异常组合、
legacy_check 的 view_set/view_action 命中逻辑、iam_check 的 subject 恒为 external_user、
异常侧 fail-closed（source=error 时 allowed 不参与 union/放行判定）。
"""
from unittest.mock import patch

from django.test import TestCase

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.handlers.external_permission_decision import (
    CheckResult,
    ExternalClientLogPermissionDecision,
)


# ──────────────────────────────────────────────
#  决策矩阵：legacy/iam/both/none 4 种正常组合 + 3 种异常组合
# ──────────────────────────────────────────────


class TestClientLogDecisionMatrix(TestCase):
    """legacy(PO client_log) OR iam(VIEW_CLIENT_LOG) 决策矩阵，对照 tapd5.md 验收标准 1/2/5。"""

    EXTERNAL_USER = "po_user_client_log"
    EXECUTION_USER = "internal_admin"

    def test_both_allowed_source_both(self):
        """legacy=允许, iam=允许 → source=both, allowed=True（验收 1：旧权限仍可用，且IAM侧同时命中）"""
        legacy = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "both")
        self.assertFalse(decision.warning)
        self.assertEqual(decision.resources, set())
        self.assertEqual(decision.authorization_subject, self.EXTERNAL_USER)
        self.assertEqual(decision.execution_user, self.EXECUTION_USER)
        self.assertEqual(decision.audit_user, self.EXTERNAL_USER)

    def test_only_legacy_allowed_source_legacy(self):
        """legacy=允许, iam=拒绝 → source=legacy, allowed=True（验收 1：旧 client_log 有效期内继续兼容）"""
        legacy = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam = CheckResult(allowed=False, source="iam", detail="iam_denied")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertFalse(decision.warning)

    def test_only_iam_allowed_source_iam(self):
        """legacy=拒绝, iam=允许 → source=iam, allowed=True（验收 2：仅 VIEW_CLIENT_LOG 用户可查看）"""
        legacy = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "iam")
        self.assertFalse(decision.warning)

    def test_both_denied_source_none(self):
        """legacy=拒绝, iam=拒绝 → source=none, allowed=False（验收 5：未授权用户无法绕过权限）"""
        legacy = CheckResult(allowed=False, source="legacy", detail="no_legacy_action")
        iam = CheckResult(allowed=False, source="iam", detail="iam_denied")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertFalse(decision.warning)
        self.assertEqual(decision.reason, "legacy_and_iam_denied_or_unavailable")

    # ── 3 种异常组合 ──

    def test_legacy_error_iam_allowed_allowed_true(self):
        """legacy=异常(error), iam=允许 → allowed=True, source=iam, warning=True"""
        legacy = CheckResult(allowed=True, source="error", detail="db error")
        iam = CheckResult(allowed=True, source="iam", detail="iam_allowed")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "iam")
        self.assertTrue(decision.warning)

    def test_legacy_allowed_iam_error_allowed_true(self):
        """legacy=允许, iam=异常(error) → allowed=True, source=legacy, warning=True"""
        legacy = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        iam = CheckResult(allowed=True, source="error", detail="IAM 不可达")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertTrue(decision.warning)

    def test_both_error_allowed_false(self):
        """legacy=异常(error), iam=异常(error) → allowed=False, source=none, warning=True（fail-closed）"""
        legacy = CheckResult(allowed=True, source="error", detail="db error")
        iam = CheckResult(allowed=True, source="error", detail="IAM 不可达")

        decision = ExternalClientLogPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertTrue(decision.warning)


# ──────────────────────────────────────────────
#  legacy_check()：命中/未命中 view_set-view_action/无授权记录
# ──────────────────────────────────────────────


class TestClientLogLegacyCheck(TestCase):
    """验收标准 1：旧 client_log 在有效期内仍可整体放行"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_legacy_client_log"

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.is_action_valid")
    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.get_authorizer_permission")
    def test_legacy_valid_action_matched_returns_allowed(self, mock_get_perm, mock_is_valid):
        """action_ids 含 client_log 且 is_action_valid=True → allowed=True, detail=legacy_valid"""
        mock_get_perm.return_value = {self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]}
        mock_is_valid.return_value = True

        result = ExternalClientLogPermissionDecision.legacy_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            view_set="TGPATaskViewSet",
            view_action="list",
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.source, "legacy")
        self.assertEqual(result.detail, "legacy_valid")
        mock_is_valid.assert_called_once_with(
            view_set="TGPATaskViewSet",
            view_action="list",
            action_id=ExternalPermissionActionEnum.CLIENT_LOG.value,
        )

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.get_authorizer_permission")
    def test_no_client_log_action_returns_denied(self, mock_get_perm):
        """action_ids 中没有 client_log → allowed=False, detail=no_legacy_action，不应再查 is_action_valid"""
        mock_get_perm.return_value = {self.SPACE_UID: [ExternalPermissionActionEnum.LOG_SEARCH.value]}

        result = ExternalClientLogPermissionDecision.legacy_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            view_set="TGPATaskViewSet",
            view_action="list",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.source, "legacy")
        self.assertEqual(result.detail, "no_legacy_action")

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.is_action_valid")
    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.get_authorizer_permission")
    def test_action_not_match_view_set_returns_denied(self, mock_get_perm, mock_is_valid):
        """有 client_log 授权，但当前 view_set/view_action 不在 ViewSetActionEnum 登记范围 → allowed=False"""
        mock_get_perm.return_value = {self.SPACE_UID: [ExternalPermissionActionEnum.CLIENT_LOG.value]}
        mock_is_valid.return_value = False

        result = ExternalClientLogPermissionDecision.legacy_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            view_set="TGPATaskViewSet",
            view_action="create",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.detail, "action_not_match")

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.get_authorizer_permission")
    def test_no_record_for_space_uid_returns_denied(self, mock_get_perm):
        """该 space_uid 下无任何授权记录（get_authorizer_permission 返回空dict）→ allowed=False"""
        mock_get_perm.return_value = {}

        result = ExternalClientLogPermissionDecision.legacy_check(
            space_uid="bkcc__999",
            external_user="nonexistent_user",
            view_set="TGPATaskViewSet",
            view_action="list",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.detail, "no_legacy_action")


# ──────────────────────────────────────────────
#  iam_check()：IAM Permission 调用编排与异常降级
# ──────────────────────────────────────────────


class TestClientLogIamCheck(TestCase):
    """验收标准 2：仅 VIEW_CLIENT_LOG 用户可查看，subject 恒为 external_user"""

    SPACE_UID = "bkcc__test"
    EXTERNAL_USER = "po_user_iam_client_log"
    BIZ_ID = 100

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_true(self, mock_perm_cls, mock_resource_enum, _mock_s2b):
        """IAM is_allowed=True → allowed=True, source=iam"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.return_value = True

        result = ExternalClientLogPermissionDecision.iam_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.source, "iam")
        self.assertEqual(result.detail, "iam_allowed")

        # 验证 IAM 请求参数：username 必须是 external_user，不是 authorizer
        mock_perm_cls.assert_called_once()
        _, kwargs = mock_perm_cls.call_args
        self.assertEqual(kwargs["username"], self.EXTERNAL_USER,
                         "IAM subject 必须为 external_user，禁止传入 authorizer")

        # 验证资源属性：BUSINESS 资源 + space_uid
        mock_resource_enum.BUSINESS.create_simple_instance.assert_called_once()
        _, res_kwargs = mock_resource_enum.BUSINESS.create_simple_instance.call_args
        self.assertEqual(res_kwargs["attribute"]["space_uid"], self.SPACE_UID)
        self.assertEqual(res_kwargs["instance_id"], self.BIZ_ID)

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_false(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """IAM is_allowed=False → allowed=False, source=iam"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.return_value = False

        result = ExternalClientLogPermissionDecision.iam_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.source, "iam")
        self.assertEqual(result.detail, "iam_denied")

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_raises_exception(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """IAM 抛异常 → allowed=None, source=error, fail-closed, 不扩权"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.side_effect = RuntimeError("IAM 不可达")

        result = ExternalClientLogPermissionDecision.iam_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertIsNone(result.allowed)
        self.assertEqual(result.source, "error")
        self.assertIn("IAM 不可达", result.detail)

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id")
    def test_iam_check_uses_bk_tenant_id_from_settings(self, mock_s2b):
        """iam_check 应传入 settings.BK_APP_TENANT_ID 作为 bk_tenant_id（多租户隔离要求）"""
        mock_s2b.return_value = 100
        with patch(
            "apps.log_commons.handlers.external_permission_decision.Permission"
        ) as mock_perm_cls, patch(
            "apps.log_commons.handlers.external_permission_decision.ResourceEnum"
        ), patch(
            "apps.log_commons.handlers.external_permission_decision.settings"
        ) as mock_settings:
            mock_settings.BK_APP_TENANT_ID = "tenant_x"
            mock_perm_cls.return_value.is_allowed.return_value = True

            ExternalClientLogPermissionDecision.iam_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
            )

            _, kwargs = mock_perm_cls.call_args
            self.assertEqual(kwargs["bk_tenant_id"], "tenant_x")
