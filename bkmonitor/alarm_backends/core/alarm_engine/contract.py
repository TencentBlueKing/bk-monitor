"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import copy
import hashlib
import json
import math
import re
import struct
from collections.abc import Mapping
from typing import Any


SCHEMA_MAJOR = 1
SCHEMA_MINOR = 0
DETECTION_OUTCOME_SCHEMA = "detection-outcome"
TRIGGER_STRATEGY_IR_SCHEMA = "trigger-strategy-ir"

FEATURE_FULL_LEVEL_EVALUATIONS = "full-level-evaluations-v1"
FEATURE_RAW_JSON = "raw-json-v1"
FEATURE_RAW_STRATEGY_BYTES = "raw-strategy-bytes-v1"
PURPOSES = {"DETECT", "NODATA"}
EVALUATION_RESULTS = {"NORMAL", "ANOMALOUS"}
OUTCOMES = {"NORMAL", "ANOMALOUS", "ERROR", "UNSUPPORTED"}
ERROR_CODES = {
    "ERROR": {"ALGORITHM_ERROR", "INTERNAL_ERROR", "INVALID_INPUT"},
    "UNSUPPORTED": {"UNSUPPORTED_FEATURE", "UNSUPPORTED_STRATEGY"},
}

_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_RECORD_ID_RE = re.compile(r"(?P<dimensions_md5>[0-9a-f]{32})\.(?P<source_time>0|[1-9][0-9]*)\Z")
_MAX_INT64 = 2**63 - 1
_MAX_CONTRACT_INT = 2**31 - 1


class ContractValidationError(ValueError):
    """Raised when a contract document cannot be interpreted safely."""


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json(value: str) -> None:
    raise ContractValidationError(f"non-finite JSON number: {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ContractValidationError(f"non-finite JSON number: {value}")
    return parsed


def _decode_strict_json_object(payload: bytes, field: str) -> dict:
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ContractValidationError(f"{field} must not contain a UTF-8 BOM")
    try:
        decoded = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_nonfinite_json,
            parse_float=_parse_finite_float,
        )
    except ContractValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"{field} must contain valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise ContractValidationError(f"{field} must contain a JSON object")
    _validate_json_strings(decoded, field)
    return decoded


def _validate_json_strings(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_utf8_string(key, f"{field} object key")
            _validate_json_strings(child, field)
    elif isinstance(value, list):
        for child in value:
            _validate_json_strings(child, field)
    elif isinstance(value, str):
        _validate_utf8_string(value, field)


def _validate_utf8_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field} must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractValidationError(f"{field} must contain valid UTF-8") from exc
    return value


def _require_mapping(value: Any, field: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field} must be an object")
    return value


def _validate_fixed_fields(
    value: Any,
    field: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
    schema_minor: int = SCHEMA_MINOR,
    allow_open: bool = False,
) -> Mapping:
    value = _require_mapping(value, field)
    optional = optional or set()
    known = required | optional
    if any(not isinstance(key, str) for key in value):
        raise ContractValidationError(f"{field} field names must be strings")
    missing = required - set(value)
    if missing:
        raise ContractValidationError(f"{field} missing required field: {sorted(missing)[0]}")
    known_casefold = {key.casefold(): key for key in known}
    unknown = set(value) - known
    for key in unknown:
        canonical = known_casefold.get(key.casefold())
        if canonical is not None:
            raise ContractValidationError(f"{field}.{key} case-collides with field {canonical}")
    if unknown and not allow_open and schema_minor <= SCHEMA_MINOR:
        raise ContractValidationError(f"{field} contains unknown field: {sorted(unknown)[0]}")
    return value


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractValidationError(f"{field} must be a non-empty string")
    return _validate_utf8_string(value, field)


def _canonical_decimal(value: Any, field: str) -> str:
    if isinstance(value, bool):
        raise ContractValidationError(f"{field} must use canonical decimal form")
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str) or not _DECIMAL_RE.fullmatch(value):
        raise ContractValidationError(f"{field} must use canonical decimal form")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0 or value > _MAX_CONTRACT_INT:
        raise ContractValidationError(f"{field} must be a positive 32-bit signed integer")
    return value


def _require_source_time(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > _MAX_INT64:
        raise ContractValidationError(f"{field} must be a non-negative int64")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ContractValidationError(f"{field} must be 64 lowercase hexadecimal characters")
    return value


def _parse_record_id(record_id: Any) -> tuple[str, int]:
    if not isinstance(record_id, str):
        raise ContractValidationError("record_id must be a string")
    matched = _RECORD_ID_RE.fullmatch(record_id)
    if not matched:
        raise ContractValidationError("record_id must use dimensions_md5.source_time canonical form")
    source_time = int(matched.group("source_time"))
    if source_time > _MAX_INT64:
        raise ContractValidationError("record source_time exceeds int64")
    return matched.group("dimensions_md5"), source_time


def _validate_header(document: Mapping, *, name: str, required_features: set[str]) -> int:
    schema = _require_mapping(document.get("schema"), "schema")
    if schema.get("name") != name:
        raise ContractValidationError(f"schema.name must be {name}")
    major = schema.get("major")
    if isinstance(major, bool) or not isinstance(major, int) or major != SCHEMA_MAJOR:
        raise ContractValidationError(f"unsupported {name} schema major")
    minor = schema.get("minor")
    if isinstance(minor, bool) or not isinstance(minor, int) or minor < 0 or minor > _MAX_CONTRACT_INT:
        raise ContractValidationError("schema.minor must be a non-negative 32-bit signed integer")
    _validate_fixed_fields(
        schema,
        "schema",
        required={"name", "major", "minor"},
        schema_minor=minor,
    )

    features = document.get("required_features")
    if not isinstance(features, list) or any(not isinstance(feature, str) for feature in features):
        raise ContractValidationError("required_features must be a string array")
    if len(features) != len(set(features)):
        raise ContractValidationError("required_features contains duplicate values")
    unknown_features = set(features) - required_features
    if unknown_features:
        raise ContractValidationError(f"unsupported required feature: {sorted(unknown_features)[0]}")
    if not required_features.issubset(features):
        raise ContractValidationError(f"missing required feature: {sorted(required_features - set(features))[0]}")
    return minor


def _normalize_purpose(value: Any) -> str:
    if not isinstance(value, str) or value not in PURPOSES:
        raise ContractValidationError(f"unsupported purpose: {value}")
    return value


def _json_values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (
            isinstance(left, Mapping)
            and isinstance(right, Mapping)
            and left.keys() == right.keys()
            and all(_json_values_equal(left[key], right[key]) for key in left)
        )
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_values_equal(left_value, right_value) for left_value, right_value in zip(left, right))
        )
    return type(left) is type(right) and left == right


def json_values_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without Python's bool/int or int/float coercion."""
    return _json_values_equal(left, right)


def _normalize_strategy_ref(strategy_ref: Any, *, schema_minor: int = SCHEMA_MINOR) -> dict[str, str]:
    strategy_ref = _validate_fixed_fields(
        strategy_ref,
        "strategy_ref",
        required={"strategy_id", "item_id", "generation", "content_sha256"},
        schema_minor=schema_minor,
    )
    return {
        "strategy_id": _canonical_decimal(strategy_ref.get("strategy_id"), "strategy_ref.strategy_id"),
        "item_id": _canonical_decimal(strategy_ref.get("item_id"), "strategy_ref.item_id"),
        "generation": _require_nonempty_string(strategy_ref.get("generation"), "strategy_ref.generation"),
        "content_sha256": _require_sha256(strategy_ref.get("content_sha256"), "strategy_ref.content_sha256"),
    }


def derive_input_id(
    *,
    tenant_id: str,
    purpose: str,
    strategy_id: str | int,
    item_id: str | int,
    strategy_content_sha256: str,
    record_id: str,
) -> str:
    """Derive the v1 replay-stable input ID from its frozen canonical tuple."""

    fields = (
        _require_nonempty_string(tenant_id, "tenant_id"),
        _normalize_purpose(purpose),
        _canonical_decimal(strategy_id, "strategy_id"),
        _canonical_decimal(item_id, "item_id"),
        _require_sha256(strategy_content_sha256, "strategy_content_sha256"),
        record_id,
    )
    _parse_record_id(record_id)

    digest = hashlib.sha256()
    for field in fields:
        try:
            encoded = field.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ContractValidationError("input_id canonical fields must contain valid UTF-8") from exc
        if len(encoded) > 2**32 - 1:
            raise ContractValidationError("input_id canonical field exceeds uint32 length")
        digest.update(struct.pack(">I", len(encoded)))
        digest.update(encoded)
    return digest.hexdigest()


def build_trigger_strategy_ir(
    *,
    tenant_id: str,
    purpose: str,
    strategy_id: str | int,
    item_id: str | int,
    generation: str,
    legacy_json: bytes,
    check_window_unit_seconds: int,
    trigger_configs: Mapping[int | str, Mapping[str, int]],
) -> dict:
    """Build the minimal immutable StrategyIR needed by Trigger v1."""

    if not isinstance(legacy_json, bytes) or not legacy_json:
        raise ContractValidationError("legacy_json must be non-empty bytes")
    _decode_strict_json_object(legacy_json, "legacy_json")
    trigger_configs = _require_mapping(trigger_configs, "trigger_configs")

    normalized_configs = []
    seen_levels = set()
    for raw_level, raw_config in trigger_configs.items():
        level = int(_canonical_decimal(raw_level, "trigger_configs.level"))
        if level <= 0:
            raise ContractValidationError("trigger_configs.level must be positive")
        if level in seen_levels:
            raise ContractValidationError("trigger_configs contains duplicate level")
        seen_levels.add(level)
        config = _require_mapping(raw_config, f"trigger_configs[{level}]")
        normalized_configs.append(
            {
                "level": level,
                "check_window_size": _require_positive_int(
                    config.get("check_window_size"), f"trigger_configs[{level}].check_window_size"
                ),
                "trigger_count": _require_positive_int(
                    config.get("trigger_count"), f"trigger_configs[{level}].trigger_count"
                ),
            }
        )
    if not normalized_configs:
        raise ContractValidationError("trigger_configs must not be empty")
    normalized_configs.sort(key=lambda config: config["level"])

    content_sha256 = hashlib.sha256(legacy_json).hexdigest()
    strategy_ir = {
        "schema": {"name": TRIGGER_STRATEGY_IR_SCHEMA, "major": SCHEMA_MAJOR, "minor": SCHEMA_MINOR},
        "required_features": [FEATURE_RAW_STRATEGY_BYTES],
        "tenant_id": _require_nonempty_string(tenant_id, "tenant_id"),
        "purpose": _normalize_purpose(purpose),
        "strategy_ref": {
            "strategy_id": _canonical_decimal(strategy_id, "strategy_id"),
            "item_id": _canonical_decimal(item_id, "item_id"),
            "generation": _require_nonempty_string(generation, "generation"),
            "content_sha256": content_sha256,
        },
        "required_levels": [config["level"] for config in normalized_configs],
        "check_window_unit_seconds": _require_positive_int(check_window_unit_seconds, "check_window_unit_seconds"),
        "trigger_configs": normalized_configs,
        "legacy_json_b64": base64.b64encode(legacy_json).decode("ascii"),
    }
    validate_trigger_strategy_ir(strategy_ir)
    return strategy_ir


def build_trigger_strategy_ir_from_legacy_config(
    *,
    tenant_id: str,
    purpose: str,
    strategy: Mapping,
    item_id: str | int,
    legacy_json: bytes,
) -> dict:
    """Project an eligible legacy Threshold strategy into the minimal Trigger StrategyIR."""

    strategy = _require_mapping(strategy, "strategy")
    if purpose != "DETECT":
        raise ContractValidationError("unsupported purpose for the first Threshold contract slice")
    if not isinstance(legacy_json, bytes) or not legacy_json:
        raise ContractValidationError("legacy_json must be non-empty bytes")
    decoded_legacy = _decode_strict_json_object(legacy_json, "legacy_json")
    if not _json_values_equal(decoded_legacy, strategy):
        raise ContractValidationError("legacy_json must represent the supplied strategy without semantic drift")

    normalized_item_id = _canonical_decimal(item_id, "item_id")
    items = strategy.get("items")
    if not isinstance(items, list) or not items:
        raise ContractValidationError("unsupported strategy without items")
    item = None
    for strategy_item in items:
        strategy_item = _require_mapping(strategy_item, "strategy item")
        if _canonical_decimal(strategy_item.get("id"), "strategy item id") == normalized_item_id:
            item = strategy_item
            break
    if item is None:
        raise ContractValidationError("unsupported strategy item: item_id not found")
    algorithms = item.get("algorithms")
    if not isinstance(algorithms, list) or not algorithms:
        raise ContractValidationError("unsupported strategy item without algorithms")
    if any(not isinstance(algorithm, Mapping) or algorithm.get("type") != "Threshold" for algorithm in algorithms):
        raise ContractValidationError("unsupported non-Threshold algorithm")
    if _require_mapping(item.get("no_data_config", {}), "no_data_config").get("is_enabled"):
        raise ContractValidationError("unsupported no-data configuration")

    algorithm_levels = {
        _require_positive_int(algorithm.get("level"), "algorithm.level") for algorithm in item["algorithms"]
    }
    trigger_configs = {}
    detects = strategy.get("detects")
    if not isinstance(detects, list):
        raise ContractValidationError("unsupported strategy without detects")
    for detect in detects:
        detect = _require_mapping(detect, "detect")
        level = _require_positive_int(detect.get("level"), "detect.level")
        if level not in algorithm_levels:
            continue
        trigger_config = _require_mapping(detect.get("trigger_config"), f"detect[{level}].trigger_config")
        if trigger_config.get("uptime"):
            raise ContractValidationError("unsupported uptime configuration")
        if level in trigger_configs:
            raise ContractValidationError("unsupported duplicate detect level")
        trigger_configs[level] = {
            "check_window_size": _require_positive_int(
                trigger_config.get("check_window"), f"detect[{level}].trigger_config.check_window"
            ),
            "trigger_count": _require_positive_int(
                trigger_config.get("count"), f"detect[{level}].trigger_config.count"
            ),
        }
    if set(trigger_configs) != algorithm_levels:
        raise ContractValidationError("unsupported strategy with incomplete trigger levels")

    query_configs = item.get("query_configs") or []
    if not isinstance(query_configs, list):
        raise ContractValidationError("query_configs must be an array")
    intervals = [
        _require_positive_int(
            _require_mapping(query_config, "query_config").get("agg_interval", 60),
            "query_config.agg_interval",
        )
        for query_config in query_configs
    ]
    return build_trigger_strategy_ir(
        tenant_id=tenant_id,
        purpose=purpose,
        strategy_id=strategy.get("id"),
        item_id=normalized_item_id,
        generation=_canonical_decimal(strategy.get("update_time"), "strategy.update_time"),
        legacy_json=legacy_json,
        check_window_unit_seconds=min(intervals) if intervals else 60,
        trigger_configs=trigger_configs,
    )


def validate_trigger_strategy_ir(strategy_ir: Mapping) -> None:
    strategy_ir = _require_mapping(strategy_ir, "strategy_ir")
    schema_minor = _validate_header(
        strategy_ir,
        name=TRIGGER_STRATEGY_IR_SCHEMA,
        required_features={FEATURE_RAW_STRATEGY_BYTES},
    )
    _validate_fixed_fields(
        strategy_ir,
        "strategy_ir",
        required={
            "schema",
            "required_features",
            "tenant_id",
            "purpose",
            "strategy_ref",
            "required_levels",
            "check_window_unit_seconds",
            "trigger_configs",
            "legacy_json_b64",
        },
        schema_minor=schema_minor,
    )
    _require_nonempty_string(strategy_ir.get("tenant_id"), "tenant_id")
    _normalize_purpose(strategy_ir.get("purpose"))
    strategy_ref = _normalize_strategy_ref(strategy_ir.get("strategy_ref"), schema_minor=schema_minor)
    _require_positive_int(strategy_ir.get("check_window_unit_seconds"), "check_window_unit_seconds")

    required_levels = strategy_ir.get("required_levels")
    if not isinstance(required_levels, list) or not required_levels:
        raise ContractValidationError("required_levels must be a non-empty array")
    if any(
        isinstance(level, bool) or not isinstance(level, int) or level <= 0 or level > _MAX_CONTRACT_INT
        for level in required_levels
    ):
        raise ContractValidationError("required_levels must contain positive 32-bit signed integers")
    if required_levels != sorted(set(required_levels)):
        raise ContractValidationError("required_levels must be sorted and unique")

    trigger_configs = strategy_ir.get("trigger_configs")
    if not isinstance(trigger_configs, list):
        raise ContractValidationError("trigger_configs must be an array")
    config_levels = []
    for config in trigger_configs:
        config = _validate_fixed_fields(
            config,
            "trigger_configs entry",
            required={"level", "check_window_size", "trigger_count"},
            schema_minor=schema_minor,
        )
        level = _require_positive_int(config.get("level"), "trigger_configs.level")
        _require_positive_int(config.get("check_window_size"), "trigger_configs.check_window_size")
        _require_positive_int(config.get("trigger_count"), "trigger_configs.trigger_count")
        config_levels.append(level)
    if len(config_levels) != len(set(config_levels)):
        raise ContractValidationError("trigger_configs contains duplicate level")
    if config_levels != required_levels:
        raise ContractValidationError("trigger_configs levels must equal required_levels")

    legacy_json_b64 = _require_nonempty_string(strategy_ir.get("legacy_json_b64"), "legacy_json_b64")
    try:
        legacy_json = base64.b64decode(legacy_json_b64, validate=True)
    except ValueError as exc:
        raise ContractValidationError("legacy_json_b64 must contain valid base64-encoded UTF-8 JSON") from exc
    if base64.b64encode(legacy_json).decode("ascii") != legacy_json_b64:
        raise ContractValidationError("legacy_json_b64 must use canonical base64 encoding")
    _decode_strict_json_object(legacy_json, "legacy_json_b64")
    if hashlib.sha256(legacy_json).hexdigest() != strategy_ref["content_sha256"]:
        raise ContractValidationError("legacy strategy content hash mismatch")


def build_detection_outcome(
    *,
    strategy_ir: Mapping,
    batch_id: str,
    data_raw: Mapping,
    evaluations: list[Mapping],
    outcome: str,
    error_code: str | None = None,
) -> dict:
    """Build one record-scoped DetectionOutcome and validate it fail-closed."""

    validate_trigger_strategy_ir(strategy_ir)
    data_raw = _require_mapping(data_raw, "data_raw")
    record_id = data_raw.get("record_id")
    dimensions_md5, source_time = _parse_record_id(record_id)
    if _require_source_time(data_raw.get("time"), "data_raw.time") != source_time:
        raise ContractValidationError("data_raw.time must equal record source_time")

    strategy_ref = _normalize_strategy_ref(strategy_ir.get("strategy_ref"))
    tenant_id = _require_nonempty_string(strategy_ir.get("tenant_id"), "strategy_ir.tenant_id")
    purpose = _normalize_purpose(strategy_ir.get("purpose"))
    document = {
        "schema": {"name": DETECTION_OUTCOME_SCHEMA, "major": SCHEMA_MAJOR, "minor": SCHEMA_MINOR},
        "required_features": [FEATURE_FULL_LEVEL_EVALUATIONS, FEATURE_RAW_JSON],
        "input_id": derive_input_id(
            tenant_id=tenant_id,
            purpose=purpose,
            strategy_id=strategy_ref["strategy_id"],
            item_id=strategy_ref["item_id"],
            strategy_content_sha256=strategy_ref["content_sha256"],
            record_id=record_id,
        ),
        "batch_id": _require_nonempty_string(batch_id, "batch_id"),
        "tenant_id": tenant_id,
        "purpose": purpose,
        "strategy_ref": strategy_ref,
        "record": {
            "record_id": record_id,
            "source_time": source_time,
            "dimensions_md5": dimensions_md5,
            "data_raw": copy.deepcopy(data_raw),
        },
        "evaluations": copy.deepcopy(evaluations),
        "outcome": outcome,
    }
    if error_code is not None:
        document["error_code"] = error_code
    validate_detection_outcome(document, strategy_ir)
    return document


def validate_detection_outcome(document: Mapping, strategy_ir: Mapping) -> None:
    document = _require_mapping(document, "detection_outcome")
    validate_trigger_strategy_ir(strategy_ir)
    schema_minor = _validate_header(
        document,
        name=DETECTION_OUTCOME_SCHEMA,
        required_features={FEATURE_FULL_LEVEL_EVALUATIONS, FEATURE_RAW_JSON},
    )
    _validate_fixed_fields(
        document,
        "detection_outcome",
        required={
            "schema",
            "required_features",
            "input_id",
            "batch_id",
            "tenant_id",
            "purpose",
            "strategy_ref",
            "record",
            "evaluations",
            "outcome",
        },
        optional={"error_code"},
        schema_minor=schema_minor,
    )

    tenant_id = _require_nonempty_string(document.get("tenant_id"), "tenant_id")
    purpose = _normalize_purpose(document.get("purpose"))
    batch_id = _require_nonempty_string(document.get("batch_id"), "batch_id")
    del batch_id

    expected_tenant_id = _require_nonempty_string(strategy_ir.get("tenant_id"), "strategy_ir.tenant_id")
    expected_purpose = _normalize_purpose(strategy_ir.get("purpose"))
    if tenant_id != expected_tenant_id or purpose != expected_purpose:
        raise ContractValidationError("outcome tenant or purpose does not match StrategyIR")

    strategy_ref = _normalize_strategy_ref(document.get("strategy_ref"), schema_minor=schema_minor)
    expected_strategy_ref = _normalize_strategy_ref(strategy_ir.get("strategy_ref"))
    if strategy_ref != expected_strategy_ref:
        raise ContractValidationError("outcome strategy_ref does not match StrategyIR")

    record = _validate_fixed_fields(
        document.get("record"),
        "record",
        required={"record_id", "source_time", "dimensions_md5", "data_raw"},
        schema_minor=schema_minor,
    )
    record_id = record.get("record_id")
    dimensions_md5, source_time = _parse_record_id(record_id)
    if record.get("dimensions_md5") != dimensions_md5:
        raise ContractValidationError("record dimensions_md5 does not match record_id")
    if _require_source_time(record.get("source_time"), "record.source_time") != source_time:
        raise ContractValidationError("record source_time does not match record_id")
    data_raw = _validate_fixed_fields(
        record.get("data_raw"),
        "record.data_raw",
        required={"record_id", "time"},
        optional={"values"},
        schema_minor=schema_minor,
        allow_open=True,
    )
    data_raw_time = _require_source_time(data_raw.get("time"), "record.data_raw.time")
    if data_raw.get("record_id") != record_id or data_raw_time != source_time:
        raise ContractValidationError("record.data_raw source coordinate mismatch")
    values = data_raw.get("values")
    if isinstance(values, Mapping) and "timestamp" in values:
        values_timestamp = _require_source_time(values["timestamp"], "record.data_raw.values.timestamp")
        if values_timestamp != source_time:
            raise ContractValidationError("record.data_raw.values timestamp mismatch")

    expected_input_id = derive_input_id(
        tenant_id=tenant_id,
        purpose=purpose,
        strategy_id=strategy_ref["strategy_id"],
        item_id=strategy_ref["item_id"],
        strategy_content_sha256=strategy_ref["content_sha256"],
        record_id=record_id,
    )
    if document.get("input_id") != expected_input_id:
        raise ContractValidationError("input_id does not match canonical tuple")

    outcome = document.get("outcome")
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        raise ContractValidationError(f"unsupported detection outcome: {outcome}")
    error_code = document.get("error_code")
    if outcome in {"NORMAL", "ANOMALOUS"}:
        if "error_code" in document:
            raise ContractValidationError("business outcome must not carry error_code")
    elif not isinstance(error_code, str) or error_code not in ERROR_CODES[outcome]:
        raise ContractValidationError(f"invalid error_code for {outcome}")

    evaluations = document.get("evaluations")
    if not isinstance(evaluations, list):
        raise ContractValidationError("evaluations must be an array")
    required_levels = set(strategy_ir["required_levels"])
    seen_levels = set()
    anomalous_count = 0
    for evaluation in evaluations:
        evaluation = _validate_fixed_fields(
            evaluation,
            "evaluation",
            required={"level", "result"},
            optional={"anomaly"},
            schema_minor=schema_minor,
        )
        level = _require_positive_int(evaluation.get("level"), "evaluation.level")
        if level not in required_levels:
            raise ContractValidationError("evaluation level is not required by StrategyIR")
        if level in seen_levels:
            raise ContractValidationError("evaluations contains duplicate level")
        seen_levels.add(level)

        result = evaluation.get("result")
        if not isinstance(result, str) or result not in EVALUATION_RESULTS:
            raise ContractValidationError(f"unsupported evaluation result: {result}")
        anomaly = evaluation.get("anomaly")
        if result == "NORMAL":
            if "anomaly" in evaluation:
                raise ContractValidationError("NORMAL evaluation must not carry anomaly")
            continue

        anomaly = _validate_fixed_fields(
            anomaly,
            "ANOMALOUS evaluation anomaly",
            required={"anomaly_id"},
            optional={"anomaly_message", "context"},
            schema_minor=schema_minor,
            allow_open=True,
        )
        expected_anomaly_id = f"{record_id}.{strategy_ref['strategy_id']}.{strategy_ref['item_id']}.{level}"
        if anomaly.get("anomaly_id") != expected_anomaly_id:
            raise ContractValidationError("anomaly_id does not match record, strategy, item and level")
        anomalous_count += 1

    if outcome in {"NORMAL", "ANOMALOUS"} and seen_levels != required_levels:
        raise ContractValidationError("business outcome evaluations must be complete")
    if outcome == "NORMAL" and anomalous_count:
        raise ContractValidationError("NORMAL outcome must contain only NORMAL evaluations")
    if outcome == "ANOMALOUS" and not anomalous_count:
        raise ContractValidationError("ANOMALOUS outcome must contain at least one ANOMALOUS evaluation")


def can_drive_trigger(document: Mapping, strategy_ir: Mapping) -> bool:
    """Return whether a valid DetectionOutcome may advance Trigger state."""

    validate_detection_outcome(document, strategy_ir)
    return document["outcome"] in {"NORMAL", "ANOMALOUS"}
