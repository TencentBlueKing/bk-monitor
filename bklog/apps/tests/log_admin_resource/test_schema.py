from django.test import SimpleTestCase

from apps.exceptions import ValidationError
from apps.log_admin_resource.schema import validate_params


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
