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
from alarm_backends.core.alarm_engine.publisher import _trigger_input_envelope
from alarm_backends.core.alarm_engine.reference import (
    build_reference_trigger_decision_batch,
    build_reference_trigger_decision_candidate,
    build_terminal_reference_decision_batches,
    is_alarm_engine_shadow_strategy_selected,
)
from alarm_backends.core.alarm_engine.runtime import prepare_finalized_threshold_batch
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY, TRIGGER_POINT, TRIGGER_STRATEGY


def legacy_bytes(strategy):
    return json.dumps(strategy, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


GOLDEN_FILE = Path(__file__).parent / "testdata" / "python-v1" / "trigger_decision_v1.json"
CHECKSUM_FILE = GOLDEN_FILE.parent / "SHA256SUMS"


def read_checksums(path: Path) -> dict[str, str]:
    return {
        name: digest
        for digest, name in (line.split("  ", 1) for line in path.read_text(encoding="ascii").splitlines() if line)
    }


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


def detect_outcome(*, point, strategy, raw):
    """Rebuild the authoritative Detect projection a Trigger reference must match."""

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
    outcome = build_detection_outcome(
        strategy_ir=strategy_ir,
        batch_id="authoritative-detect-batch",
        data_raw=point["data"],
        evaluations=evaluations,
        outcome="ANOMALOUS",
    )
    return strategy_ir, outcome


def detect_input_id(*, point, strategy, raw):
    return detect_outcome(point=point, strategy=strategy, raw=raw)[1]["input_id"]


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


def build_decision_golden_fixtures() -> list[dict]:
    """Project every Python reference terminal state with its authoritative TriggerInput.

    Each fixture carries the exact TriggerInput wire the decision was derived from, so the
    Go consumer can cross-check the terminal against the authoritative DetectionOutcome
    instead of only validating the decision in isolation.
    """

    point = copy.deepcopy(TRIGGER_POINT)
    trigger_strategy = copy.deepcopy(TRIGGER_STRATEGY)
    trigger_strategy["update_time"] = 1569246480
    trigger_raw = legacy_bytes(trigger_strategy)
    trigger_strategy_ir, anomalous = detect_outcome(point=point, strategy=trigger_strategy, raw=trigger_raw)
    anomalous_input = _trigger_input_envelope(trigger_strategy_ir, [anomalous])

    detect_strategy = copy.deepcopy(DETECT_STRATEGY)
    detect_raw = legacy_bytes(detect_strategy)
    detect_strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=detect_strategy,
        item_id=2,
        legacy_json=detect_raw,
    )

    def detect_terminal(record, *, outcome, error_code=None, evaluations):
        return build_detection_outcome(
            strategy_ir=detect_strategy_ir,
            batch_id="authoritative-detect-batch",
            data_raw=copy.deepcopy(record),
            evaluations=evaluations,
            outcome=outcome,
            error_code=error_code,
        )

    normal = detect_terminal(
        DETECT_RECORDS[1],
        outcome="NORMAL",
        evaluations=[{"level": level, "result": "NORMAL"} for level in detect_strategy_ir["required_levels"]],
    )
    algorithm_error = detect_terminal(DETECT_RECORDS[0], outcome="ERROR", error_code="ALGORITHM_ERROR", evaluations=[])
    unsupported = detect_terminal(
        DETECT_RECORDS[0], outcome="UNSUPPORTED", error_code="UNSUPPORTED_STRATEGY", evaluations=[]
    )

    fixtures = [
        {
            "name": "python-trigger-reference",
            "trigger_input": anomalous_input,
            "batch": build_reference(
                point=point, strategy=trigger_strategy, raw=trigger_raw, event_record=triggered_event(point)
            ),
        },
        {
            "name": "python-trigger-condition-not-met",
            "trigger_input": anomalous_input,
            "batch": build_reference(point=point, strategy=trigger_strategy, raw=trigger_raw, event_record=None),
        },
    ]
    for name, source in (
        ("python-input-normal", normal),
        ("python-error-terminal", algorithm_error),
        ("python-unsupported-terminal", unsupported),
    ):
        fixtures.append(
            {
                "name": name,
                "trigger_input": _trigger_input_envelope(detect_strategy_ir, [source]),
                "batch": build_terminal_reference_decision_batches(
                    strategy_ir=detect_strategy_ir,
                    detection_outcomes=[source],
                )[0],
            }
        )
    return fixtures


def test_python_reference_decision_golden_covers_every_terminal_state():
    expected = {"schema_version": "trigger-decision-batch/1.0", "fixtures": build_decision_golden_fixtures()}
    payload = GOLDEN_FILE.read_bytes()

    assert hashlib.sha256(payload).hexdigest() == read_checksums(CHECKSUM_FILE)[GOLDEN_FILE.name]
    assert decode_json_document(payload) == expected
    terminals = [
        (fixture["batch"]["decisions"][0]["outcome"], fixture["batch"]["decisions"][0]["reason_code"])
        for fixture in expected["fixtures"]
    ]
    assert terminals == [
        ("TRIGGER", "TRIGGER_CONDITION_MET"),
        ("NO_TRIGGER", "TRIGGER_CONDITION_NOT_MET"),
        ("NO_TRIGGER", "INPUT_NORMAL"),
        ("ERROR", "ALGORITHM_ERROR"),
        ("UNSUPPORTED", "UNSUPPORTED_STRATEGY"),
    ]


def test_python_reference_decision_golden_binds_each_terminal_to_its_authoritative_input():
    for fixture in build_decision_golden_fixtures():
        sources = {outcome["input_id"] for outcome in fixture["trigger_input"]["detection_outcomes"]}
        decisions = {decision["input_id"] for decision in fixture["batch"]["decisions"]}

        assert decisions <= sources, fixture["name"]


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


def test_unconfirmed_reference_candidate_preserves_the_same_trigger_identity():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    raw = legacy_bytes(strategy)

    candidate = build_reference_trigger_decision_candidate(
        strategy=strategy,
        legacy_json=raw,
        strategy_snapshot_key=point["strategy_snapshot_key"],
        tenant_id_resolver=lambda _bk_biz_id: "default",
        item_id=1,
        point=point,
        event_record=triggered_event(point),
    )
    acknowledged = build_reference(
        point=point,
        strategy=strategy,
        event_record=triggered_event(point),
        raw=raw,
    )

    assert candidate == acknowledged


@pytest.mark.parametrize("selector", [(True,), (1.9,), ("01",), (" 1 ",), "1,", None])
def test_alarm_engine_shadow_strategy_selector_rejects_noncanonical_values(selector):
    assert not is_alarm_engine_shadow_strategy_selected(selector, 1)


@pytest.mark.parametrize("selector", [(1,), ("1",), "1", ("2", 1)])
def test_alarm_engine_shadow_strategy_selector_accepts_exact_positive_ids(selector):
    assert is_alarm_engine_shadow_strategy_selected(selector, 1)


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
