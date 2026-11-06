from unittest.mock import Mock

from django.test import SimpleTestCase, TestCase
from django.conf import settings

from apps.iam.backends.v3.exceptions import V3GrantError
from apps.iam.backends.v3.writer import V3AuthorizationWriter
from apps.iam.error_summary import sanitize_error_summary
from iam_engine.migration.dual_write import DualWriteGrantOrchestrator


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
        self.v4_writer = Mock()
        self.observer = Mock()
        self.orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer), ("v4", self.v4_writer)),
            tenant_id="tenant-1",
            grant_observer=self.observer,
        )

    def test_both_versions_are_granted_synchronously_without_callbacks(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = self.orchestrator.grant_creator_action(self.application)
        self.assertEqual(result, (True, "success"))
        self.v3_client.grant_resource_creator_actions.assert_called_once_with(self.application)
        self.v4_writer.grant_resource_creator_actions.assert_called_once_with(self.application)
        self.assertEqual(callbacks, [])

    def test_celery_does_not_import_removed_grant_task(self):
        self.assertNotIn("apps.iam.tasks.grant", settings.CELERY_IMPORTS)

    def test_v4_failure_keeps_legacy_result_without_retry(self):
        self.v4_writer.grant_resource_creator_actions.side_effect = RuntimeError("iam v4 timeout")
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.assertEqual(self.orchestrator.grant_creator_action(self.application), (True, "success"))
        self.v4_writer.grant_resource_creator_actions.assert_called_once()
        self.observer.assert_any_call("v4", "collection", "failed")
        self.assertEqual(callbacks, [])

    def test_v3_failure_does_not_block_v4_by_default(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "v3 unavailable")
        self.assertIsNone(self.orchestrator.grant_creator_action(self.application))
        self.v4_writer.grant_resource_creator_actions.assert_called_once_with(self.application)

    def test_v3_strict_failure_keeps_original_exception(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "v3 unavailable")
        with self.assertRaisesMessage(V3GrantError, "v3 unavailable"):
            self.orchestrator.grant_creator_action(self.application, raise_exception=True)
        self.v4_writer.grant_resource_creator_actions.assert_not_called()

    def test_v4_strict_failure_propagates_without_retry(self):
        error = RuntimeError("iam v4 timeout")
        self.v4_writer.grant_resource_creator_actions.side_effect = error
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(RuntimeError) as caught:
                self.orchestrator.grant_creator_action(self.application, raise_exception=True)
        self.assertIs(caught.exception, error)
        self.assertEqual(callbacks, [])
        self.v4_writer.grant_resource_creator_actions.assert_called_once()


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
