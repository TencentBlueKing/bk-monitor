from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v3.exceptions import V3GrantError
from apps.iam.backends.v3.writer import V3AuthorizationWriter
from apps.iam.backends.v4.exceptions import V4ClientError, V4RateLimitError, V4TimeoutError
from apps.iam.backends.v4.writer import UnsupportedV4GrantResource, V4AuthorizationWriter
from apps.iam.iam_engine.provider.capabilities import GrantFailureKind


@override_settings(BK_IAM_V4_GRANT_EXPIRE_DAYS=365)
class AuthorizationWriterTest(SimpleTestCase):
    def test_v4_creator_grant_maps_collection_to_exact_space_operator_role(self):
        client = Mock()
        writer = V4AuthorizationWriter(client, operator="operator")
        application = {
            "system": "bk_log_search",
            "type": "collection",
            "id": "28",
            "name": "collection-28",
            "creator": "creator",
        }

        prepared = writer.prepare_resource_creator_actions(application, expired_at=1893456000)
        writer.grant_prepared(prepared)

        self.assertEqual(prepared.role_id, "space_operator")
        client.add_authorization.assert_called_once_with(
            items=[
                {
                    "subject": {"type": "user", "id": "creator"},
                    "role_id": "space_operator",
                    "related_resource_type_id": "collection",
                    "resources": [{"type": "collection", "id": "28"}],
                    "expired_at": 1893456000,
                }
            ],
            operator="operator",
        )

    def test_v4_creator_grant_rejects_unmapped_resource(self):
        writer = V4AuthorizationWriter(Mock(), operator="operator")

        with self.assertRaises(UnsupportedV4GrantResource):
            writer.prepare_resource_creator_actions(
                {"system": "bk_log_search", "type": "space", "id": "1", "creator": "creator"}
            )

    def test_all_confirmed_resource_types_map_to_space_operator(self):
        writer = V4AuthorizationWriter(Mock(), operator="operator")

        for resource_type in ("collection", "indices", "es_source"):
            with self.subTest(resource_type=resource_type):
                prepared = writer.prepare_resource_creator_actions(
                    {
                        "system": "bk_log_search",
                        "type": resource_type,
                        "id": "1",
                        "creator": "creator",
                    },
                    expired_at=1893456000,
                )
                self.assertEqual(prepared.role_id, "space_operator")
                self.assertEqual(prepared.payload[0]["related_resource_type_id"], resource_type)
                self.assertEqual(prepared.payload[0]["resources"], [{"type": resource_type, "id": "1"}])

    @override_settings(BK_IAM_V4_GRANT_EXPIRE_DAYS="invalid")
    @patch("apps.iam.backends.v4.writer.timezone.now")
    def test_invalid_expire_days_uses_default_without_startup_failure(self, now):
        frozen_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now.return_value = frozen_now
        writer = V4AuthorizationWriter(Mock(), operator="operator")

        with self.assertLogs("iam.grant.config", level="WARNING"):
            prepared = writer.prepare_resource_creator_actions(
                {
                    "system": "bk_log_search",
                    "type": "collection",
                    "id": "1",
                    "creator": "creator",
                }
            )

        expected_expired_at = int((frozen_now + timedelta(days=365)).timestamp())
        self.assertEqual(prepared.expired_at, expected_expired_at)
        self.assertEqual(prepared.payload[0]["expired_at"], expected_expired_at)

    def test_v3_false_tuple_is_normalized_to_failure(self):
        client = Mock()
        client.grant_resource_creator_actions.return_value = (False, "temporary failure")
        writer = V3AuthorizationWriter(client)

        with self.assertRaisesMessage(V3GrantError, "temporary failure"):
            writer.grant_resource_creator_actions(
                {"system": "bk_log_search", "type": "collection", "id": "1", "creator": "creator"}
            )

    @patch("apps.iam.backends.v4.writer.V4Options.from_settings")
    @patch("apps.iam.backends.v4.writer.V4Client")
    def test_v4_writer_from_settings_binds_operator(self, client_class, options_from_settings):
        writer = V4AuthorizationWriter.from_settings(username="operator", bk_tenant_id="tenant-1")

        client_class.assert_called_once_with(
            options_from_settings.return_value,
            username="operator",
            bk_tenant_id="tenant-1",
        )
        self.assertEqual(writer.operator, "operator")

    def test_v4_grant_resource_creator_actions_uses_prepare_and_grant(self):
        writer = V4AuthorizationWriter(Mock(), operator="operator")
        application = {"system": "bk_log_search", "type": "indices", "id": "1", "creator": "creator"}

        with patch.object(writer, "grant_prepared") as grant_prepared:
            writer.grant_resource_creator_actions(application)

        grant_prepared.assert_called_once()

    def test_v4_payload_value_error_is_final_without_retry(self):
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(ValueError("invalid payload")),
            GrantFailureKind.FAILED_FINAL,
        )

    def test_v4_403_is_final_and_timeout_remains_unknown(self):
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(V4ClientError("forbidden", status_code=403)),
            GrantFailureKind.FAILED_FINAL,
        )
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(V4TimeoutError("timeout")),
            GrantFailureKind.UNKNOWN,
        )

    def test_v4_retryable_failure_classification(self):
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(V4RateLimitError("limited")),
            GrantFailureKind.RETRY_WAIT,
        )
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(V4ClientError("server error", status_code=500)),
            GrantFailureKind.RETRY_WAIT,
        )
        self.assertEqual(
            V4AuthorizationWriter.classify_failure(RuntimeError("unexpected")),
            GrantFailureKind.RETRY_WAIT,
        )
