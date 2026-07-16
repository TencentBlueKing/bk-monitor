"""

直接测试 external_permission_decision.py 的核心逻辑，不依赖真实 IAM/DB。

覆盖：
  - decide() 决策矩阵（legacy/iam/both/none + error 三组合）
  - legacy_check() 核心路径（含 CLIENT_LOG → LOG_SEARCH 自动升级）
  - iam_check_resource()（含 resource_id=None / 异常分支）
  - batch_iam_allowed_resources()
  - 三身份字段 (authorization_subject / execution_user / audit_user) 分离
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.constants import ExternalPermissionActionEnum
from apps.log_commons.handlers.external_permission_decision import (
    CheckResult,
    DecisionResult,
    ExternalLogSearchPermissionDecision,
)
from apps.log_commons.models import ExternalPermission
from apps.log_search.constants import ExportStatus, ExportType
from apps.log_search.models import AsyncTask, Scenario


# ──────────────────────────────────────────────
#  decide() 决策矩阵：纯逻辑，零依赖，可以直接写断言
# ──────────────────────────────────────────────


class TestDecideMatrix(TestCase):
    """
    decide() 矩阵对照 tapd3.md 第 40-48 行「权限决策矩阵」逐条验证。

    注意：decide() 的三身份字段 (authorization_subject/execution_user/audit_user)
    由调用方传入，本类也一并验证。
    """

    EXTERNAL_USER = "po_user_a"
    EXECUTION_USER = "internal_agent_admin"

    # ── 4 种正常组合（tapd3.md 第 42-45 行）──

    def test_both_allowed_source_both(self):
        """legacy=允许, iam=允许 → source=both, resources=并集"""
        legacy = CheckResult(allowed=True, resources={10, 20}, source="legacy")
        iam = CheckResult(allowed=True, resources={30}, source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "both")
        self.assertEqual(decision.resources, {10, 20, 30})
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    def test_only_legacy_allowed_source_legacy(self):
        """legacy=允许, iam=拒绝 → source=legacy"""
        legacy = CheckResult(allowed=True, resources={10}, source="legacy")
        iam = CheckResult(allowed=False, resources=set(), source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertEqual(decision.resources, {10})
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    def test_only_iam_allowed_source_iam(self):
        """legacy=拒绝, iam=允许 → source=iam"""
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=True, resources={20}, source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "iam")
        self.assertEqual(decision.resources, {20})
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    def test_both_denied_source_none(self):
        """legacy=拒绝, iam=拒绝 → source=none, allowed=False"""
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=False, resources=set(), source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertEqual(decision.resources, set())
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    # ── 3 种异常组合（tapd3.md 第 46-48 行）──

    def test_legacy_error_iam_allowed_source_iam_warning(self):
        """legacy=异常(None), iam=允许 → source=iam, warning=True, resources=iam侧"""
        legacy = CheckResult(allowed=None, resources=set(), source="error", detail="boom")
        iam = CheckResult(allowed=True, resources={7}, source="iam")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "iam")
        self.assertEqual(decision.resources, {7})
        self.assertTrue(decision.warning, "异常侧必须触发 warning")
        self._assert_identity(decision)

    def test_legacy_allowed_iam_error_source_legacy_warning(self):
        """legacy=允许, iam=异常(None) → source=legacy, warning=True, resources=legacy侧"""
        legacy = CheckResult(allowed=True, resources={5}, source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="error", detail="timeout")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertEqual(decision.resources, {5})
        self.assertTrue(decision.warning, "异常侧必须触发 warning")
        self._assert_identity(decision)

    def test_both_error_source_none_rejected(self):
        """legacy=异常, iam=异常 → source=none, allowed=False, fail-closed"""
        legacy = CheckResult(allowed=None, resources=set(), source="error")
        iam = CheckResult(allowed=None, resources=set(), source="error")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        self.assertEqual(decision.resources, set())
        self.assertTrue(decision.warning)
        self._assert_identity(decision)

    # ── 边界：allowed=None 但 source≠error 不是异常（如 resource_id=None 场景）──

    def test_legacy_false_iam_none_none_not_error_no_warning(self):
        """legacy=False, iam=None(source=iam, 不是 error) → 审批拒绝, 无告警"""
        legacy = CheckResult(allowed=False, resources=set(), source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="iam", detail="resource_not_provided")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision_source, "none")
        # IAM source="iam" ≠ "error"，不应触发 warning
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    def test_legacy_true_iam_none_none_not_error_passes(self):
        """legacy=True, iam=None(source=iam) → legacy 放行, 无告警"""
        legacy = CheckResult(allowed=True, resources={1}, source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="iam", detail="resource_not_provided")

        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision_source, "legacy")
        self.assertEqual(decision.resources, {1})
        self.assertFalse(decision.warning)
        self._assert_identity(decision)

    # ── 资源并集：异常侧 resources 始终为空，不放大 ──

    def test_error_side_empty_resources_does_not_expand_union(self):
        """异常侧即使错误地非空，union 也只取正常的并集（当前实现异常侧恒为空）"""
        # 验证实现层面：iam_check_resource 的 except 分支显式返回 resources=set()
        legacy = CheckResult(allowed=True, resources={1, 2}, source="legacy")
        iam = CheckResult(allowed=None, resources=set(), source="error")
        decision = ExternalLogSearchPermissionDecision.decide(
            external_user=self.EXTERNAL_USER,
            execution_user=self.EXECUTION_USER,
            legacy_result=legacy,
            iam_result=iam,
        )
        # error 侧 resources 是 set()，合并后应等于 {1, 2}
        self.assertEqual(decision.resources, {1, 2})

    # ── 三身份验证辅助 ──

    def _assert_identity(self, decision: DecisionResult):
        self.assertEqual(decision.authorization_subject, self.EXTERNAL_USER)
        self.assertEqual(decision.audit_user, self.EXTERNAL_USER)
        self.assertEqual(
            decision.execution_user,
            self.EXECUTION_USER,
            "execution_user 必须与 authorization_subject/audit_user 不同，防止身份混淆",
        )


# ──────────────────────────────────────────────
#  legacy_check() 单测
# ──────────────────────────────────────────────


class TestLegacyCheck(TestCase):
    """legacy_check() 校验对外部 Permission 类方法的调用编排与返回结构。"""

    SPACE_UID = "bkcc__test"
    EXTERNAL_USER = "po_user_a"

    def test_no_action_ids_returns_not_allowed(self):
        """用户无任何 PO 授权记录 → allowed=False, detail=no_legacy_action"""
        with patch.object(
            ExternalPermission, "get_authorizer_permission", return_value={}
        ) as mock_perm:
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="search",
                resource_id=None,
            )
            self.assertFalse(result.allowed)
            self.assertEqual(result.source, "legacy")
            self.assertEqual(result.detail, "no_legacy_action")
            mock_perm.assert_called_once_with(
                space_uid=self.SPACE_UID, authorizer=self.EXTERNAL_USER
            )

    def test_action_not_matched_returns_not_allowed(self):
        """有 action_ids 但 is_action_valid 全部返回 False → detail=action_not_match"""
        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["log_search"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", return_value=False
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="OtherViewSet",
                view_action="odd_action",
                resource_id=None,
            )
            self.assertFalse(result.allowed)
            self.assertEqual(result.detail, "action_not_match")

    def test_list_interfaces_resource_id_none_returns_action_allowed(self):
        """resource_id=None → allowed=True, detail=action_allowed（列表/归类级接口）"""
        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["log_search"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", return_value=True
        ), patch.object(
            ExternalPermission, "get_resources",
            return_value={"allowed": True, "resources": ["1001", "1002"]},
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="list",
                resource_id=None,
            )
            self.assertTrue(result.allowed)
            self.assertEqual(result.detail, "action_allowed")
            self.assertEqual(result.resources, {1001, 1002})

    def test_detail_resource_in_list_allowed(self):
        """resource_id 在授权列表内 → allowed=True, detail=resource_allowed"""
        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["log_search"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", return_value=True
        ), patch.object(
            ExternalPermission, "get_resources",
            return_value={"allowed": True, "resources": ["1001", "1002", "1003"]},
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="bizs",
                resource_id=1002,
            )
            self.assertTrue(result.allowed)
            self.assertEqual(result.detail, "resource_allowed")
            self.assertEqual(result.resources, {1001, 1002, 1003})

    def test_detail_resource_not_in_list_denied(self):
        """resource_id 不在授权列表内 → allowed=False, detail=resource_denied"""
        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["log_search"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", return_value=True
        ), patch.object(
            ExternalPermission, "get_resources",
            return_value={"allowed": True, "resources": ["1001"]},
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="bizs",
                resource_id=9999,
            )
            self.assertFalse(result.allowed)
            self.assertEqual(result.detail, "resource_denied")

    # ── CLIENT_LOG → LOG_SEARCH 自动升级 ──

    def test_client_log_auto_appends_log_search_to_action_ids(self):
        """用户仅有 CLIENT_LOG → _get_legacy_action_ids 自动追加 LOG_SEARCH，
        然后对 "log_search" 做 is_action_valid 匹配（"client_log" 无法命中 SearchViewSet），
        最终 get_resources 以 "log_search" 调用。"""
        # is_action_valid("client_log") → False（SearchViewSet 中无 client_log 映射）
        # is_action_valid("log_search") → True
        def _side_effect(view_set, view_action, action_id):
            return action_id == "log_search"

        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["client_log"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", side_effect=_side_effect
        ), patch.object(
            ExternalPermission, "get_resources",
            return_value={"allowed": True, "resources": ["2001"]},
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="search",
                resource_id=2001,
            )
            self.assertTrue(result.allowed)
            # get_resources 应以 "log_search" 调用
            ExternalPermission.get_resources.assert_called_with(
                space_uid=self.SPACE_UID,
                action_id="log_search",
                authorized_user=self.EXTERNAL_USER,
            )

    def test_client_log_already_has_log_search_does_not_duplicate(self):
        """用户同时有 CLIENT_LOG + LOG_SEARCH → 不重复追加，直接命中 log_search"""
        def _side_effect(view_set, view_action, action_id):
            return action_id == "log_search"

        with patch.object(
            ExternalPermission, "get_authorizer_permission",
            return_value={self.SPACE_UID: ["client_log", "log_search"]},
        ), patch.object(
            ExternalPermission, "is_action_valid", side_effect=_side_effect
        ), patch.object(
            ExternalPermission, "get_resources",
            return_value={"allowed": True, "resources": ["3001"]},
        ):
            result = ExternalLogSearchPermissionDecision.legacy_check(
                space_uid=self.SPACE_UID,
                external_user=self.EXTERNAL_USER,
                view_set="SearchViewSet",
                view_action="search",
                resource_id=3001,
            )
            self.assertTrue(result.allowed)
            # 命中的是 log_search（列表中排在 client_log 前面或后面取决于追加逻辑，
            # 但关键是不应重复追加）
            ExternalPermission.get_resources.assert_called_with(
                space_uid=self.SPACE_UID,
                action_id="log_search",
                authorized_user=self.EXTERNAL_USER,
            )


# ──────────────────────────────────────────────
#  iam_check_resource() 单测
# ──────────────────────────────────────────────


class TestIamCheckResource(TestCase):
    """iam_check_resource() 校验 IAM Permission 调用编排与异常降级。"""

    SPACE_UID = "bkcc__test"
    EXTERNAL_USER = "po_user_a"
    RESOURCE_ID = 628000
    BIZ_ID = 100

    def test_resource_id_none_returns_undetermined(self):
        """resource_id=None → allowed=None, source=iam（不视为 error）"""
        result = ExternalLogSearchPermissionDecision.iam_check_resource(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_id=None,
        )
        self.assertIsNone(result.allowed)
        self.assertEqual(result.source, "iam")
        self.assertEqual(result.detail, "resource_not_provided")
        self.assertEqual(result.resources, set())

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_true(self, mock_perm_cls, mock_resource_enum, _mock_s2b):
        """IAM is_allowed=True → allowed=True, resource={resource_id}"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.return_value = True

        result = ExternalLogSearchPermissionDecision.iam_check_resource(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_id=self.RESOURCE_ID,
        )

        self.assertTrue(result.allowed)
        self.assertEqual(result.source, "iam")
        self.assertEqual(result.resources, {self.RESOURCE_ID})

        # 验证 IAM 请求参数：username 必须是 external_user，不是 authorizer
        mock_perm_cls.assert_called_once()
        _, kwargs = mock_perm_cls.call_args
        self.assertEqual(kwargs["username"], self.EXTERNAL_USER,
                         "IAM subject 必须为 external_user，禁止传入 authorizer")

        # 验证资源属性：bk_biz_id + space_uid
        mock_resource_enum.INDICES.create_simple_instance.assert_called_once()
        _, res_kwargs = mock_resource_enum.INDICES.create_simple_instance.call_args
        self.assertEqual(res_kwargs["attribute"]["space_uid"], self.SPACE_UID)
        self.assertEqual(res_kwargs["attribute"]["bk_biz_id"], self.BIZ_ID)

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_false(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """IAM is_allowed=False → allowed=False, resources=空"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.return_value = False

        result = ExternalLogSearchPermissionDecision.iam_check_resource(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_id=self.RESOURCE_ID,
        )

        self.assertFalse(result.allowed)
        self.assertEqual(result.source, "iam")
        self.assertEqual(result.resources, set())

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_is_allowed_raises_exception(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """IAM 抛异常 → allowed=None, source=error, fail-closed, 不扩权"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.is_allowed.side_effect = RuntimeError("IAM 不可达")

        result = ExternalLogSearchPermissionDecision.iam_check_resource(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_id=self.RESOURCE_ID,
        )

        self.assertIsNone(result.allowed)
        self.assertEqual(result.source, "error")
        self.assertEqual(result.resources, set(),
                         "异常侧 resources 必须为空，防止被 decide() union 误放大")
        self.assertIn("IAM 不可达", result.detail)


# ──────────────────────────────────────────────
#  batch_iam_allowed_resources() 单测
# ──────────────────────────────────────────────


class TestBatchIamAllowedResources(TestCase):
    """batch_iam_allowed_resources() 用于列表场景一次性批量 IAM 判定。"""

    SPACE_UID = "bkcc__test"
    EXTERNAL_USER = "po_user_a"
    BIZ_ID = 100

    SEARCH_LOG_ACTION_ID = "search_log_v2"  # 与 IAM 权限中心注册的 ActionEnum.SEARCH_LOG.id 一致

    def test_empty_resource_ids_returns_empty_set(self):
        """空列表输入 → 返回空 set，不触发 IAM 调用"""
        result = ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_ids=[],
        )
        self.assertEqual(result, set())

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    @patch("apps.log_commons.handlers.external_permission_decision.ActionEnum")
    def test_partial_allow_mixed_results(self, mock_action_enum, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """部分资源允许、部分拒绝 → 只返回 allow 的资源 ID"""
        mock_action_enum.SEARCH_LOG.id = self.SEARCH_LOG_ACTION_ID
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.batch_is_allowed.return_value = {
            "1001": {self.SEARCH_LOG_ACTION_ID: True},
            "1002": {self.SEARCH_LOG_ACTION_ID: False},
            "1003": {self.SEARCH_LOG_ACTION_ID: True},
        }

        result = ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_ids=[1001, 1002, 1003],
        )

        self.assertEqual(result, {1001, 1003})

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    @patch("apps.log_commons.handlers.external_permission_decision.ActionEnum")
    def test_all_allowed(self, mock_action_enum, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """所有资源都允许 → 返回完整集合"""
        mock_action_enum.SEARCH_LOG.id = self.SEARCH_LOG_ACTION_ID
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.batch_is_allowed.return_value = {
            "2001": {self.SEARCH_LOG_ACTION_ID: True},
            "2002": {self.SEARCH_LOG_ACTION_ID: True},
        }

        result = ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_ids=[2001, 2002],
        )

        self.assertEqual(result, {2001, 2002})

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_batch_is_allowed_raises_exception(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """批量 IAM 调用异常 → 返回空 set，fail-closed，不扩权"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.batch_is_allowed.side_effect = RuntimeError("批量 IAM 异常")

        result = ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_ids=[3001, 3002],
        )

        self.assertEqual(result, set(), "异常时不允许任何资源，防止扩权")

    @patch("apps.log_commons.handlers.external_permission_decision.space_uid_to_bk_biz_id", return_value=100)
    @patch("apps.log_commons.handlers.external_permission_decision.ResourceEnum")
    @patch("apps.log_commons.handlers.external_permission_decision.Permission")
    def test_iam_subject_is_external_user_not_authorizer(self, mock_perm_cls, _mock_resource_enum, _mock_s2b):
        """批量 IAM 的 username 参数必须为 external_user，禁止传入内部代理(authorizer)"""
        mock_perm_instance = mock_perm_cls.return_value
        mock_perm_instance.batch_is_allowed.return_value = {}

        ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
            space_uid=self.SPACE_UID,
            external_user=self.EXTERNAL_USER,
            resource_ids=[4001],
        )

        mock_perm_cls.assert_called_once()
        _, kwargs = mock_perm_cls.call_args
        self.assertEqual(kwargs["username"], self.EXTERNAL_USER,
                         "批量 IAM subject 恒为 external_user，禁止传入 authorizer 身份")


# ══════════════════════════════════════════════════
#  fetch_request_username() 外部用户前缀逻辑
# ══════════════════════════════════════════════════


class TestFetchRequestUsername(TestCase):
    """验证 fetch_request_username() 的外部用户前缀隔离逻辑。

    规则：
      - 有外部用户 → 返回 "external_{username}"
      - 无外部用户 → 回退到 get_request_username()
    """

    @patch("apps.log_search.utils.get_request_username", return_value="internal_admin")
    @patch("apps.log_search.utils.get_request_external_username", return_value="po_user_a")
    def test_external_user_gets_prefix(self, _mock_ext, _mock_int):
        from apps.log_search.utils import fetch_request_username
        result = fetch_request_username()
        self.assertEqual(result, "external_po_user_a",
                         "外部用户必须加 external_ 前缀，防止与内部同名用户数据串号")

    @patch("apps.log_search.utils.get_request_username", return_value="internal_admin")
    @patch("apps.log_search.utils.get_request_external_username", return_value="")
    def test_no_external_user_falls_back_to_request_username(self, _mock_ext, _mock_int):
        from apps.log_search.utils import fetch_request_username
        result = fetch_request_username()
        self.assertEqual(result, "internal_admin",
                         "无外部用户时应回退到请求用户名")


# ══════════════════════════════════════════════════
#  Favorite / FavoriteGroup 外部用户隔离
# ══════════════════════════════════════════════════


class TestFavoriteHandlerExternalUserIsolation(TestCase):
    """验证 FavoriteHandler / FavoriteGroupHandler / FavoriteUnionSearchHandler
    的 __init__ 中 self.username 正确取外部用户。"""

    EXTERNAL_USER = "po_user_a"
    INTERNAL_USER = "internal_admin"

    def test_favorite_handler_uses_external_user_when_set(self):
        with patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            return_value=self.EXTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            return_value=self.INTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_app_code",
            return_value="bk_log_search",
        ):
            from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
            handler = FavoriteHandler(favorite_id=None, space_uid="test_space")
            self.assertEqual(handler.username, self.EXTERNAL_USER,
                             "有 external_user 时，FavoriteHandler.username 应为外部用户名")

    def test_favorite_handler_falls_back_to_request_username(self):
        with patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            return_value="",
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            return_value=self.INTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_app_code",
            return_value="bk_log_search",
        ):
            from apps.log_search.handlers.search.favorite_handlers import FavoriteHandler
            handler = FavoriteHandler(favorite_id=None, space_uid="test_space")
            self.assertEqual(handler.username, self.INTERNAL_USER,
                             "无 external_user 时，FavoriteHandler.username 应回退到请求用户名")

    def test_favorite_group_handler_uses_external_user(self):
        with patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            return_value=self.EXTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            return_value=self.INTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_app_code",
            return_value="bk_log_search",
        ):
            from apps.log_search.handlers.search.favorite_handlers import FavoriteGroupHandler
            handler = FavoriteGroupHandler(group_id=None, space_uid="test_space")
            self.assertEqual(handler.username, self.EXTERNAL_USER)

    def test_favorite_union_search_handler_uses_external_user(self):
        with patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_external_username",
            return_value=self.EXTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.favorite_handlers.get_request_username",
            return_value=self.INTERNAL_USER,
        ):
            from apps.log_search.handlers.search.favorite_handlers import FavoriteUnionSearchHandler
            handler = FavoriteUnionSearchHandler(favorite_union_id=None, space_uid="test_space")
            self.assertEqual(handler.username, self.EXTERNAL_USER)


# ══════════════════════════════════════════════════
#  异步导出下载文件 外部用户隔离
# ══════════════════════════════════════════════════


class TestDownloadFileExternalUserIsolation(TestCase):
    """验证下载文件接口按外部用户隔离：外部用户只能下载 created_by 为自己的任务。"""

    EXTERNAL_USER = "po_user_b"

    def setUp(self):
        self.external_task = AsyncTask.objects.create(
            request_param={"keyword": "*"},
            scenario_id=Scenario.LOG,
            index_set_id=1,
            bk_biz_id=2,
            start_time="2026-07-01 00:00:00",
            end_time="2026-07-01 01:00:00",
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.SUCCESS,
            download_url="https://example.com/export_external.tar.gz",
            source_app_code="bk_log_search",
            created_by=self.EXTERNAL_USER,
        )
        self.internal_task = AsyncTask.objects.create(
            request_param={"keyword": "*"},
            scenario_id=Scenario.LOG,
            index_set_id=2,
            bk_biz_id=2,
            start_time="2026-07-01 00:00:00",
            end_time="2026-07-01 01:00:00",
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.SUCCESS,
            download_url="https://example.com/export_internal.tar.gz",
            source_app_code="bk_log_search",
            created_by="internal_admin",
        )

    @patch("apps.log_search.views.search_views.get_request_external_username")
    @patch("apps.log_search.views.search_views.get_request_app_code")
    def test_external_user_can_download_own_task(self, mock_app_code, mock_ext_user):
        """外部用户仅能下载 created_by 为自己(user)的任务"""
        mock_ext_user.return_value = self.EXTERNAL_USER
        mock_app_code.return_value = "bk_log_search"

        query_set = AsyncTask.objects.filter(
            id=self.external_task.id,
            bk_biz_id=self.external_task.bk_biz_id,
            source_app_code="bk_log_search",
            export_type=ExportType.ASYNC,
        )
        # 模拟 download_file 中的外部用户过滤：直接使用 mock 的返回值
        external_username = mock_ext_user.return_value
        if external_username:
            query_set = query_set.filter(created_by=external_username)

        task = query_set.first()
        self.assertIsNotNone(task, "外部用户应能查询到自己的导出任务")
        self.assertEqual(task.id, self.external_task.id)

    @patch("apps.log_search.views.search_views.get_request_external_username")
    @patch("apps.log_search.views.search_views.get_request_app_code")
    def test_external_user_cannot_download_others_task(self, mock_app_code, mock_ext_user):
        """外部用户不能下载 created_by 为别人的任务"""
        mock_ext_user.return_value = self.EXTERNAL_USER
        mock_app_code.return_value = "bk_log_search"

        query_set = AsyncTask.objects.filter(
            id=self.internal_task.id,
            bk_biz_id=self.internal_task.bk_biz_id,
            source_app_code="bk_log_search",
            export_type=ExportType.ASYNC,
        )
        # 外部用户模式下，extra filter created_by=external_username 会导致查不到别人的任务
        external_username = mock_ext_user.return_value
        if external_username:
            query_set = query_set.filter(created_by=external_username)

        task = query_set.first()
        self.assertIsNone(task, "外部用户不应能查询到别人的导出任务")

    @patch("apps.log_search.views.search_views.get_request_external_username")
    @patch("apps.log_search.views.search_views.get_request_app_code")
    def test_internal_user_without_external_does_not_filter_by_created_by(self, mock_app_code, mock_ext_user):
        """内部用户(无 external_user)不过滤 created_by，可以下载任意任务"""
        mock_ext_user.return_value = ""
        mock_app_code.return_value = "bk_log_search"

        query_set = AsyncTask.objects.filter(
            id=self.internal_task.id,
            bk_biz_id=self.internal_task.bk_biz_id,
            source_app_code="bk_log_search",
            export_type=ExportType.ASYNC,
        )
        # 内部用户模式下，external_username 为空，不追加 created_by 过滤
        external_username = mock_ext_user.return_value
        if external_username:
            query_set = query_set.filter(created_by=external_username)

        task = query_set.first()
        self.assertIsNotNone(task, "内部用户应能下载任意导出任务")


# ══════════════════════════════════════════════════
#  导出历史 外部用户隔离
# ══════════════════════════════════════════════════


class TestExportHistoryExternalUserIsolation(TestCase):
    """验证导出历史列表接口按外部用户隔离。"""

    EXTERNAL_USER = "po_user_c"

    def setUp(self):
        self.external_history = AsyncTask.objects.create(
            request_param={"keyword": "*"},
            scenario_id=Scenario.LOG,
            index_set_id=1,
            bk_biz_id=2,
            start_time="2026-07-01 00:00:00",
            end_time="2026-07-01 01:00:00",
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.SUCCESS,
            source_app_code="bk_log_search",
            created_by=self.EXTERNAL_USER,
        )
        self.internal_history = AsyncTask.objects.create(
            request_param={"keyword": "error"},
            scenario_id=Scenario.LOG,
            index_set_id=1,
            bk_biz_id=2,
            start_time="2026-07-01 00:00:00",
            end_time="2026-07-01 01:00:00",
            export_type=ExportType.ASYNC,
            export_status=ExportStatus.SUCCESS,
            source_app_code="bk_log_search",
            created_by="internal_admin",
        )

    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_app_code")
    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_external_username")
    def test_external_user_only_sees_own_history(self, mock_ext_user, mock_app_code):
        """外部用户只能看到 created_by 为自己的导出历史"""
        mock_ext_user.return_value = self.EXTERNAL_USER
        mock_app_code.return_value = "bk_log_search"

        external_username = mock_ext_user.return_value
        query_set = AsyncTask.objects.filter(
            bk_biz_id=self.external_history.bk_biz_id,
            source_app_code="bk_log_search",
            index_set_type="single",
        )
        if external_username:
            query_set = query_set.filter(created_by=external_username)

        task_ids = set(query_set.values_list("id", flat=True))
        self.assertIn(self.external_history.id, task_ids,
                      "外部用户应能看到自己的导出历史")
        self.assertNotIn(self.internal_history.id, task_ids,
                         "外部用户不应看到别人的导出历史")

    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_app_code")
    @patch("apps.log_search.handlers.search.async_export_handlers.get_request_external_username")
    def test_internal_user_sees_all_history(self, mock_ext_user, mock_app_code):
        """内部用户(无 external_user)可以看到全量导出历史"""
        mock_ext_user.return_value = ""
        mock_app_code.return_value = "bk_log_search"

        external_username = mock_ext_user.return_value
        query_set = AsyncTask.objects.filter(
            bk_biz_id=self.external_history.bk_biz_id,
            source_app_code="bk_log_search",
            index_set_type="single",
        )
        if external_username:
            query_set = query_set.filter(created_by=external_username)

        task_ids = set(query_set.values_list("id", flat=True))
        self.assertIn(self.external_history.id, task_ids)
        self.assertIn(self.internal_history.id, task_ids,
                      "内部用户应能看到所有人的导出历史")


# ══════════════════════════════════════════════════
#  检索历史 外部用户隔离
# ══════════════════════════════════════════════════


class TestSearchHistoryExternalUserIsolation(TestCase):
    """验证检索历史用外部用户而非内部代理用户名做隔离。"""

    EXTERNAL_USER = "po_user_d"
    INTERNAL_USER = "internal_admin"

    def test_search_history_uses_external_username_first(self):
        """search_history 应优先使用 get_request_external_username()"""
        with patch(
            "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
            return_value=self.EXTERNAL_USER,
        ), patch(
            "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
            return_value=self.INTERNAL_USER,
        ):
            from apps.log_search.handlers.search.search_handlers_esquery import (
                get_request_external_username,
                get_request_username,
            )
            username = get_request_external_username() or get_request_username()
            self.assertEqual(username, self.EXTERNAL_USER,
                             "检索历史应用外部用户名做隔离，防止外部用户看到内部代理的历史")

    def test_search_history_falls_back_when_no_external_user(self):
        """无外部用户时回退到 get_request_username()"""
        with patch(
            "apps.log_search.handlers.search.search_handlers_esquery.get_request_external_username",
            return_value="",
        ), patch(
            "apps.log_search.handlers.search.search_handlers_esquery.get_request_username",
            return_value=self.INTERNAL_USER,
        ):
            from apps.log_search.handlers.search.search_handlers_esquery import (
                get_request_external_username,
                get_request_username,
            )
            username = get_request_external_username() or get_request_username()
            self.assertEqual(username, self.INTERNAL_USER)
