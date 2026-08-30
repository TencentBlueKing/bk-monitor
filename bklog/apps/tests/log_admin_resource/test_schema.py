from django.test import SimpleTestCase

from apps.exceptions import ValidationError
from apps.log_admin_resource.registry import FUNCTIONS
from apps.log_admin_resource.schema import validate_params


LEGACY_FUNCTIONS = {
    "bklog.collector.list",
    "bklog.collector.detail",
    "bklog.collector.storage.preview",
    "bklog.collector.storage.snapshot",
    "bklog.collector.storage.apply",
    "bklog.storage_cluster.list",
    "bklog.index_set.list",
    "bklog.index_set.detail",
    "bklog.clustering_config.list",
    "bklog.clustering_config.detail",
    "bklog.clustering_config.access_pipeline",
    "bklog.clustering_config.pipeline.retry",
    "bklog.clustering_config.pipeline.skip",
    "bklog.clustering_config.pipeline.force_fail",
    "bklog.bkdata.raw.snapshot",
    "bklog.bkdata.clean.snapshot",
    "bklog.bkdata.flow.snapshot",
    "bklog.bkdata.result_table.snapshot_batch",
}


class ResourceSchemaValidationTest(SimpleTestCase):
    def assert_invalid(self, value, schema, message):
        with self.assertRaisesRegex(ValidationError, message):
            validate_params(value, schema)

    def test_rejects_invalid_server_schema_and_unknown_type(self):
        self.assert_invalid({}, [], "invalid server schema")
        self.assert_invalid("value", {"type": "unsupported"}, "must be of type unsupported")

    def test_any_of_accepts_first_match_and_reports_all_failures(self):
        validate_params("value", {"anyOf": [{"type": "string"}, {"type": "integer"}]})
        self.assert_invalid(
            True,
            {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            "does not match any allowed schema",
        )

    def test_const_enum_and_not(self):
        validate_params("ready", {"const": "ready", "enum": ["ready", "failed"], "not": {"const": "failed"}})
        self.assert_invalid("failed", {"const": "ready"}, "must equal 'ready'")
        self.assert_invalid("unknown", {"enum": ["ready", "failed"]}, "must be one of")
        self.assert_invalid("blocked", {"not": {"const": "blocked"}}, "matches a forbidden value")

    def test_object_required_additional_properties_and_nested_validation(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string", "minLength": 2}},
            "required": ["name"],
            "additionalProperties": False,
        }
        validate_params({"name": "ok"}, schema)
        self.assert_invalid({}, schema, "missing required fields: name")
        self.assert_invalid({"name": "ok", "extra": 1}, schema, "contains unsupported fields: extra")
        self.assert_invalid({"name": "x"}, schema, "params.name must contain at least 2 characters")
        validate_params({"free": "value"}, {"type": "object"})

    def test_array_bounds_and_items(self):
        schema = {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "integer"}}
        validate_params([1, 2], schema)
        self.assert_invalid([], schema, "must contain at least 1 items")
        self.assert_invalid([1, 2, 3], schema, "must contain at most 2 items")
        self.assert_invalid([1, "2"], schema, r"params\[1\] must be of type integer")
        validate_params(["unconstrained"], {"type": "array"})

    def test_string_length_bounds(self):
        schema = {"type": "string", "minLength": 2, "maxLength": 3}
        validate_params("ab", schema)
        self.assert_invalid("a", schema, "must contain at least 2 characters")
        self.assert_invalid("abcd", schema, "must contain at most 3 characters")

    def test_numeric_bounds_and_bool_is_not_numeric(self):
        schema = {"type": ["integer", "number"], "minimum": 1, "maximum": 2}
        validate_params(1, schema)
        validate_params(1.5, schema)
        self.assert_invalid(True, schema, "must be of type integer or number")
        self.assert_invalid(0, schema, "must be greater than or equal to 1")
        self.assert_invalid(3, schema, "must be less than or equal to 2")

    def test_boolean_and_null_types(self):
        validate_params(False, {"type": "boolean"})
        validate_params(None, {"type": "null"})

    def test_strict_resource_handlers_expose_field_level_response_contracts(self):
        strict_functions = {name: function for name, function in FUNCTIONS.items() if function.get("validate_params")}

        self.assertTrue(strict_functions)
        for name, function in strict_functions.items():
            with self.subTest(func_name=name):
                response_schema = function.get("response_schema")
                self.assertIsInstance(response_schema, dict)
                self.assertNotEqual(response_schema, {"type": "object"})
                self.assertTrue(response_schema.get("required") or response_schema.get("anyOf"))

    def test_every_registered_resource_exposes_request_and_response_schemas(self):
        for name, function in FUNCTIONS.items():
            with self.subTest(func_name=name):
                self.assertIsInstance(function.get("params_schema"), dict)
                self.assertIsInstance(function.get("response_schema"), dict)

    def test_legacy_resource_schemas_remain_discovery_only(self):
        self.assertTrue(LEGACY_FUNCTIONS.issubset(FUNCTIONS))
        for name in LEGACY_FUNCTIONS:
            with self.subTest(func_name=name):
                self.assertFalse(FUNCTIONS[name].get("validate_params"))
