from unittest.mock import Mock

from django.test import SimpleTestCase
from iam import Resource

from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.backends.v4.exceptions import V4ResponseError, V4TimeoutError
from apps.iam.backends.v4.provider import V4PermissionProvider
from apps.iam.handlers.actions import ActionEnum
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthStatus


class BklogNameCodecTest(SimpleTestCase):
    def setUp(self):
        self.codec = BklogNameCodec()

    def test_encode_action_strips_v2_suffix(self):
        self.assertEqual(self.codec.encode_action("view_collection_v2"), "view_collection")

    def test_normalize_iam_path_converts_biz_to_space(self):
        self.assertEqual(self.codec.normalize_iam_path("/biz,215/"), "/space,215/")

    def test_build_ancestors_from_iam_path(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": "/space,215/"},
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "215"}])


class V4PermissionProviderTest(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.client.options.system_id = "bk_log_search"
        self.client.options.batch_chunk_size = 100
        self.provider = V4PermissionProvider(self.client)

    def test_single_allow_result(self):
        self.client.direct_auth.return_value = True
        request = AuthRequest(
            subject=Subject(id="admin", tenant_id="tenant-1"),
            action_id="view_collection_v2",
            resources=(ResourceInstance(type="collection", id="1", attributes={"_bk_iam_path_": "/space,10/"}),),
        )

        result = self.provider.is_allowed(request)

        self.assertEqual(result.status, AuthStatus.ALLOW)
        self.client.direct_auth.assert_called_once()

    def test_single_deny_result(self):
        self.client.direct_auth.return_value = False
        request = AuthRequest(subject=Subject(id="admin"), action_id="view_collection_v2")

        result = self.provider.is_allowed(request)

        self.assertEqual(result.status, AuthStatus.DENY)

    def test_single_error_is_not_collapsed_into_deny(self):
        self.client.direct_auth.side_effect = V4TimeoutError("timeout")
        request = AuthRequest(subject=Subject(id="admin"), action_id="view_collection_v2")

        result = self.provider.is_allowed(request)

        self.assertEqual(result.status, AuthStatus.ERROR)
        self.assertEqual(result.error_type, "TimeoutError")

    def test_batch_uses_auth_by_resources_per_action(self):
        self.client.direct_auth_by_resources.return_value = {"1": True, "2": False}
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=("view_collection_v2", "manage_collection_v2"),
            resource_groups=(
                (ResourceInstance(type="collection", id="1", attributes={"_bk_iam_path_": "/space,10/"}),),
                (ResourceInstance(type="collection", id="2", attributes={"_bk_iam_path_": "/space,10/"}),),
            ),
        )

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(self.client.direct_auth_by_resources.call_count, 2)
        self.assertFalse(result.by_key()[("manage_collection_v2", "2")].allowed)
        self.client.direct_auth.assert_not_called()

    def test_apply_data_uses_v4_apply_url(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"
        resources = [Resource("bk_log_search", "collection", "1", {"_bk_iam_path_": "/space,10/"})]

        apply_data, apply_url = self.provider.get_apply_data([ActionEnum.VIEW_COLLECTION], resources)

        self.assertEqual(apply_url, "https://bkiam.example/apply")
        self.assertEqual(apply_data["provider"], "v4")
        self.client.generate_perm_apply_url.assert_called_once()

    def test_apply_data_propagates_v4_error(self):
        self.client.generate_perm_apply_url.side_effect = V4ResponseError("missing url")

        with self.assertRaisesMessage(RuntimeError, "missing url"):
            self.provider.get_apply_data([ActionEnum.VIEW_COLLECTION], [])
