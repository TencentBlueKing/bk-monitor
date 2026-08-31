from unittest.mock import Mock

from django.test import SimpleTestCase
from iam.exceptions import AuthAPIError

from apps.iam.backends.v3.provider import V3PermissionProvider
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthStatus


class V3PermissionProviderTest(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.provider = V3PermissionProvider(client=self.client, system_id="bk_log_search")
        self.request = AuthRequest(
            subject=Subject(id="admin", tenant_id="tenant-1"),
            action_id="search_log_v2",
            resources=(
                ResourceInstance(
                    system="bk_log_search",
                    type="indices",
                    id="1001",
                    name="index-set",
                    attributes={"_bk_iam_path_": "/space,2/"},
                ),
            ),
        )

    def test_allow_result_is_preserved(self):
        self.client.is_allowed.return_value = True

        result = self.provider.is_allowed(self.request)

        self.assertEqual(result.status, AuthStatus.ALLOW)
        self.assertEqual(result.provider_name, "v3")

    def test_deny_result_is_preserved(self):
        self.client.is_allowed.return_value = False

        result = self.provider.is_allowed(self.request)

        self.assertEqual(result.status, AuthStatus.DENY)
        self.assertEqual(result.provider_name, "v3")

    def test_auth_api_error_is_not_collapsed_into_deny(self):
        self.client.is_allowed.side_effect = AuthAPIError("request timeout")

        result = self.provider.is_allowed(self.request)

        self.assertEqual(result.status, AuthStatus.ERROR)
        self.assertEqual(result.provider_name, "v3")
        self.assertEqual(result.reason, "request timeout")
        self.assertEqual(result.error_type, "AuthAPIError")

    def test_unexpected_programming_error_is_not_swallowed(self):
        self.client.is_allowed.side_effect = ValueError("invalid request")

        with self.assertRaisesMessage(ValueError, "invalid request"):
            self.provider.is_allowed(self.request)

    def test_request_is_converted_without_changing_v3_semantics(self):
        self.client.is_allowed.return_value = True

        self.provider.is_allowed(self.request)

        v3_request = self.client.is_allowed.call_args.args[0]
        self.assertEqual(
            v3_request.to_dict(),
            {
                "system": "bk_log_search",
                "subject": {"type": "user", "id": "admin"},
                "action": {"id": "search_log_v2"},
                "resources": [
                    {
                        "system": "bk_log_search",
                        "type": "indices",
                        "id": "1001",
                        "attribute": {"_bk_iam_path_": "/space,2/", "name": "index-set"},
                    }
                ],
                "environment": {},
            },
        )

    def test_batch_result_is_normalized_to_three_state_items(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2", "manage_collection_v2"),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        self.client.batch_resource_multi_actions_allowed.return_value = {
            "1": {"view_collection_v2": True, "manage_collection_v2": False}
        }

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(
            [(item.action_id, item.resource_id, item.result.status) for item in result.items],
            [
                ("view_collection_v2", "1", AuthStatus.ALLOW),
                ("manage_collection_v2", "1", AuthStatus.DENY),
            ],
        )

    def test_batch_request_is_converted_without_changing_v3_semantics(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1", name="collection-1"),),),
        )
        self.client.batch_resource_multi_actions_allowed.return_value = {"1": {"view_collection_v2": True}}

        self.provider.batch_is_allowed(request)

        v3_request, resource_groups = self.client.batch_resource_multi_actions_allowed.call_args.args
        self.assertEqual(
            v3_request.to_dict(),
            {
                "system": "bk_log_search",
                "subject": {"type": "user", "id": "admin"},
                "actions": [{"id": "view_collection_v2"}],
                "resources": [],
                "environment": {},
            },
        )
        self.assertEqual(
            [[resource.to_dict() for resource in group] for group in resource_groups],
            [
                [
                    {
                        "system": "bk_log_search",
                        "type": "collection",
                        "id": "1",
                        "attribute": {"name": "collection-1"},
                    }
                ]
            ],
        )

    def test_missing_batch_item_is_error(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        self.client.batch_resource_multi_actions_allowed.return_value = {}

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(result.items[0].result.status, AuthStatus.ERROR)
        self.assertEqual(result.items[0].result.error_type, "IncompleteBatchResult")

    def test_batch_auth_api_error_is_returned_for_every_item(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2",),
            resource_groups=((ResourceInstance(type="collection", id="1"),),),
        )
        self.client.batch_resource_multi_actions_allowed.side_effect = AuthAPIError("batch timeout")

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(result.items[0].result.status, AuthStatus.ERROR)
        self.assertEqual(result.items[0].result.reason, "batch timeout")
        self.assertEqual(result.items[0].result.error_type, "AuthAPIError")
