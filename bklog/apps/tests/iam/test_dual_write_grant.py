from unittest.mock import Mock, patch

from django.db import transaction
from django.test import SimpleTestCase, TestCase

from apps.iam.backends.v3.exceptions import V3GrantError
from apps.iam.backends.v3.writer import V3AuthorizationWriter
from apps.iam.backends.v4.writer import UnsupportedV4GrantResource
from apps.iam.error_summary import sanitize_error_summary
from apps.iam.iam_engine.migration.dual_write import DualWriteGrantOrchestrator
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant


class DualWriteGrantOrchestratorTest(TestCase):
    application = {
        "system": "bk_log_search",
        "type": "collection",
        "id": "28",
        "name": "collection-28",
        "creator": "creator",
    }

    def setUp(self):
        self.v3_client = Mock()
        self.v3_client.grant_resource_creator_actions.return_value = (True, "success")
        self.v3_writer = V3AuthorizationWriter(self.v3_client)
        self.v4_prepared = PreparedAuthorizationGrant(
            payload=[{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
            role_id="space_operator",
            expired_at=1893456000,
        )
        self.v4_writer = Mock()
        self.v4_writer.prepare_resource_creator_actions.return_value = self.v4_prepared
        self.dispatch = Mock()
        self.grant_observer = Mock()
        self.orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer), ("v4", self.v4_writer)),
            tenant_id="tenant-1",
            operator="operator",
            dispatch_v4_grant=self.dispatch,
            grant_observer=self.grant_observer,
        )

    @property
    def expected_task_kwargs(self) -> dict:
        return {
            "tenant_id": "tenant-1",
            "operator": "operator",
            "payload": [{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
            "role_id": "space_operator",
            "expired_at": 1893456000,
            "resource_meta": {
                "subject_id": "creator",
                "resource_system": "bk_log_search",
                "resource_type": "collection",
                "resource_id": "28",
            },
        }

    def test_both_versions_are_granted_synchronously_without_a_retry_task(self):
        with self.captureOnCommitCallbacks(execute=True):
            result = self.orchestrator.grant_creator_action(self.application)

        self.assertEqual(result, (True, "success"))
        self.v3_client.grant_resource_creator_actions.assert_called_once_with(self.application)
        self.v4_writer.prepare_resource_creator_actions.assert_called_once_with(self.application)
        # 首次授权必须同步完成，否则 V4 模式下创建者会有一段时间访问不了自己的新资源。
        self.v4_writer.grant_prepared.assert_called_once_with(self.v4_prepared)
        self.dispatch.assert_not_called()

    def test_both_results_are_available_before_the_outer_transaction_commits(self):
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                result = self.orchestrator.grant_creator_action(self.application)
                # 用户创建资源后必须立刻有权限，两侧授权都不能等到提交后才发生。
                self.v3_client.grant_resource_creator_actions.assert_called_once()
                self.v4_writer.grant_prepared.assert_called_once()

        self.assertEqual(result, (True, "success"))
        self.dispatch.assert_not_called()

    def test_v4_sync_failure_falls_back_to_the_retry_task_after_commit(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")

        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                result = self.orchestrator.grant_creator_action(self.application)
                # 回落任务挂在提交回调上，事务内不得投递。
                self.dispatch.assert_not_called()

        # V4 同步失败不影响 V3 结果，也不上抛，否则回落重试就失去意义。
        self.assertEqual(result, (True, "success"))
        self.dispatch.assert_called_once_with(self.expected_task_kwargs)

    def test_rolled_back_transaction_does_not_dispatch_the_fallback_task(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(RuntimeError, "business failure"):
                with transaction.atomic():
                    self.orchestrator.grant_creator_action(self.application)
                    raise RuntimeError("business failure")

        self.dispatch.assert_not_called()

    def test_v3_failure_is_fail_open_by_default_and_does_not_block_v4_grant(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "v3 unavailable")

        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(self.orchestrator.grant_creator_action(self.application))

        self.v4_writer.grant_prepared.assert_called_once_with(self.v4_prepared)
        self.dispatch.assert_not_called()

    def test_v3_failure_propagates_original_error_in_strict_mode(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "v3 unavailable")

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(V3GrantError, "v3 unavailable"):
                self.orchestrator.grant_creator_action(self.application, raise_exception=True)

        # V3 在 V4 之前执行，严格模式下抛出时 V4 还没登记提交回调。
        self.v4_writer.prepare_resource_creator_actions.assert_not_called()
        self.dispatch.assert_not_called()

    def test_v4_preparation_failure_skips_dispatch_and_keeps_v3_result(self):
        self.v4_writer.prepare_resource_creator_actions.side_effect = UnsupportedV4GrantResource("unsupported")

        with self.captureOnCommitCallbacks(execute=True):
            result = self.orchestrator.grant_creator_action(self.application)

        # 请求构造失败没有可重放的载荷，重试也不会成功，直接按终态处理。
        self.assertEqual(result, (True, "success"))
        self.v4_writer.grant_prepared.assert_not_called()
        self.dispatch.assert_not_called()

    def test_v4_preparation_failure_propagates_in_strict_mode(self):
        self.v4_writer.prepare_resource_creator_actions.side_effect = UnsupportedV4GrantResource("unsupported")

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaisesMessage(UnsupportedV4GrantResource, "unsupported"):
                self.orchestrator.grant_creator_action(self.application, raise_exception=True)

        self.dispatch.assert_not_called()

    def test_dispatch_failure_is_logged_without_breaking_the_caller(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")
        self.dispatch.side_effect = RuntimeError("broker unavailable")

        with patch("apps.iam.iam_engine.migration.dual_write.logger.exception") as exception_log:
            with self.captureOnCommitCallbacks(execute=True):
                result = self.orchestrator.grant_creator_action(self.application)

        # 提交后回调抛错会打断同批次其他回调，投递失败只能靠日志发现。
        self.assertEqual(result, (True, "success"))
        exception_log.assert_called_once()
        self.assertIn("v4 dispatch failed", exception_log.call_args.args[0])

    def test_orchestrator_without_v4_writer_only_grants_v3(self):
        orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer),),
            tenant_id="tenant-1",
            operator="operator",
            dispatch_v4_grant=self.dispatch,
            grant_observer=self.grant_observer,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(orchestrator.grant_creator_action(self.application), (True, "success"))

        self.dispatch.assert_not_called()

    def test_frozen_payload_is_normalized_for_task_serialization(self):
        self.v4_writer.grant_prepared.side_effect = RuntimeError("iam v4 timeout")
        self.v4_writer.prepare_resource_creator_actions.return_value = PreparedAuthorizationGrant(
            payload=[{"resources": ({"type": "collection", "id": 28},), "expired_at": 1893456000}],
            role_id="space_operator",
            expired_at=1893456000,
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.orchestrator.grant_creator_action(self.application)

        self.assertEqual(
            self.dispatch.call_args.args[0]["payload"],
            [{"resources": [{"type": "collection", "id": 28}], "expired_at": 1893456000}],
        )


class ErrorSummaryTest(SimpleTestCase):
    def test_summary_redacts_credentials_and_personal_identifiers(self):
        summary = sanitize_error_summary(
            "marker=<preserved-0> password=plain-secret user@example.com 13800138000 " + "credential-value-" * 40
        )

        self.assertIn("<preserved-0>", summary)
        self.assertNotIn("plain-secret", summary)
        self.assertNotIn("user@example.com", summary)
        self.assertNotIn("13800138000", summary)
        self.assertLessEqual(len(summary), 256)

    def test_summary_collapses_whitespace_and_respects_custom_length(self):
        summary = sanitize_error_summary("IAM V4\n  HTTP 500\tgateway error", max_length=10)

        self.assertEqual(summary, "IAM V4 HTT")
