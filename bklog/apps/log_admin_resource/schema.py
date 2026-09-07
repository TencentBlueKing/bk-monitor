"""Small, dependency-free JSON-schema subset used by opt-in Resource handlers.

The existing Resource Call protocol predates strict parameter validation.  New
Agent-facing handlers opt in through ``validate_params=True`` while legacy
handlers keep their historical behavior.  Only the schema keywords used by the
registry are implemented here; unsupported keywords fail closed when reached.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from apps.exceptions import ValidationError


TYPE_CHECKERS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, int | float) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}
SUPPORTED_KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "minProperties",
    "maxProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "const",
    "enum",
    "anyOf",
    "oneOf",
    "not",
    "format",
    # Annotation-only JSON Schema keywords used by registry metadata.
    "default",
    "description",
    "examples",
    "title",
    "deprecated",
}


def validate_params(params: Any, schema: dict[str, Any], path: str = "params") -> None:
    """Validate a value against the registry's supported JSON-schema subset."""

    if not isinstance(schema, dict):
        raise ValidationError(f"invalid server schema at {path}")
    unsupported = sorted(set(schema) - SUPPORTED_KEYWORDS)
    if unsupported:
        raise ValidationError(f"unsupported server schema keywords at {path}: {', '.join(unsupported)}")

    if "anyOf" in schema:
        errors = []
        matched = False
        for option in schema["anyOf"]:
            try:
                validate_params(params, option, path)
            except ValidationError as error:
                errors.append(error.message)
            else:
                matched = True
                break
        if not matched:
            raise ValidationError(f"{path} does not match any allowed schema: {'; '.join(errors)}")

    if "oneOf" in schema:
        matches = 0
        for option in schema["oneOf"]:
            try:
                validate_params(params, option, path)
            except ValidationError:
                continue
            matches += 1
        if matches != 1:
            raise ValidationError(f"{path} must match exactly one allowed schema")

    expected_type = schema.get("type")
    if expected_type:
        allowed_types = [expected_type] if isinstance(expected_type, str) else list(expected_type)
        unsupported_types = [item for item in allowed_types if item not in TYPE_CHECKERS]
        if unsupported_types:
            raise ValidationError(f"invalid server schema types at {path}: {', '.join(unsupported_types)}")
        if not any(TYPE_CHECKERS[item](params) for item in allowed_types):
            raise ValidationError(f"{path} must be of type {' or '.join(allowed_types)}")

    if "const" in schema and params != schema["const"]:
        raise ValidationError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and params not in schema["enum"]:
        raise ValidationError(f"{path} must be one of {schema['enum']!r}")
    if "not" in schema:
        try:
            validate_params(params, schema["not"], path)
        except ValidationError:
            pass
        else:
            raise ValidationError(f"{path} matches a forbidden value")

    if isinstance(params, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if "minProperties" in schema and len(params) < schema["minProperties"]:
            raise ValidationError(f"{path} must contain at least {schema['minProperties']} properties")
        if "maxProperties" in schema and len(params) > schema["maxProperties"]:
            raise ValidationError(f"{path} must contain at most {schema['maxProperties']} properties")
        missing = [name for name in required if name not in params]
        if missing:
            raise ValidationError(f"{path} is missing required fields: {', '.join(missing)}")
        additional_properties = schema.get("additionalProperties", True)
        unknown = sorted(set(params) - set(properties))
        if additional_properties is False:
            if unknown:
                raise ValidationError(f"{path} contains unsupported fields: {', '.join(unknown)}")
        for name, value in params.items():
            if name in properties:
                validate_params(value, properties[name], f"{path}.{name}")
            elif isinstance(additional_properties, dict):
                validate_params(value, additional_properties, f"{path}.{name}")

    if isinstance(params, list):
        if "minItems" in schema and len(params) < schema["minItems"]:
            raise ValidationError(f"{path} must contain at least {schema['minItems']} items")
        if "maxItems" in schema and len(params) > schema["maxItems"]:
            raise ValidationError(f"{path} must contain at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            encoded_items = [json.dumps(item, sort_keys=True, ensure_ascii=False, default=str) for item in params]
            if len(set(encoded_items)) != len(encoded_items):
                raise ValidationError(f"{path} must contain unique items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(params):
                validate_params(item, item_schema, f"{path}[{index}]")

    if isinstance(params, str):
        if "minLength" in schema and len(params) < schema["minLength"]:
            raise ValidationError(f"{path} must contain at least {schema['minLength']} characters")
        if "maxLength" in schema and len(params) > schema["maxLength"]:
            raise ValidationError(f"{path} must contain at most {schema['maxLength']} characters")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(params.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValidationError(f"{path} must be a valid date-time") from error
        elif schema.get("format"):
            raise ValidationError(f"unsupported server schema format at {path}: {schema['format']}")

    if isinstance(params, int | float) and not isinstance(params, bool):
        if "minimum" in schema and params < schema["minimum"]:
            raise ValidationError(f"{path} must be greater than or equal to {schema['minimum']}")
        if "maximum" in schema and params > schema["maximum"]:
            raise ValidationError(f"{path} must be less than or equal to {schema['maximum']}")
