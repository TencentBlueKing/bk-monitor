from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from iam.exceptions import AuthAPIError

from apps.iam.backends.v3.client import CompatibleIAM, build_v3_client

COMPATIBILITY_FLAG = "__compatibility_mode"


def make_client(compatibility_mode: bool | None = True) -> CompatibleIAM:
    client = CompatibleIAM("app", "secret", "https://iam.example/api")
    client._client = Mock()
    if compatibility_mode is not None:
        setattr(CompatibleIAM, COMPATIBILITY_FLAG, compatibility_mode)
    return client


class CompatibleIAMModeTest(SimpleTestCase):
    def tearDown(self):
        if hasattr(CompatibleIAM, COMPATIBILITY_FLAG):
            delattr(CompatibleIAM, COMPATIBILITY_FLAG)

    def test_compatibility_mode_defaults_to_on_when_switch_is_absent(self):
        from apps.log_search.models import GlobalConfig

        client = make_client(compatibility_mode=None)
        with patch.object(GlobalConfig.objects, "get", side_effect=GlobalConfig.DoesNotExist):
            self.assertTrue(client.in_compatibility_mode())

    def test_compatibility_mode_follows_the_global_config_switch(self):
        from apps.log_search.models import GlobalConfig

        client = make_client(compatibility_mode=None)
        with patch.object(GlobalConfig.objects, "get", return_value=Mock(configs=False)):
            self.assertFalse(client.in_compatibility_mode())

    def test_switch_is_read_once_and_cached_on_the_class(self):
        from apps.log_search.models import GlobalConfig

        client = make_client(compatibility_mode=None)
        with patch.object(GlobalConfig.objects, "get", return_value=Mock(configs=True)) as mocked_get:
            client.in_compatibility_mode()
            client.in_compatibility_mode()

        self.assertEqual(mocked_get.call_count, 1)


class PatchPolicyExpressionTest(SimpleTestCase):
    def setUp(self):
        self.client = make_client()

    def tearDown(self):
        delattr(CompatibleIAM, COMPATIBILITY_FLAG)

    def test_empty_expression_is_left_untouched(self):
        self.assertIsNone(self.client._patch_policy_expression({}))

    def test_biz_field_and_value_are_rewritten_to_space(self):
        expression = {"op": "eq", "field": "biz.id", "value": "biz,1"}

        self.client._patch_policy_expression(expression)

        self.assertEqual(expression, {"op": "eq", "field": "space.id", "value": "space,1"})

    def test_or_expression_is_rewritten_recursively(self):
        expression = {
            "op": "OR",
            "content": [
                {"op": "eq", "field": "biz.id", "value": "2"},
                {"op": "starts_with", "field": "collection._bk_iam_path_", "value": "/biz,3/"},
            ],
        }

        self.client._patch_policy_expression(expression)

        self.assertEqual(
            expression["content"],
            [
                {"op": "eq", "field": "space.id", "value": "2"},
                {"op": "starts_with", "field": "collection._bk_iam_path_", "value": "/space,3/"},
            ],
        )


class DoPolicyQueryTest(SimpleTestCase):
    def tearDown(self):
        if hasattr(CompatibleIAM, COMPATIBILITY_FLAG):
            delattr(CompatibleIAM, COMPATIBILITY_FLAG)

    @staticmethod
    def make_request(action_id: str) -> Mock:
        return Mock(
            **{
                "to_dict.return_value": {
                    "action": {"id": action_id},
                    "resources": [{"system": "bk_log_search", "type": "collection", "id": "28"}],
                }
            }
        )

    def test_non_compatibility_mode_falls_back_to_the_sdk_implementation(self):
        client = make_client(compatibility_mode=False)
        client._client.v2_policy_query.return_value = (True, "ok", {"op": "any", "value": []})

        policies = client._do_policy_query(self.make_request("view_collection_v2"))

        self.assertEqual(policies, {"op": "any", "value": []})
        client._client.policy_query.assert_not_called()

    def test_actions_without_v2_suffix_only_query_once(self):
        client = make_client()
        client._client.policy_query.return_value = (True, "ok", {"op": "eq", "field": "space.id", "value": "1"})

        policies = client._do_policy_query(self.make_request("view_collection"))

        self.assertEqual(policies, {"op": "eq", "field": "space.id", "value": "1"})
        self.assertEqual(client._client.policy_query.call_count, 1)

    def test_dropping_resources_queries_all_policies(self):
        client = make_client()
        client._client.policy_query.return_value = (True, "ok", {})

        client._do_policy_query(self.make_request("view_collection"), with_resources=False)

        self.assertEqual(client._client.policy_query.call_args.args[0]["resources"], [])

    def test_v2_action_also_queries_the_v1_action_against_cmdb_business(self):
        client = make_client()
        request = Mock(
            **{
                "to_dict.return_value": {
                    "action": {"id": "view_collection_v2"},
                    "resources": [
                        {
                            "system": "bk_log_search",
                            "type": "space",
                            "id": "1",
                            "attribute": {"_bk_iam_path_": "/space,1/"},
                        }
                    ],
                }
            }
        )
        client._client.policy_query.side_effect = [(True, "ok", {}), (True, "ok", {})]

        client._do_policy_query(request)

        v1_data = client._client.policy_query.call_args_list[1].args[0]
        self.assertEqual(v1_data["action"]["id"], "view_collection")
        self.assertEqual(v1_data["resources"][0]["system"], "bk_cmdb")
        self.assertEqual(v1_data["resources"][0]["type"], "biz")
        self.assertEqual(v1_data["resources"][0]["attribute"]["_bk_iam_path_"], "/biz,1/")

    def test_v1_policies_are_used_when_the_v2_action_has_none(self):
        client = make_client()
        client._client.policy_query.side_effect = [
            (True, "ok", {}),
            (True, "ok", {"op": "eq", "field": "biz.id", "value": "2"}),
        ]

        policies = client._do_policy_query(self.make_request("view_collection_v2"))

        self.assertEqual(policies, {"op": "eq", "field": "space.id", "value": "2"})

    def test_v1_and_v2_policies_are_combined_with_or(self):
        client = make_client()
        client._client.policy_query.side_effect = [
            (True, "ok", {"op": "eq", "field": "space.id", "value": "1"}),
            (True, "ok", {"op": "eq", "field": "biz.id", "value": "2"}),
        ]

        policies = client._do_policy_query(self.make_request("view_collection_v2"))

        self.assertEqual(
            policies,
            {
                "op": "OR",
                "content": [
                    {"op": "eq", "field": "space.id", "value": "1"},
                    {"op": "eq", "field": "space.id", "value": "2"},
                ],
            },
        )

    def test_failed_query_without_policies_raises(self):
        client = make_client()
        client._client.policy_query.return_value = (False, "iam unavailable", None)

        with self.assertRaises(AuthAPIError):
            client._do_policy_query(self.make_request("view_collection"))


class DoPolicyQueryByActionsTest(SimpleTestCase):
    def tearDown(self):
        if hasattr(CompatibleIAM, COMPATIBILITY_FLAG):
            delattr(CompatibleIAM, COMPATIBILITY_FLAG)

    @staticmethod
    def make_request(*action_ids: str) -> Mock:
        return Mock(
            **{
                "to_dict.return_value": {
                    "actions": [{"id": action_id} for action_id in action_ids],
                    "resources": [{"system": "bk_log_search", "type": "space", "id": "1"}],
                }
            }
        )

    def test_non_compatibility_mode_falls_back_to_the_sdk_implementation(self):
        client = make_client(compatibility_mode=False)
        client._client.v2_policy_query_by_actions.return_value = (True, "ok", [])

        self.assertEqual(client._do_policy_query_by_actions(self.make_request("view_collection_v2")), [])
        client._client.policy_query_by_actions.assert_not_called()

    def test_actions_without_v2_suffix_only_query_once(self):
        client = make_client()
        client._client.policy_query_by_actions.return_value = (
            True,
            "ok",
            [{"action": {"id": "view_collection"}, "condition": {}}],
        )

        client._do_policy_query_by_actions(self.make_request("view_collection"))

        self.assertEqual(client._client.policy_query_by_actions.call_count, 1)

    def test_dropping_resources_queries_all_policies(self):
        client = make_client()
        client._client.policy_query_by_actions.return_value = (True, "ok", [])

        client._do_policy_query_by_actions(self.make_request("view_collection"), with_resources=False)

        self.assertEqual(client._client.policy_query_by_actions.call_args.args[0]["resources"], [])

    def test_v1_condition_fills_in_an_empty_v2_condition(self):
        client = make_client()
        client._client.policy_query_by_actions.side_effect = [
            (True, "ok", [{"action": {"id": "view_collection_v2"}, "condition": {}}]),
            (
                True,
                "ok",
                [{"action": {"id": "view_collection"}, "condition": {"op": "eq", "field": "biz.id", "value": "2"}}],
            ),
        ]

        action_policies = client._do_policy_query_by_actions(self.make_request("view_collection_v2"))

        self.assertEqual(
            client._client.policy_query_by_actions.call_args_list[1].args[0]["actions"], [{"id": "view_collection"}]
        )
        self.assertEqual(action_policies[0]["condition"], {"op": "eq", "field": "space.id", "value": "2"})

    def test_v1_and_v2_conditions_are_combined_with_or(self):
        client = make_client()
        client._client.policy_query_by_actions.side_effect = [
            (
                True,
                "ok",
                [
                    {
                        "action": {"id": "view_collection_v2"},
                        "condition": {"op": "eq", "field": "space.id", "value": "1"},
                    }
                ],
            ),
            (
                True,
                "ok",
                [{"action": {"id": "view_collection"}, "condition": {"op": "eq", "field": "biz.id", "value": "2"}}],
            ),
        ]

        action_policies = client._do_policy_query_by_actions(self.make_request("view_collection_v2"))

        self.assertEqual(
            action_policies[0]["condition"],
            {
                "op": "OR",
                "content": [
                    {"op": "eq", "field": "space.id", "value": "1"},
                    {"op": "eq", "field": "space.id", "value": "2"},
                ],
            },
        )

    def test_empty_v1_condition_does_not_overwrite_the_v2_condition(self):
        client = make_client()
        client._client.policy_query_by_actions.side_effect = [
            (
                True,
                "ok",
                [
                    {
                        "action": {"id": "view_collection_v2"},
                        "condition": {"op": "eq", "field": "space.id", "value": "1"},
                    }
                ],
            ),
            (True, "ok", [{"action": {"id": "view_collection"}, "condition": {}}]),
        ]

        action_policies = client._do_policy_query_by_actions(self.make_request("view_collection_v2"))

        self.assertEqual(action_policies[0]["condition"], {"op": "eq", "field": "space.id", "value": "1"})

    def test_v1_condition_is_only_merged_into_the_matching_action(self):
        client = make_client()
        client._client.policy_query_by_actions.side_effect = [
            (
                True,
                "ok",
                [
                    {"action": {"id": "view_index_set_v2"}, "condition": {}},
                    {"action": {"id": "view_collection_v2"}, "condition": {}},
                ],
            ),
            (
                True,
                "ok",
                [{"action": {"id": "view_collection"}, "condition": {"op": "eq", "field": "biz.id", "value": "2"}}],
            ),
        ]

        action_policies = client._do_policy_query_by_actions(
            self.make_request("view_index_set_v2", "view_collection_v2")
        )

        self.assertEqual(action_policies[0]["condition"], {})
        self.assertEqual(action_policies[1]["condition"], {"op": "eq", "field": "space.id", "value": "2"})

    def test_failed_query_raises(self):
        client = make_client()
        client._client.policy_query_by_actions.return_value = (False, "iam unavailable", [])

        with self.assertRaises(AuthAPIError):
            client._do_policy_query_by_actions(self.make_request("view_collection"))


class BuildV3ClientTest(SimpleTestCase):
    @override_settings(
        APP_CODE="bk_log_search",
        SECRET_KEY="secret",
        BK_IAM_APIGATEWAY_URL="https://iam.example/api",
        BK_IAM_SYSTEM_ID="bk_log_search",
    )
    def test_client_is_built_from_settings_for_the_given_tenant(self):
        client = build_v3_client("tenant-1")

        self.assertIsInstance(client, CompatibleIAM)
        self.assertEqual(client._client._app_code, "bk_log_search")
        self.assertEqual(client._client._bk_tenant_id, "tenant-1")

    def test_upgrade_command_resolves_the_client_from_the_v3_backend(self):
        from apps.iam.management.commands import iam_upgrade_action_v2

        self.assertIs(iam_upgrade_action_v2.CompatibleIAM, CompatibleIAM)
