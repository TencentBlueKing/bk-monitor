"""Small, dependency-free JSON-schema subset used by opt-in Resource handlers.

The existing Resource Call protocol predates strict parameter validation.  New
Agent-facing handlers opt in through ``validate_params=True`` while legacy
handlers keep their historical behavior.  Only the schema keywords used by the
registry are implemented here; unsupported keywords fail closed when reached.
"""

from __future__ import annotations

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


def validate_params(params: Any, schema: dict[str, Any], path: str = "params") -> None:
    """Validate a value against the registry's supported JSON-schema subset."""

    if not isinstance(schema, dict):
        raise ValidationError(f"invalid server schema at {path}")

    if "anyOf" in schema:
        errors = []
        for option in schema["anyOf"]:
            try:
                validate_params(params, option, path)
                return
            except ValidationError as error:
                errors.append(error.message)
        raise ValidationError(f"{path} does not match any allowed schema: {'; '.join(errors)}")

    expected_type = schema.get("type")
    if expected_type:
        allowed_types = [expected_type] if isinstance(expected_type, str) else list(expected_type)
        if not any(TYPE_CHECKERS.get(item, lambda _value: False)(params) for item in allowed_types):
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
        missing = [name for name in required if name not in params]
        if missing:
            raise ValidationError(f"{path} is missing required fields: {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(params) - set(properties))
            if unknown:
                raise ValidationError(f"{path} contains unsupported fields: {', '.join(unknown)}")
        for name, value in params.items():
            if name in properties:
                validate_params(value, properties[name], f"{path}.{name}")

    if isinstance(params, list):
        if "minItems" in schema and len(params) < schema["minItems"]:
            raise ValidationError(f"{path} must contain at least {schema['minItems']} items")
        if "maxItems" in schema and len(params) > schema["maxItems"]:
            raise ValidationError(f"{path} must contain at most {schema['maxItems']} items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(params):
                validate_params(item, item_schema, f"{path}[{index}]")

    if isinstance(params, str):
        if "minLength" in schema and len(params) < schema["minLength"]:
            raise ValidationError(f"{path} must contain at least {schema['minLength']} characters")
        if "maxLength" in schema and len(params) > schema["maxLength"]:
            raise ValidationError(f"{path} must contain at most {schema['maxLength']} characters")

    if isinstance(params, int | float) and not isinstance(params, bool):
        if "minimum" in schema and params < schema["minimum"]:
            raise ValidationError(f"{path} must be greater than or equal to {schema['minimum']}")
        if "maximum" in schema and params > schema["maximum"]:
            raise ValidationError(f"{path} must be less than or equal to {schema['maximum']}")
