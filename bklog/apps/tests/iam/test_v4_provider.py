from unittest.mock import Mock

from django.conf import settings
from django.test import SimpleTestCase

from apps.iam.backends.v4.codec import BKLOG_ROOT_RESOURCE_TYPE_ID, BklogNameCodec, V4ResourceCodec
from apps.iam.backends.v4.exceptions import V4ResponseError, V4TimeoutError
from apps.iam.backends.v4.provider import V4PermissionProvider
from apps.iam.handlers.actions import ActionEnum, get_action_by_id
from apps.iam.handlers.resources import ResourceEnum
from apps.iam.iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from apps.iam.iam_engine.core.types import AuthStatus


class BklogNameCodecTest(SimpleTestCase):
    def setUp(self):
        self.codec = BklogNameCodec()

    def test_encode_action_strips_v2_suffix(self):
        self.assertEqual(self.codec.encode_action("view_collection_v2"), "view_collection")

    def test_encode_action_keeps_action_without_v2_suffix(self):
        self.assertEqual(self.codec.encode_action("manage_desensitize_rule"), "manage_desensitize_rule")

    def test_negative_space_id_uses_reversible_iam_safe_encoding(self):
        encoded = self.codec.encode_resource_id("space", "-5423")

        self.assertEqual(encoded, "neg_5423")
        self.assertEqual(self.codec.decode_resource_id("space", encoded), "-5423")

    def test_space_id_encoding_keeps_positive_ids_and_other_resource_types(self):
        self.assertEqual(self.codec.encode_resource_id("space", "5423"), "5423")
        self.assertEqual(self.codec.encode_resource_id("collection", "-5423"), "-5423")

    def test_base_codec_keeps_protocol_names(self):
        codec = V4ResourceCodec()

        self.assertEqual(codec.encode_action("view_collection"), "view_collection")
        self.assertEqual(codec.encode_resource_type("space"), "space")

    def test_root_resource_type_matches_bklog_model(self):
        self.assertEqual(BKLOG_ROOT_RESOURCE_TYPE_ID, ResourceEnum.BUSINESS.id)

    def test_normalize_iam_path_adds_path_delimiters(self):
        self.assertEqual(self.codec.normalize_iam_path("space,215"), "/space,215/")

    def test_build_ancestors_from_iam_path(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": "/space,215/"},
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "215"}])

    def test_build_ancestors_encodes_negative_space_id_from_iam_path(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": "/space,-5423/"},
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "neg_5423"}])

    def test_build_ancestors_uses_resource_type_from_iam_path(self):
        resource = ResourceInstance(
            type="host",
            id="28",
            attributes={"_bk_iam_path_": "/biz,215/"},
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "biz", "id": "215"}])

    def test_build_ancestors_preserves_multiple_path_segments(self):
        resource = ResourceInstance(
            type="host",
            id="28",
            attributes={"_bk_iam_path_": "/biz,215/set,3/"},
        )

        self.assertEqual(
            self.codec.build_ancestors(resource),
            [{"type": "biz", "id": "215"}, {"type": "set", "id": "3"}],
        )

    def test_build_ancestors_falls_back_to_biz_id(self):
        resource = ResourceInstance(type="collection", id="28", attributes={"bk_biz_id": "215"})

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "215"}])

    def test_build_ancestors_falls_back_to_engine_ancestor_chain(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            ancestor_chain=(ResourceInstance(type="space", id="215"),),
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "215"}])

    def test_encode_auth_resource_normalizes_path_collection(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": ["space,215"]},
        )

        self.assertEqual(
            self.codec.encode_resource_for_auth(resource),
            {"id": "28", "attributes": {"_bk_iam_path_": "/space,215/"}},
        )

    def test_encode_space_resource_does_not_invent_iam_path(self):
        resource = ResourceInstance(type="space", id="215")

        self.assertEqual(self.codec.encode_resource_for_auth(resource), {"id": "215", "attributes": {}})

    def test_encode_negative_space_resource_for_auth(self):
        resource = ResourceInstance(type="space", id="-5423")

        self.assertEqual(self.codec.encode_resource_for_auth(resource), {"id": "neg_5423", "attributes": {}})

    def test_encode_auth_resource_encodes_negative_space_id_in_path(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": "/space,-5423/"},
        )

        self.assertEqual(
            self.codec.encode_resource_for_auth(resource),
            {"id": "28", "attributes": {"_bk_iam_path_": "/space,neg_5423/"}},
        )

    def test_build_ancestors_accepts_path_collection(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": ["space,215"]},
        )

        self.assertEqual(self.codec.build_ancestors(resource), [{"type": "space", "id": "215"}])

    def test_build_ancestors_returns_empty_for_unrelated_resource(self):
        resource = ResourceInstance(type="collection", id="28", attributes={"bk_biz_id": "not-a-number"})

        self.assertEqual(self.codec.build_ancestors(resource), [])

    def test_encode_apply_resource_uses_structured_ancestors(self):
        resource = ResourceInstance(
            type="collection",
            id="28",
            attributes={"_bk_iam_path_": "/space,215/"},
        )

        self.assertEqual(
            self.codec.encode_resource_for_apply(resource),
            {"type": "collection", "id": "28", "ancestors": [{"type": "space", "id": "215"}]},
        )

    def test_encode_negative_space_resource_for_apply(self):
        resource = ResourceInstance(type="space", id="-5423")

        self.assertEqual(
            self.codec.encode_resource_for_apply(resource),
            {"type": "space", "id": "neg_5423"},
        )


class V4PermissionProviderTest(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.client.options.system_id = "bk_log_search"
        self.client.options.batch_chunk_size = 100
        self.client.options.batch_max_workers = 4
        self.provider = V4PermissionProvider(self.client, action_resolver=get_action_by_id)

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

    def test_single_auth_encodes_negative_space_id(self):
        self.client.direct_auth.return_value = True
        request = AuthRequest(
            subject=Subject(id="admin"),
            action_id=ActionEnum.VIEW_BUSINESS,
            resources=(
                ResourceInstance(
                    system=ResourceEnum.BUSINESS.system_id,
                    type="space",
                    id="-5423",
                ),
            ),
        )

        result = self.provider.is_allowed(request)

        self.assertEqual(result.status, AuthStatus.ALLOW)
        self.client.direct_auth.assert_called_once_with(
            subject={"type": "user", "id": "admin"},
            action_id="view_business",
            resource={"id": "neg_5423", "attributes": {}},
        )

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
                (
                    ResourceInstance(
                        system=ResourceEnum.COLLECTION.system_id,
                        type="collection",
                        id="1",
                        attributes={"_bk_iam_path_": "/space,10/"},
                    ),
                ),
                (
                    ResourceInstance(
                        system=ResourceEnum.COLLECTION.system_id,
                        type="collection",
                        id="2",
                        attributes={"_bk_iam_path_": "/space,10/"},
                    ),
                ),
            ),
        )

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(self.client.direct_auth_by_resources.call_count, 2)
        self.assertFalse(result.by_key()[("manage_collection_v2", "2")].allowed)
        self.client.direct_auth.assert_not_called()

    def test_batch_maps_encoded_negative_space_result_back_to_local_id(self):
        self.client.direct_auth_by_resources.return_value = {"neg_5423": True}
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.VIEW_BUSINESS,),
            resource_groups=(
                (
                    ResourceInstance(
                        system=ResourceEnum.BUSINESS.system_id,
                        type="space",
                        id="-5423",
                    ),
                ),
            ),
        )

        result = self.provider.batch_is_allowed(request)

        self.assertTrue(result.by_key()[(ActionEnum.VIEW_BUSINESS.id, "-5423")].allowed)

    def test_batch_missing_related_resource_returns_error_without_calling_client(self):
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.VIEW_COLLECTION,),
            resource_groups=((ResourceInstance(system="other", type="other", id="1"),),),
        )

        result = self.provider.batch_is_allowed(request)

        item = result.by_key()[(ActionEnum.VIEW_COLLECTION.id, "1")]
        self.assertEqual(item.status, AuthStatus.ERROR)
        self.assertEqual(item.error_type, "IncompleteBatchResult")
        self.client.direct_auth.assert_not_called()
        self.client.direct_auth_by_resources.assert_not_called()

    def test_batch_action_without_resource_uses_single_auth(self):
        self.client.direct_auth.return_value = True
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE,),
            resource_groups=((ResourceInstance(system="placeholder", type="placeholder", id="1"),),),
        )

        result = self.provider.batch_is_allowed(request)

        self.assertEqual(
            result.by_key()[(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id, "1")].status,
            AuthStatus.ALLOW,
        )
        self.client.direct_auth.assert_called_once_with(
            subject={"type": "user", "id": "admin"},
            action_id="manage_global_desensitize_rule",
        )

    def test_batch_action_without_resource_preserves_client_error(self):
        self.client.direct_auth.side_effect = V4TimeoutError("timeout")
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE,),
            resource_groups=((ResourceInstance(system="placeholder", type="placeholder", id="1"),),),
        )

        result = self.provider.batch_is_allowed(request)

        item = result.by_key()[(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE.id, "1")]
        self.assertEqual(item.status, AuthStatus.ERROR)
        self.assertEqual(item.error_type, "TimeoutError")
        self.assertEqual(item.reason, "timeout")

    def test_batch_client_error_marks_every_resource_in_chunk_as_error(self):
        self.client.direct_auth_by_resources.side_effect = V4TimeoutError("timeout")
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.VIEW_COLLECTION,),
            resource_groups=(
                (ResourceInstance(system=ResourceEnum.COLLECTION.system_id, type="collection", id="1"),),
                (ResourceInstance(system=ResourceEnum.COLLECTION.system_id, type="collection", id="2"),),
            ),
        )

        result = self.provider.batch_is_allowed(request)

        self.assertEqual([item.result.status for item in result.items], [AuthStatus.ERROR, AuthStatus.ERROR])
        self.assertEqual([item.result.error_type for item in result.items], ["TimeoutError", "TimeoutError"])

    def test_batch_incomplete_provider_result_is_error_not_deny(self):
        self.client.direct_auth_by_resources.return_value = {}
        request = BatchAuthRequest(
            subject=Subject(id="admin"),
            action_ids=(ActionEnum.VIEW_COLLECTION,),
            resource_groups=((ResourceInstance(system=ResourceEnum.COLLECTION.system_id, type="collection", id="1"),),),
        )

        result = self.provider.batch_is_allowed(request)

        item = result.by_key()[(ActionEnum.VIEW_COLLECTION.id, "1")]
        self.assertEqual(item.status, AuthStatus.ERROR)
        self.assertEqual(item.error_type, "IncompleteBatchResult")

    def test_apply_data_uses_v4_apply_url(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"
        resources = [
            ResourceInstance(
                system=ResourceEnum.COLLECTION.system_id,
                type="collection",
                id="1",
                attributes={"_bk_iam_path_": "/space,10/"},
            )
        ]

        apply_data, apply_url = self.provider.get_apply_data([ActionEnum.VIEW_COLLECTION], resources)

        self.assertEqual(apply_url, "https://bkiam.example/apply")
        self.assertEqual(apply_data["provider"], "v4")
        self.client.generate_perm_apply_url.assert_called_once()

        # 展示数据与 V3 同构，且 id 用 V4 编码；permissions 是发给 IAM 的请求体，不进对外响应。
        self.assertNotIn("permissions", apply_data)
        self.assertEqual(apply_data["system_id"], "bk_log_search")
        self.assertEqual(apply_data["system_name"], settings.BK_IAM_SYSTEM_NAME)
        self.assertEqual(apply_data["actions"][0]["id"], "view_collection")
        self.assertEqual(apply_data["actions"][0]["name"], ActionEnum.VIEW_COLLECTION.name)
        self.assertEqual(
            apply_data["actions"][0]["related_resource_types"][0]["instances"],
            [[{"type": "collection", "type_name": ResourceEnum.COLLECTION.name, "id": "1", "name": ""}]],
        )

    def test_apply_data_matches_the_permissions_sent_to_iam(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"
        resources = [
            ResourceInstance(system=ResourceEnum.BUSINESS.system_id, type="space", id="10", name="空间A"),
            ResourceInstance(
                system=ResourceEnum.INDICES.system_id,
                type="indices",
                id="20",
                name="索引集A",
                attributes={"_bk_iam_path_": "/space,10/"},
            ),
        ]

        apply_data, _ = self.provider.get_apply_data([ActionEnum.VIEW_BUSINESS, ActionEnum.SEARCH_LOG], resources)

        def displayed_resource_ids(action):
            return [
                node["id"]
                for resource_type in action["related_resource_types"]
                for chain in resource_type["instances"]
                for node in chain
            ]

        # 展示数据与申请单由两段代码分别构造，前端不会校验两者是否一致，只能靠测试锁住：
        # 页面上写的动作和资源，必须就是申请单里的那一批。
        permissions = self.client.generate_perm_apply_url.call_args.kwargs["permissions"]
        self.assertEqual(
            [action["id"] for action in apply_data["actions"]],
            [permission["action_id"] for permission in permissions],
        )
        self.assertEqual(
            [displayed_resource_ids(action) for action in apply_data["actions"]],
            [[resource["id"] for resource in permission["resources"]] for permission in permissions],
        )

    def test_apply_data_encodes_negative_space_id_for_iam_and_display_contract(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"
        resource = ResourceInstance(
            system=ResourceEnum.BUSINESS.system_id,
            type="space",
            id="-5423",
            name="流水线空间",
        )

        apply_data, _ = self.provider.get_apply_data([ActionEnum.VIEW_BUSINESS], [resource])

        permissions = self.client.generate_perm_apply_url.call_args.kwargs["permissions"]
        self.assertEqual(
            permissions,
            [{"action_id": "view_business", "resources": [{"type": "space", "id": "neg_5423"}]}],
        )
        self.assertEqual(
            apply_data["actions"][0]["related_resource_types"][0]["instances"][0][0]["id"],
            "neg_5423",
        )

    def test_apply_data_propagates_v4_error(self):
        self.client.generate_perm_apply_url.side_effect = V4ResponseError("missing url")

        with self.assertRaisesMessage(RuntimeError, "missing url"):
            self.provider.get_apply_data([ActionEnum.VIEW_COLLECTION], [])

    def test_apply_data_filters_resources_for_each_action(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"
        resources = [
            ResourceInstance(
                system=ResourceEnum.BUSINESS.system_id,
                type="space",
                id="10",
            ),
            ResourceInstance(
                system=ResourceEnum.INDICES.system_id,
                type="indices",
                id="20",
                attributes={"_bk_iam_path_": "/space,10/"},
            ),
        ]

        self.provider.get_apply_data([ActionEnum.VIEW_BUSINESS, ActionEnum.SEARCH_LOG], resources)

        permissions = self.client.generate_perm_apply_url.call_args.kwargs["permissions"]
        self.assertEqual(
            permissions,
            [
                {"action_id": "view_business", "resources": [{"type": "space", "id": "10"}]},
                {
                    "action_id": "search_log",
                    "resources": [
                        {
                            "type": "indices",
                            "id": "20",
                            "ancestors": [{"type": "space", "id": "10"}],
                        }
                    ],
                },
            ],
        )

    def test_apply_data_action_without_related_resource_keeps_empty_resources(self):
        self.client.generate_perm_apply_url.return_value = "https://bkiam.example/apply"

        self.provider.get_apply_data(
            [ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE],
            [ResourceInstance(system=ResourceEnum.COLLECTION.system_id, type="collection", id="1")],
        )

        self.assertEqual(
            self.client.generate_perm_apply_url.call_args.kwargs["permissions"],
            [{"action_id": "manage_global_desensitize_rule", "resources": []}],
        )

    def test_string_action_requires_an_injected_resolver(self):
        provider = V4PermissionProvider(self.client)

        with self.assertRaisesMessage(ValueError, "action resolver is required"):
            provider.get_apply_data(["view_collection_v2"], [])

    def test_non_positive_batch_size_falls_back_to_default(self):
        with self.assertLogs("iam.v4.config", level="WARNING"):
            provider = V4PermissionProvider(self.client, batch_chunk_size=0)

        self.assertEqual(provider.batch_chunk_size, 100)

    def test_list_authorized_resources_returns_concrete_scope(self):
        self.client.username = "admin"
        self.client.list_authorized_resource.return_value = {"type": "space", "ids": ["2", "3"]}

        scope = self.provider.list_authorized_resources(action_id="view_business_v2")

        self.assertTrue(scope.ok)
        self.assertFalse(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset({"2", "3"}))
        self.client.list_authorized_resource.assert_called_once()

    def test_list_authorized_resources_decodes_negative_space_ids(self):
        self.client.username = "admin"
        self.client.list_authorized_resource.return_value = {"type": "space", "ids": ["neg_5423", "2"]}

        scope = self.provider.list_authorized_resources(action_id="view_business")

        self.assertEqual(scope.ids, frozenset({"-5423", "2"}))

    def test_list_authorized_resources_returns_wildcard_scope(self):
        self.client.username = "admin"
        self.client.list_authorized_resource.return_value = {"type": "space", "ids": ["*"]}

        scope = self.provider.list_authorized_resources(action_id="view_business")
        self.assertTrue(scope.is_wildcard)

    def test_list_authorized_resources_returns_empty_scope(self):
        self.client.username = "admin"
        self.client.list_authorized_resource.return_value = {"type": "space", "ids": []}

        scope = self.provider.list_authorized_resources(action_id="view_business")

        self.assertTrue(scope.ok)
        self.assertFalse(scope.is_wildcard)
        self.assertEqual(scope.ids, frozenset())

    def test_list_authorized_resources_rejects_empty_subject(self):
        self.client.username = ""

        scope = self.provider.list_authorized_resources(action_id="view_business")

        self.assertFalse(scope.ok)
        self.assertEqual(scope.error_type, "InvalidSubject")
        self.client.list_authorized_resource.assert_not_called()

    def test_list_authorized_resources_maps_client_error(self):
        self.client.username = "admin"
        self.client.list_authorized_resource.side_effect = V4TimeoutError("timeout")

        scope = self.provider.list_authorized_resources(action_id="view_business")
        self.assertFalse(scope.ok)
        self.assertEqual(scope.error_type, "TimeoutError")
