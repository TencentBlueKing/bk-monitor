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
from collections.abc import Mapping, Sequence

from alarm_backends.core.alarmd.contract import (
    ContractValidationError,
    build_detection_outcome,
    build_trigger_strategy_ir_from_legacy_config,
    validate_trigger_strategy_ir,
)
from alarm_backends.core.alarmd.encoder import encode_json_document


class DetectionNotFinalized(ContractValidationError):
    """Raised when a record batch cannot safely be projected as a business outcome."""


def prepare_detect_input_batch(
    *,
    strategy_ir: Mapping,
    batch_id: str,
    data_points: Sequence[Mapping],
) -> dict:
    """Build the raw record batch consumed by the Go Detect→Trigger Shadow path."""

    validate_trigger_strategy_ir(strategy_ir)
    if not isinstance(batch_id, str) or not batch_id:
        raise ContractValidationError("batch_id must be a non-empty string")
    records = []
    record_ids = set()
    for data_point in data_points:
        if not isinstance(data_point, Mapping):
            raise ContractValidationError("data point must be an object")
        record_id = data_point.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise ContractValidationError("data point record_id must be a non-empty string")
        if record_id in record_ids:
            raise ContractValidationError(f"duplicate accepted record: {record_id}")
        record_ids.add(record_id)
        records.append(copy.deepcopy(dict(data_point)))
    if not records:
        raise ContractValidationError("detect input records must not be empty")
    return {
        "schema": {"name": "detect-input", "major": 1, "minor": 0},
        "required_features": [],
        "partition_hash_version": "trigger-input-partition-v1",
        "strategy_ir": copy.deepcopy(dict(strategy_ir)),
        "batch_id": batch_id,
        "records": records,
    }


def prepare_finalized_threshold_batch(
    *,
    tenant_id: str,
    strategy: Mapping,
    item_id: str | int,
    legacy_json: bytes,
    batch_id: str,
    data_points: Sequence[Mapping],
    anomaly_outputs: Sequence[Mapping],
    finalized: bool,
) -> dict:
    """Build the first DETECT-only Threshold input batch after finalization is proven."""

    if finalized is not True:
        raise DetectionNotFinalized("detection batch is not finalized")
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id=tenant_id,
        purpose="DETECT",
        strategy=strategy,
        item_id=item_id,
        legacy_json=legacy_json,
    )
    outcomes = project_detection_outcomes(
        strategy_ir=strategy_ir,
        batch_id=batch_id,
        data_points=data_points,
        anomaly_outputs=anomaly_outputs,
    )
    return {"strategy_ir": strategy_ir, "outcomes": outcomes}


def project_detection_outcomes(
    *,
    strategy_ir: Mapping,
    batch_id: str,
    data_points: Sequence[Mapping],
    anomaly_outputs: Sequence[Mapping],
) -> list[dict]:
    """Project finalized legacy Detect results into one outcome per accepted record."""

    validate_trigger_strategy_ir(strategy_ir)
    anomalies_by_record = _index_anomalies(anomaly_outputs)
    seen_records = set()
    outcomes = []
    for data_raw in data_points:
        if not isinstance(data_raw, Mapping):
            raise ContractValidationError("data point must be an object")
        record_id = data_raw.get("record_id")
        if record_id in seen_records:
            raise ContractValidationError(f"duplicate accepted record: {record_id}")
        seen_records.add(record_id)

        indexed_output = anomalies_by_record.pop(record_id, None)
        if indexed_output is None:
            anomalies = {}
        else:
            if encode_json_document(indexed_output["data"]) != encode_json_document(data_raw):
                raise ContractValidationError(f"anomaly output data does not match accepted data: {record_id}")
            anomalies = indexed_output["anomalies"]
        evaluations = []
        for level in strategy_ir["required_levels"]:
            level_key = str(level)
            if level_key not in anomalies:
                evaluations.append({"level": level, "result": "NORMAL"})
                continue
            anomaly = anomalies.pop(level_key)
            evaluations.append(
                {
                    "level": level,
                    "result": "ANOMALOUS",
                    "anomaly": copy.deepcopy(anomaly),
                }
            )
        if anomalies:
            raise ContractValidationError(f"anomaly contains levels not required by StrategyIR: {sorted(anomalies)}")
        outcomes.append(
            build_detection_outcome(
                strategy_ir=strategy_ir,
                batch_id=batch_id,
                data_raw=data_raw,
                evaluations=evaluations,
                outcome="ANOMALOUS" if any(item["result"] == "ANOMALOUS" for item in evaluations) else "NORMAL",
            )
        )
    if anomalies_by_record:
        raise ContractValidationError(f"anomaly output references unaccepted record: {sorted(anomalies_by_record)}")
    return outcomes


def _index_anomalies(anomaly_outputs: Sequence[Mapping]) -> dict[str, dict]:
    anomalies_by_record = {}
    for output in anomaly_outputs:
        if not isinstance(output, Mapping):
            raise ContractValidationError("anomaly output must be an object")
        data = output.get("data")
        anomalies = output.get("anomaly")
        if not isinstance(data, Mapping) or not isinstance(anomalies, Mapping):
            raise ContractValidationError("anomaly output data and anomaly must be objects")
        record_id = data.get("record_id")
        if not isinstance(record_id, str):
            raise ContractValidationError("anomaly output record_id must be a string")
        if record_id in anomalies_by_record:
            raise ContractValidationError(f"duplicate anomaly output: {record_id}")
        if not anomalies:
            raise ContractValidationError("anomaly output must contain at least one anomaly")
        if any(not isinstance(level, str) for level in anomalies):
            raise ContractValidationError("anomaly level keys must be strings")
        if any(not isinstance(anomaly, Mapping) for anomaly in anomalies.values()):
            raise ContractValidationError("anomaly entries must be objects")
        anomalies_by_record[record_id] = {
            "data": copy.deepcopy(dict(data)),
            "anomalies": copy.deepcopy(dict(anomalies)),
        }
    return anomalies_by_record
