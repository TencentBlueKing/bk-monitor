from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from apps.iam.backends.legacy_v3 import LegacyV3AuthorizationWriter, LegacyV3GrantError
from apps.iam.backends.v4.writer import UnsupportedV4GrantResource, V4AuthorizationWriter


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

    def test_v3_false_tuple_is_normalized_to_failure(self):
        client = Mock()
        client.grant_resource_creator_actions.return_value = (False, "temporary failure")
        writer = LegacyV3AuthorizationWriter(client)

        with self.assertRaisesMessage(LegacyV3GrantError, "temporary failure"):
            writer.grant_resource_creator_actions(
                {"system": "bk_log_search", "type": "collection", "id": "1", "creator": "creator"}
            )
