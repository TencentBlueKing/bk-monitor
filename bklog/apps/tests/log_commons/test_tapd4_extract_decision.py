"""
TAPD4 决策组件单测：覆盖 ExternalLogExtractPermissionDecision 的完整决策矩阵。

对照 TAPD4 验收标准：
  A. 没有有效旧权限但存在本人策略时可以使用日志提取  → TestExtractDecisionMatrix
  B. 没有策略的外部用户无法浏览或创建提取任务         → TestExtractDecisionMatrix
  F. 旧 log_extract 有效期内继续兼容                   → TestExtractLegacyCheck

对照自测：
  S1. 用户 X 不能访问用户 Y 的策略目录                → TestExtractStrategyCheck
  S2. 覆盖旧权限有效、旧权限过期、仅策略授权和无策略   → TestExtractDecisionMatrix
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.handlers.external_permission_decision import (
    CheckResult,
    DecisionResult,
    ExternalLogExtractPermissionDecision,
)


# ──────────────────────────────────────────────
#  决策矩阵：legacy/strategy/both/none 4 种正常组合 + 3 种异常组合
# ──────────────────────────────────────────────

class TestExtractDecisionMatrix(TestCase):
    """legacy(PO) OR strategy 决策矩阵，对照 tapd4.md 验收标准 A/B/F。"""

    EXTERNAL_USER = "po_user_a"
    EXECUTION_USER = "internal_admin"

    def test_both_allowed_source_both(self):
        """legacy=允许, strategy=允许 → source=both, allowed=True（验收 F + A）"""
        legacy = CheckResult(allowed=True, source="legacy")
        strategy = CheckResult(allowed=True, source="strategy")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "both")
        self.assertFalse(decision.warning)
        self.assertEqual(decision.authorization_subject, self.EXTERNAL_USER)
        self.assertEqual(decision.execution_user, self.EXECUTION_USER)
        self.assertEqual(decision.audit_user, self.EXTERNAL_USER)

    def test_only_legacy_allowed_source_legacy(self):
        """legacy=允许, strategy=拒绝 → source=legacy, allowed=True（验收 F：旧 log_extract 有效）"""
        legacy = CheckResult(allowed=True, source="legacy")
        strategy = CheckResult(allowed=False, source="strategy")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertFalse(decision.warning)

    def test_only_strategy_allowed_source_strategy(self):
        """legacy=拒绝, strategy=允许 → source=strategy, allowed=True（验收 A：仅策略授权可用）"""
        legacy = CheckResult(allowed=False, source="legacy")
        strategy = CheckResult(allowed=True, source="strategy")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "strategy")
        self.assertFalse(decision.warning)

    def test_both_denied_source_none(self):
        """legacy=拒绝, strategy=拒绝 → source=none, allowed=False（验收 B：无策略外部用户被拒）"""
        legacy = CheckResult(allowed=False, source="legacy", detail="legacy_expired_or_missing")
        strategy = CheckResult(allowed=False, source="strategy", detail="no_strategy")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertFalse(decision.warning)
        self.assertEqual(decision.reason, "legacy_and_strategy_denied_or_unavailable")

    # ── 3 种异常组合 ──

    def test_legacy_error_strategy_allowed_allowed_true(self):
        """legacy=异常(error), strategy=允许 → allowed=True, source=strategy, warning=True"""
        legacy = CheckResult(allowed=True, source="error", detail="db error")
        strategy = CheckResult(allowed=True, source="strategy", detail="strategy_found")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "strategy")
        self.assertTrue(decision.warning)

    def test_legacy_allowed_strategy_error_allowed_true(self):
        """legacy=允许, strategy=异常(error) → allowed=True, source=legacy, warning=True"""
        legacy = CheckResult(allowed=True, source="legacy", detail="legacy_valid")
        strategy = CheckResult(allowed=True, source="error", detail="db error")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertTrue(decision.warning)

    def test_both_error_allowed_false(self):
        """legacy=异常(error), strategy=异常(error) → allowed=False, source=none, warning=True"""
        legacy = CheckResult(allowed=True, source="error", detail="db error")
        strategy = CheckResult(allowed=True, source="error", detail="db error")

        decision = ExternalLogExtractPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            strategy_result=strategy,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertTrue(decision.warning)


# ──────────────────────────────────────────────
#  legacy_check()：有效/过期/无记录
# ──────────────────────────────────────────────

class TestExtractLegacyCheck(TestCase):
    """验收标准 F：旧 log_extract 有效期内继续兼容"""

    SPACE_UID = "bkcc__2"
    EXTERNAL_USER = "po_user_legacy"

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.objects.filter")
    def test_legacy_valid_returns_allowed(self, mock_filter):
        """expire_time > now → allowed=True, source=legacy, detail=legacy_valid"""
        mock_qs = mock_filter.return_value
        mock_qs.exists.return_value = True

        result = ExternalLogExtractPermissionDecision.legacy_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.source, "legacy")
        self.assertEqual(result.detail, "legacy_valid")
        mock_filter.assert_called_once_with(
            authorized_user=self.EXTERNAL_USER,
            space_uid=self.SPACE_UID,
            action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value,
            expire_time__gt=mock_filter.call_args[1]["expire_time__gt"],
        )

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.objects.filter")
    def test_legacy_expired_returns_denied(self, mock_filter):
        """expire_time <= now 或无记录 → allowed=False, detail=legacy_expired_or_missing"""
        mock_qs = mock_filter.return_value
        mock_qs.exists.return_value = False

        result = ExternalLogExtractPermissionDecision.legacy_check(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.source, "legacy")
        self.assertEqual(result.detail, "legacy_expired_or_missing")

    @patch("apps.log_commons.handlers.external_permission_decision.ExternalPermission.objects.filter")
    def test_legacy_no_record_returns_denied(self, mock_filter):
        """ExternalPermission 表中没有该用户记录 → allowed=False"""
        mock_filter.return_value.exists.return_value = False

        result = ExternalLogExtractPermissionDecision.legacy_check(
            space_uid="bkcc__999",
            external_user="nonexistent_user",
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.detail, "legacy_expired_or_missing")


# ──────────────────────────────────────────────
#  strategy_check()：有策略/无策略/user_list 锚定
# ──────────────────────────────────────────────

class TestExtractStrategyCheck(TestCase):
    """验收标准 A/B 策略校验 + 自测 S1：用户 X 不能匹配用户 Y 的策略

    注意：strategy_check 内部使用惰性导入 `from apps.log_extract.models import Strategies`，
    因此 mock 路径必须指向 `apps.log_extract.models.Strategies` 而非 `external_permission_decision`。
    """

    BK_BIZ_ID = 2
    EXTERNAL_USER = "po_user_strategy"

    @patch("apps.log_extract.models.Strategies.objects.filter")
    def test_strategy_found_returns_allowed(self, mock_filter):
        """user_list 包含 external_user → allowed=True, source=strategy"""
        mock_qs = mock_filter.return_value
        mock_qs.exclude.return_value.exists.return_value = True

        result = ExternalLogExtractPermissionDecision.strategy_check(
            bk_biz_id=self.BK_BIZ_ID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.source, "strategy")
        self.assertEqual(result.detail, "strategy_found")
        mock_filter.assert_called_once_with(
            bk_biz_id=self.BK_BIZ_ID,
            user_list__contains=f",{self.EXTERNAL_USER},",
        )

    @patch("apps.log_extract.models.Strategies.objects.filter")
    def test_no_strategy_returns_denied(self, mock_filter):
        """user_list 不包含 external_user → allowed=False"""
        mock_qs = mock_filter.return_value
        mock_qs.exclude.return_value.exists.return_value = False

        result = ExternalLogExtractPermissionDecision.strategy_check(
            bk_biz_id=self.BK_BIZ_ID,
            external_user=self.EXTERNAL_USER,
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.source, "strategy")
        self.assertEqual(result.detail, "no_strategy")

    @patch("apps.log_extract.models.Strategies.objects.filter")
    def test_user_list_anchored_no_false_match(self, mock_filter):
        """user_list 锚定匹配：'alice' 不会匹配到 'alice_2'。

        user_list 存储格式 ',user1,user2,'，使用 ',{user},' 做 contains 天然防误匹配。
        """
        mock_qs = mock_filter.return_value
        mock_qs.exclude.return_value.exists.return_value = True

        result = ExternalLogExtractPermissionDecision.strategy_check(
            bk_biz_id=self.BK_BIZ_ID,
            external_user="alice",
        )

        mock_filter.assert_called_once_with(
            bk_biz_id=self.BK_BIZ_ID,
            user_list__contains=",alice,",
        )
        # 这个查询不会匹配到 user_list = ",alice_2," 的记录（逗号锚定）
        # 验证 query 构建正确即可，具体匹配逻辑由数据库执行
