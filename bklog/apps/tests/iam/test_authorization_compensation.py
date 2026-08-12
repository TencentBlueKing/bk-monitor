from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.iam.iam_engine.provider.capabilities import PreparedAuthorizationGrant
from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository
from apps.iam.tasks.compensation import build_writer, compensate_iam_authorization_grants, retry_authorization_grant


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

    @patch("apps.iam.tasks.compensation.Permission.get_iam_client")
    def test_build_writer_uses_frozen_target_configuration(self, get_iam_client):
        v3_grant = self.make_record(logical_key="7" * 64, target_version=IAMAuthorizationGrant.TargetVersion.V3)
        v4_grant = self.make_record(logical_key="8" * 64, target_version=IAMAuthorizationGrant.TargetVersion.V4)

        with patch("apps.iam.tasks.compensation.V4AuthorizationWriter.from_settings") as v4_from_settings:
            v3_writer = build_writer(v3_grant)
            v4_writer = build_writer(v4_grant)

        self.assertIs(v3_writer.iam_client, get_iam_client.return_value)
        v4_from_settings.assert_called_once_with(username="operator", bk_tenant_id="tenant-1")
        self.assertIs(v4_writer, v4_from_settings.return_value)

    def test_build_writer_rejects_unknown_target(self):
        grant = self.make_record(target_version="v5")

        with self.assertRaisesRegex(ValueError, "unsupported IAM grant target"):
            build_writer(grant)

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

    @override_settings(BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS=50)
    @patch("apps.iam.tasks.compensation.time.monotonic", side_effect=[0, 1, 51])
    @patch("apps.iam.tasks.compensation.retry_authorization_grant")
    @patch("apps.iam.tasks.compensation.IAMAuthorizationGrantRepository")
    def test_compensation_stops_when_round_time_budget_is_exhausted(
        self,
        repository_class,
        retry_grant,
        _,
    ):
        repository = repository_class.return_value
        repository.recover_expired_leases.return_value = 0
        repository.due_ids.return_value = [1, 2]

        with patch("apps.iam.tasks.compensation.logger.warning") as warning:
            compensate_iam_authorization_grants.run()

        retry_grant.assert_called_once_with(1)
        warning.assert_called_once_with("[IAM Compensation] round time budget exhausted remaining=%s", 1)

    @override_settings(BK_IAM_GRANT_COMPENSATION_TIME_BUDGET_SECONDS=50)
    @patch("apps.iam.tasks.compensation.time.monotonic", side_effect=[0, 1])
    @patch("apps.iam.tasks.compensation.retry_authorization_grant", side_effect=RuntimeError("unexpected"))
    @patch("apps.iam.tasks.compensation.IAMAuthorizationGrantRepository")
    def test_compensation_logs_unexpected_record_error_and_continues(
        self,
        repository_class,
        _,
        __,
    ):
        repository = repository_class.return_value
        repository.recover_expired_leases.return_value = 0
        repository.due_ids.return_value = [1]

        with patch("apps.iam.tasks.compensation.logger.exception") as exception_log:
            compensate_iam_authorization_grants.run()

        exception_log.assert_called_once_with("[IAM Compensation] unexpected failure grant_id=%s", 1)
