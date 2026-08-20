"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import math
from collections.abc import Mapping
from typing import Any

from alarm_backends.core.alarm_engine.contract import ContractValidationError


MAX_TRIGGER_DECISION_BATCH_BYTES = 512 * 1024


def _validate_json_value(value: Any, field: str = "contract payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ContractValidationError(f"{field} object keys must be strings")
            _validate_json_value(key, field)
            _validate_json_value(child, field)
    elif isinstance(value, list):
        for child in value:
            _validate_json_value(child, field)
    elif isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ContractValidationError(f"{field} must contain valid UTF-8") from exc
    elif value is None or isinstance(value, (bool, int)):
        return
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ContractValidationError(f"{field} must not contain non-finite numbers")
    else:
        raise ContractValidationError(f"{field} contains unsupported JSON value type")


def encode_json_document(document: Mapping) -> bytes:
    """Encode a contract document deterministically without accepting NaN or infinity."""

    _validate_json_value(document)
    return json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ContractValidationError(f"non-finite JSON number: {value}")


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ContractValidationError(f"non-finite JSON number: {value}")
    return parsed


def decode_json_document(payload: bytes | str) -> dict:
    """Decode an object document while preserving integers and rejecting ambiguous JSON."""

    if (isinstance(payload, bytes) and payload.startswith(b"\xef\xbb\xbf")) or (
        isinstance(payload, str) and payload.startswith("\ufeff")
    ):
        raise ContractValidationError("contract payload must not contain a UTF-8 BOM")
    try:
        document = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("contract payload must be valid UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise ContractValidationError("contract payload must contain a JSON object")
    _validate_json_value(document)
    return document


def encode_trigger_decision_batch(document: Mapping) -> bytes:
    from alarm_backends.core.alarm_engine.contract import validate_trigger_decision_batch

    validate_trigger_decision_batch(document)
    payload = encode_json_document(document)
    if len(payload) > MAX_TRIGGER_DECISION_BATCH_BYTES:
        raise ContractValidationError("trigger decision batch exceeds encoded byte limit")
    return payload


def decode_trigger_decision_batch(payload: bytes | str) -> dict:
    if len(payload.encode("utf-8") if isinstance(payload, str) else payload) > MAX_TRIGGER_DECISION_BATCH_BYTES:
        raise ContractValidationError("trigger decision batch exceeds encoded byte limit")
    document = decode_json_document(payload)

    from alarm_backends.core.alarm_engine.contract import validate_trigger_decision_batch

    validate_trigger_decision_batch(document)
    return document
