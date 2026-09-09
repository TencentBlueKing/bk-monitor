import copy
import json
import os
import tempfile

from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.backends.v4.model_definition import (
    ACTIONS_NOT_REGISTERED_IN_V4,
    ModelDefinitionError,
    build_model_definition,
    load_model_definition,
    load_model_payload,
    resolve_callback_url,
    resolve_model_managers,
)
from apps.iam.handlers.actions import ActionEnum, ActionMeta

MINIMAL_PAYLOAD = {
    "version": 1,
    "system": {"name": "日志平台", "description": "desc", "clients": ["bk_log_search"]},
    "resource_types": [
        {"id": "space", "name": "空间", "ancestors": []},
        {"id": "indices", "name": "索引集", "ancestors": ["space"]},
    ],
    "actions": [
        {"id": "view_business", "name": "业务访问", "resource_type_id": "space"},
        {"id": "search_log", "name": "日志检索", "resource_type_id": "indices"},
        {"id": "manage_global_desensitize_rule", "name": "全局脱敏规则管理", "resource_type_id": ""},
    ],
    "roles": [
        {
            "id": "space_viewer",
            "name": "业务只读",
            "description": "只读",
            "actions": [
                {"id": "view_business", "resource_type_id": "space"},
                {"id": "search_log", "resource_type_id": "indices"},
            ],
        }
    ],
}


def build(payload=None, **kwargs):
    kwargs.setdefault("system_id", "bk_log_search")
    kwargs.setdefault("callback_url", "https://bklog.example/api/v1/iam/v4/resource/")
    return build_model_definition(payload if payload is not None else copy.deepcopy(MINIMAL_PAYLOAD), **kwargs)


class V4ModelDefinitionBuildTest(SimpleTestCase):
    def test_minimal_payload_builds_expected_model(self):
        model = build()

        self.assertEqual(model.version, 1)
        self.assertEqual(model.system.id, "bk_log_search")
        self.assertEqual(model.resource_type_ids(), ("space", "indices"))
        self.assertEqual(
            model.action_ids(),
            ("view_business", "search_log", "manage_global_desensitize_rule"),
        )
        self.assertEqual(model.role_ids(), ("space_viewer",))

    def test_extra_clients_are_appended_and_deduplicated(self):
        model = build(extra_clients=["bk_log_search", "bk_bklog", " "])

        self.assertEqual(model.system.clients, ("bk_log_search", "bk_bklog"))

    def test_managers_default_to_unmanaged(self):
        self.assertIsNone(build().system.managers)

    def test_managers_are_deduplicated_when_provided(self):
        model = build(managers=["colecai", "colecai", "jayjhwu"])

        self.assertEqual(model.system.managers, ("colecai", "jayjhwu"))

    def test_role_may_grant_action_at_ancestor_dimension(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"][1]["resource_type_id"] = "space"

        model = build(payload)

        self.assertEqual(model.roles[0].actions[1].resource_type_id, "space")

    def test_resource_free_action_can_be_granted_with_empty_dimension(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"].append({"id": "manage_global_desensitize_rule", "resource_type_id": ""})

        model = build(payload)

        self.assertEqual(model.roles[0].actions[-1].resource_type_id, "")


class V4ModelDefinitionValidationTest(SimpleTestCase):
    def assert_invalid(self, payload, message, **kwargs):
        with self.assertRaisesRegex(ModelDefinitionError, message):
            build(payload, **kwargs)

    def test_version_must_be_positive_integer(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["version"] = 0
        self.assert_invalid(payload, "positive integer version")

    def test_system_id_must_match_iam_naming_rule(self):
        self.assert_invalid(None, "invalid system id", system_id="BK_LOG")

    def test_callback_url_must_not_be_empty(self):
        self.assert_invalid(None, "non-empty callback_url", callback_url="  ")

    def test_system_requires_at_least_one_client(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["system"]["clients"] = []
        self.assert_invalid(payload, "at least one client")

    def test_resource_type_id_must_match_iam_naming_rule(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][0]["id"] = "Space"
        self.assert_invalid(payload, "invalid resource_type id")

    def test_duplicate_resource_type_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"].append({"id": "space", "name": "空间", "ancestors": []})
        self.assert_invalid(payload, "duplicate resource_type id")

    def test_unknown_ancestor_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][1]["ancestors"] = ["cluster"]
        self.assert_invalid(payload, "unknown ancestors")

    def test_self_ancestor_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][1]["ancestors"] = ["indices"]
        self.assert_invalid(payload, "its own ancestor")

    def test_duplicate_ancestor_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][1]["ancestors"] = ["space", "space"]
        self.assert_invalid(payload, "duplicate ancestors")

    def test_action_with_unknown_resource_type_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["actions"][0]["resource_type_id"] = "cluster"
        self.assert_invalid(payload, "unknown resource_type")

    def test_duplicate_action_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["actions"].append({"id": "view_business", "name": "业务访问", "resource_type_id": "space"})
        self.assert_invalid(payload, "duplicate action id")

    def test_role_with_unknown_action_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"][0]["id"] = "view_dashboard"
        self.assert_invalid(payload, "unknown action")

    def test_role_without_action_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"] = []
        self.assert_invalid(payload, "at least one action")

    def test_role_with_duplicate_action_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"].append({"id": "view_business", "resource_type_id": "space"})
        self.assert_invalid(payload, "duplicate action")

    def test_role_cannot_grant_action_at_unrelated_dimension(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"][0]["resource_type_id"] = "indices"
        self.assert_invalid(payload, "neither its resource_type nor an ancestor")

    def test_role_cannot_grant_resource_action_without_dimension(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"][0]["resource_type_id"] = ""
        self.assert_invalid(payload, "must grant action view_business on a resource_type")

    def test_role_cannot_grant_resource_free_action_with_dimension(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"].append(
            {"id": "manage_global_desensitize_rule", "resource_type_id": "space"},
        )
        self.assert_invalid(payload, "with an empty resource_type_id")

    def test_role_cannot_grant_same_resource_type_at_two_dimensions(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["actions"].append({"id": "manage_indices", "name": "索引集管理", "resource_type_id": "indices"})
        payload["roles"][0]["actions"].append({"id": "manage_indices", "resource_type_id": "space"})
        self.assert_invalid(payload, "inconsistent dimensions")

    def test_duplicate_role_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"].append(copy.deepcopy(payload["roles"][0]))
        self.assert_invalid(payload, "duplicate role id")

    def test_ancestor_cycle_is_rejected(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][0]["ancestors"] = ["indices"]
        self.assert_invalid(payload, "form a cycle")

    def test_system_must_be_an_object(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["system"] = []
        self.assert_invalid(payload, "requires a system object")

    def test_resource_types_must_be_a_list(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"] = {}
        self.assert_invalid(payload, "resource_types must be a list")

    def test_resource_type_entry_must_be_an_object(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"].append("space")
        self.assert_invalid(payload, r"resource_types\[2\] must be an object")

    def test_action_entry_must_be_an_object(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["actions"].append("view_business")
        self.assert_invalid(payload, r"actions\[3\] must be an object")

    def test_role_entry_must_be_an_object(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"].append("space_viewer")
        self.assert_invalid(payload, r"roles\[1\] must be an object")

    def test_role_action_entry_must_be_an_object(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["roles"][0]["actions"].append("view_business")
        self.assert_invalid(payload, r"roles\[space_viewer\].actions\[2\] must be an object")

    def test_name_must_not_be_blank(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["resource_types"][0]["name"] = "  "
        self.assert_invalid(payload, "requires a non-empty name")

    def test_client_entry_must_not_be_blank(self):
        payload = copy.deepcopy(MINIMAL_PAYLOAD)
        payload["system"]["clients"] = ["bk_log_search", ""]
        self.assert_invalid(payload, r"system.clients\[1\] must be a non-empty string")


@override_settings(
    APP_CODE="bk_log_search",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_IAM_V4_SYSTEM_ID="",
    BK_IAM_RESOURCE_API_HOST="https://bklog.example/o/bk_log_search/",
)
class V4ModelDefinitionSettingsTest(SimpleTestCase):
    def test_callback_url_is_derived_with_v4_specific_path(self):
        self.assertEqual(
            resolve_callback_url(),
            "https://bklog.example/o/bk_log_search/api/v1/iam/v4/resource/",
        )

    def test_explicit_callback_url_wins(self):
        with self.settings(BK_IAM_V4_CALLBACK_URL="https://custom.example/callback/"):
            self.assertEqual(resolve_callback_url(), "https://custom.example/callback/")

    def test_missing_callback_host_is_reported(self):
        with self.settings(BK_IAM_V4_CALLBACK_URL="", BK_IAM_RESOURCE_API_HOST=""):
            with self.assertRaisesRegex(ModelDefinitionError, "BK_IAM_RESOURCE_API_HOST"):
                resolve_callback_url()

    def test_managers_are_parsed_from_comma_separated_setting(self):
        with self.settings(BK_IAM_V4_MODEL_MANAGERS="colecai, jayjhwu ,colecai"):
            self.assertEqual(resolve_model_managers(), ("colecai", "jayjhwu"))

    def test_managers_are_unmanaged_when_setting_is_blank(self):
        with self.settings(BK_IAM_V4_MODEL_MANAGERS="  , "):
            self.assertIsNone(resolve_model_managers())

    def test_managers_are_unmanaged_when_setting_is_none(self):
        with self.settings(BK_IAM_V4_MODEL_MANAGERS=None):
            self.assertIsNone(resolve_model_managers())

    def test_managers_accept_a_sequence_setting(self):
        with self.settings(BK_IAM_V4_MODEL_MANAGERS=["colecai", " jayjhwu "]):
            self.assertEqual(resolve_model_managers(), ("colecai", "jayjhwu"))

    def test_managers_reject_unsupported_setting_type(self):
        with self.settings(BK_IAM_V4_MODEL_MANAGERS=42):
            with self.assertRaisesRegex(ModelDefinitionError, "invalid BK_IAM_V4_MODEL_MANAGERS"):
                resolve_model_managers()

    def test_load_model_definition_uses_effective_v4_system_id(self):
        with self.settings(BK_IAM_V4_SYSTEM_ID="bklog_test"):
            model = load_model_definition()

        self.assertEqual(model.system.id, "bklog_test")

    def test_load_model_definition_injects_callback_and_clients(self):
        model = load_model_definition()

        self.assertEqual(
            model.system.callback_url,
            "https://bklog.example/o/bk_log_search/api/v1/iam/v4/resource/",
        )
        self.assertIn("bk_log_search", model.system.clients)


class V4ModelPayloadFileTest(SimpleTestCase):
    def setUp(self):
        self.model_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.model_dir.cleanup)

    def write(self, content):
        file_path = os.path.join(self.model_dir.name, "0001_initial.json")
        with open(file_path, "w", encoding="utf-8") as model_file:
            model_file.write(content)

    def load(self):
        with self.settings(BK_IAM_V4_MODEL_DIR=self.model_dir.name):
            return load_model_payload()

    def test_missing_file_is_reported(self):
        with self.assertRaisesRegex(ModelDefinitionError, "baseline not found"):
            self.load()

    def test_malformed_json_is_reported(self):
        self.write("{not json")

        with self.assertRaisesRegex(ModelDefinitionError, "not valid JSON"):
            self.load()

    def test_non_object_json_is_reported(self):
        self.write("[]")

        with self.assertRaisesRegex(ModelDefinitionError, "must be a JSON object"):
            self.load()

    def test_valid_file_is_loaded_from_overridden_dir(self):
        self.write(json.dumps(MINIMAL_PAYLOAD))

        self.assertEqual(self.load()["version"], 1)


class V4ModelBaselineTest(SimpleTestCase):
    """守住仓库基线文件与运行时 Action 定义的一致性。"""

    def setUp(self):
        self.payload = load_model_payload()
        self.model = build(self.payload)

    def test_baseline_file_is_valid(self):
        self.assertEqual(self.model.resource_type_ids(), ("space", "indices", "collection", "es_source"))
        self.assertEqual(self.model.role_ids(), ("space_operator", "space_viewer", "system_admin"))

    def test_baseline_does_not_pin_environment_specific_fields(self):
        # system_id / callback_url / managers 必须由 settings 注入，否则 test 与 prod 又会分叉成两份文件。
        self.assertNotIn("id", self.payload["system"])
        self.assertNotIn("callback_url", self.payload["system"])
        self.assertNotIn("managers", self.payload["system"])

    def test_baseline_actions_match_action_enum(self):
        codec = BklogNameCodec()
        runtime_action_ids = {
            codec.encode_action(action.id) for action in vars(ActionEnum).values() if isinstance(action, ActionMeta)
        }

        self.assertEqual(
            set(self.model.action_ids()),
            runtime_action_ids - ACTIONS_NOT_REGISTERED_IN_V4,
        )

    def test_actions_excluded_from_v4_are_known_action_enum_members(self):
        codec = BklogNameCodec()
        runtime_action_ids = {
            codec.encode_action(action.id) for action in vars(ActionEnum).values() if isinstance(action, ActionMeta)
        }

        self.assertTrue(ACTIONS_NOT_REGISTERED_IN_V4 <= runtime_action_ids)

    def test_creator_grant_roles_exist_in_baseline(self):
        from apps.iam.backends.v4.writer import CREATOR_ROLE_BY_RESOURCE_TYPE

        self.assertTrue(set(CREATOR_ROLE_BY_RESOURCE_TYPE.values()) <= set(self.model.role_ids()))
        self.assertTrue(set(CREATOR_ROLE_BY_RESOURCE_TYPE) <= set(self.model.resource_type_ids()))
