"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from collections.abc import Mapping
from collections.abc import Callable

from alarm_backends.core.alarmd.contract import (
    ContractValidationError,
    build_detection_outcome,
    build_trigger_decision_batch,
    build_trigger_strategy_ir_from_legacy_config,
    derive_trigger_decision_id,
    json_values_equal,
    validate_detection_outcome,
    validate_trigger_strategy_ir,
)


def build_reference_trigger_decision_batch(
    *,
    strategy: Mapping,
    legacy_json: bytes,
    strategy_snapshot_key: str,
    tenant_id_resolver: Callable[[int], str],
    expected_input_id: str,
    item_id: str | int,
    point: Mapping,
    event_record: Mapping | None,
) -> dict:
    """Project one real Trigger result and verify it against an acknowledged Detection input."""

    return _build_reference_trigger_decision_batch(
        strategy=strategy,
        legacy_json=legacy_json,
        strategy_snapshot_key=strategy_snapshot_key,
        tenant_id_resolver=tenant_id_resolver,
        expected_input_id=expected_input_id,
        item_id=item_id,
        point=point,
        event_record=event_record,
    )


def build_reference_trigger_decision_candidate(
    *,
    strategy: Mapping,
    legacy_json: bytes,
    strategy_snapshot_key: str,
    tenant_id_resolver: Callable[[int], str],
    item_id: str | int,
    point: Mapping,
    event_record: Mapping | None,
) -> dict:
    """Project an unconfirmed Trigger result for later DetectInput correlation."""

    return _build_reference_trigger_decision_batch(
        strategy=strategy,
        legacy_json=legacy_json,
        strategy_snapshot_key=strategy_snapshot_key,
        tenant_id_resolver=tenant_id_resolver,
        expected_input_id=None,
        item_id=item_id,
        point=point,
        event_record=event_record,
    )


def _build_reference_trigger_decision_batch(
    *,
    strategy: Mapping,
    legacy_json: bytes,
    strategy_snapshot_key: str,
    tenant_id_resolver: Callable[[int], str],
    expected_input_id: str | None,
    item_id: str | int,
    point: Mapping,
    event_record: Mapping | None,
) -> dict:
    """Project one real legacy Python Trigger result without mutating its Redis point."""

    point = _require_mapping(point, "reference point")
    point_snapshot_key = _require_nonempty_utf8(point.get("strategy_snapshot_key"), "reference point snapshot key")
    strategy_snapshot_key = _require_nonempty_utf8(strategy_snapshot_key, "reference strategy snapshot key")
    if point_snapshot_key != strategy_snapshot_key:
        raise ContractValidationError("reference point does not match the exact strategy snapshot")
    strategy = _require_mapping(strategy, "reference strategy")
    bk_biz_id = strategy.get("bk_biz_id")
    if isinstance(bk_biz_id, bool) or not isinstance(bk_biz_id, int):
        raise ContractValidationError("reference strategy bk_biz_id must be an integer")
    if not callable(tenant_id_resolver):
        raise ContractValidationError("reference tenant_id_resolver must be callable")
    tenant_id = tenant_id_resolver(bk_biz_id)
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id=tenant_id,
        purpose="DETECT",
        strategy=strategy,
        item_id=item_id,
        legacy_json=legacy_json,
    )
    data_raw = _require_mapping(point.get("data"), "reference point data")
    anomalies = _require_mapping(point.get("anomaly"), "reference point anomaly")
    if not anomalies:
        raise ContractValidationError("reference Trigger point must contain an anomaly")

    evaluations = []
    remaining = dict(anomalies)
    for level in strategy_ir["required_levels"]:
        level_key = str(level)
        if level_key not in remaining:
            evaluations.append({"level": level, "result": "NORMAL"})
        else:
            anomaly = remaining.pop(level_key)
            evaluations.append(
                {
                    "level": level,
                    "result": "ANOMALOUS",
                    "anomaly": copy.deepcopy(_require_mapping(anomaly, "reference anomaly")),
                }
            )
    if remaining:
        raise ContractValidationError("reference point contains a level outside StrategyIR")

    record_id = data_raw.get("record_id")
    source = build_detection_outcome(
        strategy_ir=strategy_ir,
        batch_id=f"python-reference-{record_id}",
        data_raw=data_raw,
        evaluations=evaluations,
        outcome="ANOMALOUS",
    )
    if expected_input_id is not None and source["input_id"] != expected_input_id:
        raise ContractValidationError("reference input_id does not match the acknowledged Detect input")
    decision = {
        "decision_id": derive_trigger_decision_id(source["input_id"]),
        "input_id": source["input_id"],
        "record_id": record_id,
        "outcome": "NO_TRIGGER",
        "reason_code": "TRIGGER_CONDITION_NOT_MET",
        "anomaly_timestamps": [],
    }
    if event_record is not None:
        level, timestamps = _parse_trigger_result(
            event_record,
            strategy_ir=strategy_ir,
            source=source,
            strategy_snapshot_key=strategy_snapshot_key,
        )
        decision.update(
            outcome="TRIGGER",
            reason_code="TRIGGER_CONDITION_MET",
            level=level,
            anomaly_timestamps=timestamps,
        )
    return build_trigger_decision_batch(
        strategy_ir=strategy_ir,
        batch_id=source["batch_id"],
        decisions=[decision],
    )


def build_terminal_reference_decision_batches(*, strategy_ir: Mapping, detection_outcomes: list[Mapping]) -> list[dict]:
    """Project ACKed non-anomalous DetectionOutcomes without invoking the legacy Trigger."""

    validate_trigger_strategy_ir(strategy_ir)
    if not isinstance(detection_outcomes, list) or not detection_outcomes:
        raise ContractValidationError("reference detection_outcomes must be a non-empty array")
    batch_id = None
    decisions = []
    for source in detection_outcomes:
        validate_detection_outcome(source, strategy_ir)
        if batch_id is None:
            batch_id = source["batch_id"]
        elif source["batch_id"] != batch_id:
            raise ContractValidationError("reference detection_outcomes must share one batch_id")
        if source["outcome"] == "ANOMALOUS":
            continue
        if source["outcome"] == "NORMAL":
            outcome = "NO_TRIGGER"
            reason_code = "INPUT_NORMAL"
        else:
            outcome = source["outcome"]
            reason_code = source["error_code"]
        decisions.append(
            {
                "decision_id": derive_trigger_decision_id(source["input_id"]),
                "input_id": source["input_id"],
                "record_id": source["record"]["record_id"],
                "outcome": outcome,
                "reason_code": reason_code,
                "anomaly_timestamps": [],
            }
        )
    return [
        build_trigger_decision_batch(
            strategy_ir=strategy_ir, batch_id=batch_id, decisions=decisions[start : start + 500]
        )
        for start in range(0, len(decisions), 500)
    ]


def _parse_trigger_result(
    event_record: Mapping,
    *,
    strategy_ir: Mapping,
    source: Mapping,
    strategy_snapshot_key: str,
) -> tuple[int, list[int]]:
    event_record = _require_mapping(event_record, "reference event_record")
    point_data = source["record"]["data_raw"]
    if not json_values_equal(event_record.get("data"), point_data):
        raise ContractValidationError("reference event_record data does not match the source point")
    expected_anomalies = {
        str(evaluation["level"]): evaluation["anomaly"]
        for evaluation in source["evaluations"]
        if evaluation["result"] == "ANOMALOUS"
    }
    if not json_values_equal(event_record.get("anomaly"), expected_anomalies):
        raise ContractValidationError("reference event_record anomaly does not match the source point")
    if event_record.get("strategy_snapshot_key") != strategy_snapshot_key:
        raise ContractValidationError("reference event_record strategy snapshot does not match the source point")
    trigger = _require_mapping(event_record.get("trigger"), "reference event_record trigger")
    raw_level = trigger.get("level")
    if isinstance(raw_level, bool):
        raise ContractValidationError("reference trigger level must be a positive integer")
    try:
        level = int(raw_level)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("reference trigger level must be a positive integer") from exc
    if str(level) != str(raw_level) or level <= 0:
        raise ContractValidationError("reference trigger level must use canonical decimal form")
    anomalous_levels = {
        evaluation["level"] for evaluation in source["evaluations"] if evaluation["result"] == "ANOMALOUS"
    }
    if level not in anomalous_levels:
        raise ContractValidationError("reference trigger level is not anomalous in the source point")

    anomaly_ids = trigger.get("anomaly_ids")
    if not isinstance(anomaly_ids, list) or not anomaly_ids:
        raise ContractValidationError("reference trigger anomaly_ids must be a non-empty array")
    ref = strategy_ir["strategy_ref"]
    (
        record_dimensions,
        _,
    ) = source["record"]["record_id"].split(".", 1)
    timestamps = []
    for anomaly_id in anomaly_ids:
        if not isinstance(anomaly_id, str):
            raise ContractValidationError("reference trigger anomaly_id must be a string")
        parts = anomaly_id.split(".")
        if len(parts) != 5:
            raise ContractValidationError("reference trigger anomaly_id is not canonical")
        dimensions, timestamp, strategy_id, anomaly_item_id, anomaly_level = parts
        if (
            dimensions != record_dimensions
            or strategy_id != ref["strategy_id"]
            or anomaly_item_id != ref["item_id"]
            or anomaly_level != str(level)
            or not timestamp.isascii()
            or not timestamp.isdigit()
            or (timestamp.startswith("0") and timestamp != "0")
        ):
            raise ContractValidationError("reference trigger anomaly_id identity mismatch")
        timestamps.append(int(timestamp))
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        raise ContractValidationError("reference trigger timestamps must be strictly increasing")

    config = next((item for item in strategy_ir["trigger_configs"] if item["level"] == level), None)
    if config is None or len(timestamps) < config["trigger_count"]:
        raise ContractValidationError("reference trigger result does not satisfy trigger_count")
    source_time = source["record"]["source_time"]
    window_start = source_time - strategy_ir["check_window_unit_seconds"] * config["check_window_size"] + 1
    if (
        any(timestamp < window_start or timestamp > source_time for timestamp in timestamps)
        or timestamps[-1] != source_time
    ):
        raise ContractValidationError("reference trigger timestamps fall outside the selected window")
    return level, timestamps


def _require_mapping(value, field):
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field} must be an object")
    return value


def _require_nonempty_utf8(value, field):
    if not isinstance(value, str) or not value:
        raise ContractValidationError(f"{field} must be a non-empty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContractValidationError(f"{field} must contain valid UTF-8") from exc
    return value
