from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.iam.backends.v4.exceptions import V4ResponseError
from apps.iam.backends.v4.provider import V4PermissionProvider
from apps.iam.handlers.actions import get_action_by_id
from apps.iam.handlers.resources import ResourceEnum
from apps.iam.iam_engine.core.requests import BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthStatus


class V4BatchProviderTest(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.client.options.system_id = "bk_log_search"
        self.provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=20,
        )

    def _make_request(self, resource_count: int, action_count: int = 1) -> BatchAuthRequest:
        resource_groups = tuple(
            (
                ResourceInstance(
                    system=ResourceEnum.COLLECTION.system_id,
                    type="collection",
                    id=str(index),
                    attributes={"_bk_iam_path_": "/space,10/"},
                ),
            )
            for index in range(1, resource_count + 1)
        )
        if action_count == 2:
            action_ids = ("view_collection_v2", "manage_collection_v2")
        else:
            action_ids = ("view_collection_v2",)
        return BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=action_ids,
            resource_groups=resource_groups,
        )

    def test_batch_does_not_call_single_auth_for_each_resource(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }
        request = self._make_request(resource_count=250, action_count=1)

        self.provider.batch_is_allowed(request)

        self.assertEqual(self.client.direct_auth.call_count, 0)
        self.assertEqual(self.client.direct_auth_by_resources.call_count, 13)

    def test_batch_chunks_by_configured_size(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }
        request = self._make_request(resource_count=125, action_count=1)

        self.provider.batch_is_allowed(request)

        chunk_sizes = [len(call.kwargs["resources"]) for call in self.client.direct_auth_by_resources.call_args_list]
        self.assertEqual(chunk_sizes, [20, 20, 20, 20, 20, 20, 5])

    def test_batch_size_is_capped_at_v4_contract_limit(self):
        provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=100,
        )
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }

        provider.batch_is_allowed(self._make_request(resource_count=101))

        chunk_sizes = [len(call.kwargs["resources"]) for call in self.client.direct_auth_by_resources.call_args_list]
        self.assertEqual(chunk_sizes, [20, 20, 20, 20, 20, 1])

    def test_partial_batch_response_marks_missing_items_as_error(self):
        self.client.direct_auth_by_resources.side_effect = V4ResponseError("missing IAM V4 batch results")
        request = self._make_request(resource_count=2, action_count=1)

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(result.items[0].result.status, AuthStatus.ERROR)
        self.assertEqual(result.items[1].result.status, AuthStatus.ERROR)
        self.assertEqual(result.items[1].result.error_type, "InvalidResponse")

    def test_multiple_actions_use_one_batch_call_per_action(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }
        request = self._make_request(resource_count=10, action_count=2)

        self.provider.batch_is_allowed(request)

        self.assertEqual(self.client.direct_auth_by_resources.call_count, 2)
