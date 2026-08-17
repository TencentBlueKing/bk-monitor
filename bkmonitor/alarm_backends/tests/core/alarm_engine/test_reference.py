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
import hashlib
import json
from pathlib import Path

import pytest

from alarm_backends.core.alarm_engine.contract import (
    ContractValidationError,
    build_detection_outcome,
    build_trigger_strategy_ir_from_legacy_config,
)
from alarm_backends.core.alarm_engine.encoder import decode_json_document
from alarm_backends.core.alarm_engine.reference import build_reference_trigger_decision_batch
from alarm_backends.core.alarm_engine.reference import build_terminal_reference_decision_batches
from alarm_backends.core.alarm_engine.runtime import prepare_finalized_threshold_batch
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY, TRIGGER_POINT, TRIGGER_STRATEGY


def legacy_bytes(strategy):
    return json.dumps(strategy, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


GOLDEN_FILE = Path(__file__).parent / "testdata" / "python-v1" / "trigger_decision_v1.json"
GOLDEN_SHA256 = "982bfd06f5cf3d98fc2f7c965fafd854346601b1a47d74e86e4c7195a1f93f21"


def build_reference(*, point, strategy, event_record, raw=None, tenant_id="default"):
    raw = raw or legacy_bytes(strategy)
    return build_reference_trigger_decision_batch(
        strategy=strategy,
        legacy_json=raw,
        strategy_snapshot_key=point["strategy_snapshot_key"],
        tenant_id_resolver=lambda _bk_biz_id: tenant_id,
        expected_input_id=detect_input_id(point=point, strategy=strategy, raw=raw),
        item_id=1,
        point=point,
        event_record=event_record,
    )


def triggered_event(point):
    source_time = point["data"]["time"]
    return {
        "data": copy.deepcopy(point["data"]),
        "anomaly": copy.deepcopy(point["anomaly"]),
        "strategy_snapshot_key": point["strategy_snapshot_key"],
        "trigger": {
            "level": "3",
            "anomaly_ids": [f"55a76cf628e46c04a052f4e19bdb9dbf.{source_time}.1.1.3"],
        },
    }


def detect_input_id(*, point, strategy, raw):
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=1,
        legacy_json=raw,
    )
    evaluations = [
        {"level": level, "result": "ANOMALOUS", "anomaly": copy.deepcopy(point["anomaly"][str(level)])}
        for level in strategy_ir["required_levels"]
    ]
    return build_detection_outcome(
        strategy_ir=strategy_ir,
        batch_id="authoritative-detect-batch",
        data_raw=point["data"],
        evaluations=evaluations,
        outcome="ANOMALOUS",
    )["input_id"]


def test_reference_rebuilds_same_input_id_from_exact_snapshot_for_no_trigger():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    raw = legacy_bytes(strategy)

    first = build_reference(point=point, strategy=strategy, raw=raw, event_record=None)
    retry = build_reference(point=point, strategy=strategy, raw=raw, event_record=None)

    assert first == retry
    assert first["decisions"][0]["outcome"] == "NO_TRIGGER"
    assert first["decisions"][0]["reason_code"] == "TRIGGER_CONDITION_NOT_MET"


def test_reference_projects_real_checker_trigger_shape():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    source_time = point["data"]["time"]
    batch = build_reference(point=point, strategy=strategy, event_record=triggered_event(point))

    assert batch["decisions"][0]["outcome"] == "TRIGGER"
    assert batch["decisions"][0]["reason_code"] == "TRIGGER_CONDITION_MET"
    assert batch["decisions"][0]["level"] == 3
    assert batch["decisions"][0]["anomaly_timestamps"] == [source_time]


def test_python_reference_decision_golden_is_current():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    expected = {
        "schema_version": "trigger-decision-batch/1.0",
        "fixtures": [
            {
                "name": "python-trigger-reference",
                "batch": build_reference(point=point, strategy=strategy, event_record=triggered_event(point)),
            }
        ],
    }

    payload = GOLDEN_FILE.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == GOLDEN_SHA256
    assert decode_json_document(payload) == expected


def test_reference_uses_exact_snapshot_bytes_and_fails_closed_on_identity_drift():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    compact = legacy_bytes(strategy)
    spaced = json.dumps(strategy, ensure_ascii=False, indent=1).encode("utf-8")

    compact_batch = build_reference(point=point, strategy=strategy, raw=compact, event_record=None)
    spaced_batch = build_reference(point=point, strategy=strategy, raw=spaced, event_record=None)
    assert compact_batch["decisions"][0]["input_id"] != spaced_batch["decisions"][0]["input_id"]

    point["data"]["time"] += 1
    with pytest.raises(ContractValidationError):
        build_reference(point=point, strategy=strategy, raw=compact, event_record=None)


def test_reference_rejects_null_anomaly_instead_of_treating_it_as_normal():
    point = copy.deepcopy(TRIGGER_POINT)
    point["anomaly"]["1"] = None
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480

    with pytest.raises(ContractValidationError, match="object"):
        build_reference(point=point, strategy=strategy, event_record=None)


def test_reference_input_id_matches_authoritative_detect_projection():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    raw = legacy_bytes(strategy)
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=1,
        legacy_json=raw,
    )
    evaluations = [
        {"level": level, "result": "ANOMALOUS", "anomaly": copy.deepcopy(point["anomaly"][str(level)])}
        for level in strategy_ir["required_levels"]
    ]
    detect = build_detection_outcome(
        strategy_ir=strategy_ir,
        batch_id="authoritative-detect-batch",
        data_raw=point["data"],
        evaluations=evaluations,
        outcome="ANOMALOUS",
    )

    reference = build_reference(point=point, strategy=strategy, raw=raw, event_record=None)

    assert reference["decisions"][0]["input_id"] == detect["input_id"]


def test_reference_rejects_stale_snapshot_and_event_identity():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    with pytest.raises(ContractValidationError, match="exact strategy snapshot"):
        build_reference_trigger_decision_batch(
            strategy=strategy,
            legacy_json=legacy_bytes(strategy),
            strategy_snapshot_key="another-snapshot",
            tenant_id_resolver=lambda _bk_biz_id: "default",
            expected_input_id=detect_input_id(point=point, strategy=strategy, raw=legacy_bytes(strategy)),
            item_id=1,
            point=point,
            event_record=None,
        )

    stale_event = triggered_event(point)
    stale_event["data"]["value"] = 999
    with pytest.raises(ContractValidationError, match="event_record data"):
        build_reference(point=point, strategy=strategy, event_record=stale_event)


@pytest.mark.parametrize("snapshot_key", [None, "", b"snapshot", "\ud800"])
def test_reference_rejects_missing_or_invalid_snapshot_identity(snapshot_key):
    point = copy.deepcopy(TRIGGER_POINT)
    point["strategy_snapshot_key"] = snapshot_key
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480

    with pytest.raises(ContractValidationError, match="snapshot key"):
        build_reference_trigger_decision_batch(
            strategy=strategy,
            legacy_json=legacy_bytes(strategy),
            strategy_snapshot_key=snapshot_key,
            tenant_id_resolver=lambda _bk_biz_id: "default",
            expected_input_id="0" * 64,
            item_id=1,
            point=point,
            event_record=None,
        )


def test_reference_rejects_tenant_mapping_drift_from_acknowledged_detect_input():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480

    with pytest.raises(ContractValidationError, match="acknowledged Detect input"):
        build_reference(point=point, strategy=strategy, event_record=None, tenant_id="tenant-b")


def test_terminal_reference_projects_only_detection_terminal_outcomes_after_ack():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    detection = prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=strategy,
        item_id=2,
        legacy_json=legacy_bytes(strategy),
        batch_id="detect-batch",
        data_points=copy.deepcopy(DETECT_RECORDS),
        anomaly_outputs=[
            {
                "data": copy.deepcopy(DETECT_RECORDS[0]),
                "anomaly": {
                    "3": {
                        "anomaly_id": f"{DETECT_RECORDS[0]['record_id']}.1.2.3",
                        "anomaly_message": "threshold matched",
                    }
                },
            }
        ],
        finalized=True,
    )

    reference_batches = build_terminal_reference_decision_batches(
        strategy_ir=detection["strategy_ir"],
        detection_outcomes=detection["outcomes"],
    )
    reference = reference_batches[0]

    assert [decision["input_id"] for decision in reference["decisions"]] == [detection["outcomes"][1]["input_id"]]
    assert reference["decisions"][0]["outcome"] == "NO_TRIGGER"
    assert reference["decisions"][0]["reason_code"] == "INPUT_NORMAL"


@pytest.mark.parametrize(
    ("outcome", "error_code"),
    [
        ("ERROR", "ALGORITHM_ERROR"),
        ("UNSUPPORTED", "UNSUPPORTED_STRATEGY"),
    ],
)
def test_terminal_reference_preserves_detection_error_terminal(outcome, error_code):
    strategy = copy.deepcopy(DETECT_STRATEGY)
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=2,
        legacy_json=legacy_bytes(strategy),
    )
    source = build_detection_outcome(
        strategy_ir=strategy_ir,
        batch_id="detect-batch",
        data_raw=copy.deepcopy(DETECT_RECORDS[0]),
        evaluations=[],
        outcome=outcome,
        error_code=error_code,
    )

    reference_batches = build_terminal_reference_decision_batches(
        strategy_ir=strategy_ir,
        detection_outcomes=[source],
    )
    reference = reference_batches[0]

    assert reference["decisions"][0]["outcome"] == outcome
    assert reference["decisions"][0]["reason_code"] == error_code


def test_terminal_reference_returns_none_when_all_inputs_require_real_trigger():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    detection = prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=strategy,
        item_id=2,
        legacy_json=legacy_bytes(strategy),
        batch_id="detect-batch",
        data_points=[copy.deepcopy(DETECT_RECORDS[0])],
        anomaly_outputs=[
            {
                "data": copy.deepcopy(DETECT_RECORDS[0]),
                "anomaly": {"3": {"anomaly_id": f"{DETECT_RECORDS[0]['record_id']}.1.2.3"}},
            }
        ],
        finalized=True,
    )

    assert (
        build_terminal_reference_decision_batches(
            strategy_ir=detection["strategy_ir"],
            detection_outcomes=detection["outcomes"],
        )
        == []
    )


@pytest.mark.parametrize(("outcome_count", "expected_chunk_sizes"), [(500, [500]), (501, [500, 1])])
def test_terminal_reference_chunks_at_the_wire_outcome_limit(outcome_count, expected_chunk_sizes):
    strategy = copy.deepcopy(DETECT_STRATEGY)
    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=2,
        legacy_json=legacy_bytes(strategy),
    )
    template = copy.deepcopy(DETECT_RECORDS[1])
    outcomes = []
    for index in range(outcome_count):
        record = copy.deepcopy(template)
        record["record_id"] = f"{index:032x}.{index + 1}"
        record["time"] = index + 1
        record["values"]["timestamp"] = index + 1
        outcomes.append(
            build_detection_outcome(
                strategy_ir=strategy_ir,
                batch_id="detect-batch",
                data_raw=record,
                evaluations=[{"level": level, "result": "NORMAL"} for level in strategy_ir["required_levels"]],
                outcome="NORMAL",
            )
        )

    batches = build_terminal_reference_decision_batches(
        strategy_ir=strategy_ir,
        detection_outcomes=outcomes,
    )

    assert [len(batch["decisions"]) for batch in batches] == expected_chunk_sizes
