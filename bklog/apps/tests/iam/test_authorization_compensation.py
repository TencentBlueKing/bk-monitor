from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant
from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository
from apps.iam.tasks.compensation import compensate_iam_authorization_grants, retry_authorization_grant


@override_settings(BK_IAM_GRANT_LEASE_SECONDS=120, BK_IAM_GRANT_MAX_ATTEMPTS=12)
class AuthorizationCompensationTest(TestCase):
    def make_record(self, **overrides) -> IAMAuthorizationGrant:
        values = {
            "logical_key": "c" * 64,
            "target_version": "v4",
            "tenant_id": "tenant-1",
            "subject_id": "creator",
            "operator": "operator",
            "resource_system": "bk_log_search",
            "resource_type": "collection",
            "resource_id": "28",
            "semantic_role": "resource_creator",
            "role_id": "space_operator",
            "payload": [{"resources": [{"type": "collection", "id": "28"}], "expired_at": 1893456000}],
            "expired_at": 1893456000,
        }
        values.update(overrides)
        return IAMAuthorizationGrant.objects.create(**values)

    @patch("apps.iam.tasks.compensation.build_writer")
    def test_retry_uses_frozen_payload_and_marks_only_target_succeeded(self, build_writer):
        record = self.make_record(state=IAMAuthorizationGrant.State.UNKNOWN, next_retry_at=timezone.now())
        writer = Mock()
        build_writer.return_value = writer

        retry_authorization_grant(record.pk)

        writer.grant_prepared.assert_called_once_with(
            PreparedAuthorizationGrant(
                payload=record.payload,
                role_id="space_operator",
                expired_at=1893456000,
            )
        )
        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.SUCCEEDED)

    def test_expired_processing_lease_recovers_as_unknown(self):
        record = self.make_record(
            state=IAMAuthorizationGrant.State.PROCESSING,
            lease_owner="dead-worker",
            lease_until=timezone.now() - timedelta(seconds=1),
        )

        self.assertEqual(IAMAuthorizationGrantRepository.recover_expired_leases(), 1)

        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.UNKNOWN)
        self.assertEqual(record.lease_owner, "")
        self.assertIsNotNone(record.next_retry_at)

    def test_expired_processing_lease_at_attempt_limit_becomes_final(self):
        record = self.make_record(
            state=IAMAuthorizationGrant.State.PROCESSING,
            attempts=12,
            lease_owner="dead-worker",
            lease_until=timezone.now() - timedelta(seconds=1),
        )

        self.assertEqual(IAMAuthorizationGrantRepository.recover_expired_leases(), 1)

        record.refresh_from_db()
        self.assertEqual(record.state, IAMAuthorizationGrant.State.FAILED_FINAL)
        self.assertIsNone(record.next_retry_at)
        self.assertEqual(IAMAuthorizationGrantRepository.due_ids(limit=10), [])

    @override_settings(BK_IAM_GRANT_COMPENSATION_BATCH_SIZE="invalid")
    @patch("apps.iam.tasks.compensation.retry_authorization_grant")
    @patch("apps.iam.tasks.compensation.IAMAuthorizationGrantRepository")
    def test_compensation_uses_default_batch_size_for_invalid_setting(self, repository_class, retry_grant):
        repository = repository_class.return_value
        repository.recover_expired_leases.return_value = 0
        repository.due_ids.return_value = []

        with self.assertLogs("iam.grant.config", level="WARNING"):
            compensate_iam_authorization_grants.run()

        repository.due_ids.assert_called_once_with(limit=100)
        retry_grant.assert_not_called()
