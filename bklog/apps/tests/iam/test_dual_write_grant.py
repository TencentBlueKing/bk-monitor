from unittest.mock import Mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.iam.backends.legacy_v3 import LegacyV3AuthorizationWriter
from apps.iam.backends.v4.exceptions import V4TimeoutError
from apps.iam.iam_engine.migration.dual_write import (
    DualWriteGrantError,
    DualWriteGrantOrchestrator,
    LeaseOwnershipLostError,
)
from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant
from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository


@override_settings(BK_IAM_GRANT_LEASE_SECONDS=120, BK_IAM_GRANT_MAX_ATTEMPTS=12)
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
        self.v3_writer = LegacyV3AuthorizationWriter(self.v3_client)
        self.v4_writer = Mock()
        self.v4_prepared = PreparedAuthorizationGrant(
            payload=[{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
            role_id="space_operator",
            expired_at=1893456000,
        )
        self.v4_writer.prepare_resource_creator_actions.return_value = self.v4_prepared
        self.orchestrator = DualWriteGrantOrchestrator(
            writers=(("v3", self.v3_writer), ("v4", self.v4_writer)),
            tenant_id="tenant-1",
            operator="operator",
        )

    def test_both_intents_exist_before_first_remote_call(self):
        observed_counts = []

        def observe_intents(_):
            observed_counts.append(IAMAuthorizationGrant.objects.count())
            return (True, "success")

        self.v3_client.grant_resource_creator_actions.side_effect = observe_intents

        result = self.orchestrator.grant_creator_action(self.application)

        self.assertEqual(result, (True, "success"))
        self.assertEqual(observed_counts, [2])
        self.assertEqual(
            set(IAMAuthorizationGrant.objects.values_list("state", flat=True)),
            {IAMAuthorizationGrant.State.SUCCEEDED},
        )

    def test_repeated_grant_does_not_call_succeeded_targets_again(self):
        self.orchestrator.grant_creator_action(self.application)
        self.v3_client.reset_mock()
        self.v4_writer.grant_prepared.reset_mock()

        result = self.orchestrator.grant_creator_action(self.application)

        self.assertEqual(result, (True, "success"))
        self.v3_client.grant_resource_creator_actions.assert_not_called()
        self.v4_writer.grant_prepared.assert_not_called()
        self.assertEqual(IAMAuthorizationGrant.objects.count(), 2)

    def test_timeout_enters_unknown_and_retry_reuses_frozen_payload(self):
        self.v4_writer.grant_prepared.side_effect = V4TimeoutError("timeout")

        self.orchestrator.grant_creator_action(self.application)

        v4_record = IAMAuthorizationGrant.objects.get(target_version="v4")
        self.assertEqual(v4_record.state, IAMAuthorizationGrant.State.UNKNOWN)
        self.assertEqual(v4_record.expired_at, 1893456000)
        self.assertIsNotNone(v4_record.next_retry_at)

        IAMAuthorizationGrant.objects.filter(pk=v4_record.pk).update(next_retry_at=timezone.now())
        self.v3_client.reset_mock()
        self.v4_writer.grant_prepared.reset_mock()
        self.v4_writer.grant_prepared.side_effect = None
        self.v4_writer.prepare_resource_creator_actions.return_value = PreparedAuthorizationGrant(
            payload=[{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1999999999}],
            role_id="space_operator",
            expired_at=1999999999,
        )

        self.orchestrator.grant_creator_action(self.application)

        self.v3_client.grant_resource_creator_actions.assert_not_called()
        self.v4_writer.grant_prepared.assert_called_once_with(self.v4_prepared)
        v4_record.refresh_from_db()
        self.assertEqual(v4_record.state, IAMAuthorizationGrant.State.SUCCEEDED)
        self.assertEqual(v4_record.expired_at, 1893456000)

    def test_cas_claim_allows_only_one_worker(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="a" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
        )
        repository = IAMAuthorizationGrantRepository()

        self.assertIsNotNone(repository.claim(record.pk, lease_owner="worker-1"))
        self.assertIsNone(repository.claim(record.pk, lease_owner="worker-2"))

    def test_claim_finalizes_due_record_already_at_attempt_limit(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="d" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
            state=IAMAuthorizationGrant.State.UNKNOWN,
            attempts=12,
            next_retry_at=timezone.now(),
        )

        self.assertIsNone(IAMAuthorizationGrantRepository().claim(record.pk, lease_owner="worker-1"))

        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.FAILED_FINAL)
        self.assertEqual(record.attempts, 12)

    def test_success_after_lost_lease_is_not_reported_as_persisted_success(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="e" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
            payload={"resource": "28"},
        )
        writer = Mock()

        def lose_lease(_prepared):
            IAMAuthorizationGrant.objects.filter(pk=record.pk).update(lease_owner="replacement-worker")

        writer.grant_prepared.side_effect = lose_lease

        execution = self.orchestrator.execute_record(record, writer)

        self.assertIsInstance(execution.error, LeaseOwnershipLostError)
        self.assertIsNone(execution.result)
        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.PROCESSING)
        self.assertEqual(record.lease_owner, "replacement-worker")

    def test_failure_after_lost_lease_does_not_overwrite_new_owner_state(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="f" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
            payload={"resource": "28"},
        )
        writer = Mock()

        def lose_lease_then_fail(_prepared):
            IAMAuthorizationGrant.objects.filter(pk=record.pk).update(lease_owner="replacement-worker")
            raise V4TimeoutError("timeout")

        writer.grant_prepared.side_effect = lose_lease_then_fail

        execution = self.orchestrator.execute_record(record, writer)

        self.assertIsInstance(execution.error, LeaseOwnershipLostError)
        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.PROCESSING)
        self.assertEqual(record.last_error_message, "")

    def test_expired_lease_cannot_persist_remote_success_before_recovery_scan(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="0" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
            payload={"resource": "28"},
        )
        writer = Mock()

        def expire_lease(_prepared):
            IAMAuthorizationGrant.objects.filter(pk=record.pk).update(lease_until=timezone.now())

        writer.grant_prepared.side_effect = expire_lease

        execution = self.orchestrator.execute_record(record, writer)

        self.assertIsInstance(execution.error, LeaseOwnershipLostError)
        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.PROCESSING)
        self.assertIsNone(record.succeeded_at)

    def test_manual_requeue_becomes_visible_to_compensation_scanner(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="b" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
            state=IAMAuthorizationGrant.State.FAILED_FINAL,
        )

        IAMAuthorizationGrantRepository.requeue_failed([record.pk])

        self.assertEqual(IAMAuthorizationGrantRepository.due_ids(limit=10), [record.pk])

    def test_v3_false_result_enters_retry_wait(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "temporary failure")

        self.assertIsNone(self.orchestrator.grant_creator_action(self.application))

        v3_record = IAMAuthorizationGrant.objects.get(target_version="v3")
        self.assertEqual(v3_record.state, IAMAuthorizationGrant.State.RETRY_WAIT)
        self.assertEqual(
            IAMAuthorizationGrant.objects.get(target_version="v4").state,
            IAMAuthorizationGrant.State.SUCCEEDED,
        )

    def test_double_failure_is_fail_open_by_default_and_strict_when_requested(self):
        self.v3_client.grant_resource_creator_actions.return_value = (False, "v3 unavailable")
        self.v4_writer.grant_prepared.side_effect = V4TimeoutError("v4 timeout")

        self.assertIsNone(self.orchestrator.grant_creator_action(self.application))
        self.assertEqual(
            set(IAMAuthorizationGrant.objects.values_list("state", flat=True)),
            {IAMAuthorizationGrant.State.RETRY_WAIT, IAMAuthorizationGrant.State.UNKNOWN},
        )

        self.v3_client.reset_mock()
        self.v4_writer.grant_prepared.reset_mock()
        with self.assertRaises(DualWriteGrantError):
            self.orchestrator.grant_creator_action(self.application, raise_exception=True)

        self.v3_client.grant_resource_creator_actions.assert_not_called()
        self.v4_writer.grant_prepared.assert_not_called()

    def test_persisted_error_message_is_redacted_and_bounded(self):
        record = IAMAuthorizationGrant.objects.create(
            logical_key="1" * 64,
            target_version="v4",
            tenant_id="tenant-1",
            subject_id="creator",
            operator="operator",
            resource_system="bk_log_search",
            resource_type="collection",
            resource_id="28",
            semantic_role="resource_creator",
        )
        repository = IAMAuthorizationGrantRepository()
        claimed = repository.claim(record.pk, lease_owner="worker-1")

        persisted, _ = repository.mark_failed(
            claimed,
            lease_owner="worker-1",
            state=IAMAuthorizationGrant.State.RETRY_WAIT,
            error=RuntimeError("password=plain-secret user@example.com 13800138000 " + "credential-value-" * 40),
        )

        self.assertTrue(persisted)
        record.refresh_from_db()
        self.assertNotIn("plain-secret", record.last_error_message)
        self.assertNotIn("user@example.com", record.last_error_message)
        self.assertNotIn("13800138000", record.last_error_message)
        self.assertLessEqual(len(record.last_error_message), 256)
