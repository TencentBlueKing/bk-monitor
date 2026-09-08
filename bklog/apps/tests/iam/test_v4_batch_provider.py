from unittest.mock import Mock, patch

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
        self.client.options.batch_max_workers = 4
        self.provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=100,
            batch_max_workers=4,
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
        self.assertEqual(self.client.direct_auth_by_resources.call_count, 3)

    def test_batch_chunks_by_configured_size(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }
        request = self._make_request(resource_count=125, action_count=1)

        self.provider.batch_is_allowed(request)

        chunk_sizes = [len(call.kwargs["resources"]) for call in self.client.direct_auth_by_resources.call_args_list]
        self.assertEqual(chunk_sizes, [100, 25])

    def test_batch_size_is_capped_at_v4_contract_limit(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }

        with self.assertLogs("iam.v4.config", level="WARNING"):
            provider = V4PermissionProvider(
                self.client,
                action_resolver=get_action_by_id,
                batch_chunk_size=101,
            )
            provider.batch_is_allowed(self._make_request(resource_count=101))

        chunk_sizes = [len(call.kwargs["resources"]) for call in self.client.direct_auth_by_resources.call_args_list]
        self.assertEqual(chunk_sizes, [100, 1])

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

    def test_multiple_actions_do_not_nest_parallel_chunk_pools(self):
        self.client.direct_auth_by_resources.side_effect = lambda **kwargs: {
            resource["id"]: True for resource in kwargs["resources"]
        }
        worker_limits = []

        def _run_inline(items, function, *, max_workers):
            worker_limits.append(max_workers)
            return [function(item) for item in items]

        with patch(
            "apps.iam.backends.v4.provider.map_chunks_concurrently",
            side_effect=_run_inline,
        ):
            self.provider.batch_is_allowed(self._make_request(resource_count=250, action_count=2))

        self.assertEqual(worker_limits, [4, 1, 1])

    def test_multiple_actions_merge_per_action_results(self):
        def _side_effect(**kwargs):
            action_id = kwargs["action_id"]
            allowed = action_id == "view_collection"
            return {resource["id"]: allowed for resource in kwargs["resources"]}

        self.client.direct_auth_by_resources.side_effect = _side_effect
        request = self._make_request(resource_count=3, action_count=2)

        result = self.provider.batch_is_allowed(request)
        by_key = {(item.action_id, item.resource_id): item.result for item in result.items}

        self.assertTrue(by_key[("view_collection_v2", "1")].allowed)
        self.assertTrue(by_key[("view_collection_v2", "3")].allowed)
        self.assertFalse(by_key[("manage_collection_v2", "1")].allowed)
        self.assertFalse(by_key[("manage_collection_v2", "2")].allowed)

    def test_multiple_actions_run_concurrently(self):
        import threading
        import time

        started = threading.Event()
        release = threading.Event()
        seen_actions = []

        def _side_effect(**kwargs):
            action_id = kwargs["action_id"]
            seen_actions.append(action_id)
            if action_id == "view_collection":
                started.set()
                release.wait(timeout=1)
            else:
                if not started.wait(timeout=1):
                    return {resource["id"]: False for resource in kwargs["resources"]}
                release.set()
            return {resource["id"]: True for resource in kwargs["resources"]}

        self.client.direct_auth_by_resources.side_effect = _side_effect
        request = self._make_request(resource_count=5, action_count=2)

        started_at = time.monotonic()
        result = self.provider.batch_is_allowed(request)
        elapsed = time.monotonic() - started_at

        self.assertEqual(self.client.direct_auth_by_resources.call_count, 2)
        self.assertTrue(all(item.result.allowed for item in result.items))
        self.assertLess(elapsed, 0.5)
        self.assertEqual(len(seen_actions), 2)

    def test_concurrent_chunks_merge_results(self):
        def _side_effect(**kwargs):
            return {resource["id"]: int(resource["id"]) % 2 == 1 for resource in kwargs["resources"]}

        self.client.direct_auth_by_resources.side_effect = _side_effect
        provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=100,
            batch_max_workers=4,
        )
        result = provider.batch_is_allowed(self._make_request(resource_count=250))

        self.assertEqual(self.client.direct_auth_by_resources.call_count, 3)
        allowed = {item.resource_id for item in result.items if item.result.allowed}
        self.assertEqual(allowed, {str(i) for i in range(1, 251, 2)})

    def test_partial_chunk_error_keeps_other_chunks(self):
        def _side_effect(**kwargs):
            resource_ids = [resource["id"] for resource in kwargs["resources"]]
            if "1" in resource_ids:
                raise V4ResponseError("first chunk failed")
            return {resource_id: True for resource_id in resource_ids}

        self.client.direct_auth_by_resources.side_effect = _side_effect
        provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=100,
            batch_max_workers=4,
        )
        result = provider.batch_is_allowed(self._make_request(resource_count=250))

        by_id = {item.resource_id: item.result for item in result.items}
        self.assertEqual(by_id["1"].status, AuthStatus.ERROR)
        self.assertEqual(by_id["100"].status, AuthStatus.ERROR)
        self.assertTrue(by_id["101"].allowed)
        self.assertTrue(by_id["250"].allowed)

    def test_max_workers_one_keeps_serial_semantics(self):
        call_order = []

        def _side_effect(**kwargs):
            resource_ids = [resource["id"] for resource in kwargs["resources"]]
            call_order.append(resource_ids[0])
            return {resource_id: True for resource_id in resource_ids}

        self.client.direct_auth_by_resources.side_effect = _side_effect
        provider = V4PermissionProvider(
            self.client,
            action_resolver=get_action_by_id,
            batch_chunk_size=100,
            batch_max_workers=1,
        )
        result = provider.batch_is_allowed(self._make_request(resource_count=250))

        self.assertEqual(call_order, ["1", "101", "201"])
        self.assertTrue(all(item.result.allowed for item in result.items))
