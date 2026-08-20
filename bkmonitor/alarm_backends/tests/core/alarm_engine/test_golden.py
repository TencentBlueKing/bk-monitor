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

from alarm_backends.core.alarm_engine.contract import (
    build_detection_outcome,
    build_trigger_strategy_ir_from_legacy_config,
)
from alarm_backends.core.alarm_engine.encoder import decode_json_document, encode_json_document
from alarm_backends.tests.alarm_engine_fixtures import (
    DETECT_RECORDS,
    DETECT_STRATEGY,
    TRIGGER_POINT,
    TRIGGER_STRATEGY,
)


FIXTURE_DIR = Path(__file__).parent / "testdata" / "python-v1"
FIXTURE_FILE = FIXTURE_DIR / "detection_outcome_v1.json"
CHECKSUM_FILE = FIXTURE_DIR / "SHA256SUMS"
GO_SEMANTIC_FILE = FIXTURE_DIR / "go_semantic_v1.json"


def _legacy_bytes(strategy: dict) -> bytes:
    # Deliberately retain whitespace and insertion order: StrategyIR must preserve these exact bytes.
    return json.dumps(strategy, ensure_ascii=False, indent=1).encode("utf-8")


def _build_detect_strategy_ir():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    return build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=2,
        legacy_json=_legacy_bytes(strategy),
    )


def _build_trigger_strategy_ir():
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    return build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=1,
        legacy_json=_legacy_bytes(strategy),
    )


def _anomaly(record_id: str, strategy_id: int, item_id: int, level: int) -> dict:
    return {
        "anomaly_id": f"{record_id}.{strategy_id}.{item_id}.{level}",
        "anomaly_message": "异常测试",
        "anomaly_time": "2019-10-10 10:10:00",
        "context": {"level": level, "mixed": [1, "2", {"nested": True}]},
    }


def build_fixture_set() -> list[dict]:
    detect_strategy_ir = _build_detect_strategy_ir()
    anomalous_data, normal_data = copy.deepcopy(DETECT_RECORDS)
    anomalous_data["values"]["huge_counter"] = 9007199254740993
    normal = build_detection_outcome(
        strategy_ir=detect_strategy_ir,
        batch_id="detect-batch-1",
        data_raw=normal_data,
        evaluations=[{"level": 3, "result": "NORMAL"}],
        outcome="NORMAL",
    )
    anomalous = build_detection_outcome(
        strategy_ir=detect_strategy_ir,
        batch_id="detect-batch-1",
        data_raw=anomalous_data,
        evaluations=[
            {
                "level": 3,
                "result": "ANOMALOUS",
                "anomaly": _anomaly(anomalous_data["record_id"], 1, 2, 3),
            }
        ],
        outcome="ANOMALOUS",
    )
    retry = build_detection_outcome(
        strategy_ir=detect_strategy_ir,
        batch_id="detect-batch-retry-2",
        data_raw=anomalous_data,
        evaluations=[
            {
                "level": 3,
                "result": "ANOMALOUS",
                "anomaly": _anomaly(anomalous_data["record_id"], 1, 2, 3),
            }
        ],
        outcome="ANOMALOUS",
    )

    trigger_strategy_ir = _build_trigger_strategy_ir()
    trigger_data = copy.deepcopy(TRIGGER_POINT["data"])
    trigger_data["values"]["huge_counter"] = 9007199254740993
    partial_error = build_detection_outcome(
        strategy_ir=trigger_strategy_ir,
        batch_id="trigger-batch-1",
        data_raw=trigger_data,
        evaluations=[{"level": 1, "result": "NORMAL"}],
        outcome="ERROR",
        error_code="ALGORITHM_ERROR",
    )
    unsupported = build_detection_outcome(
        strategy_ir=trigger_strategy_ir,
        batch_id="trigger-batch-1",
        data_raw=trigger_data,
        evaluations=[],
        outcome="UNSUPPORTED",
        error_code="UNSUPPORTED_STRATEGY",
    )

    source_tests = [
        "alarm_backends/tests/service/detect/test_processor.py::TestProcessorViews::test_processor_handle",
        "alarm_backends/tests/service/trigger/test_checker.py::TestChecker::test_init",
    ]
    return [
        {"name": "normal", "source_tests": source_tests, "strategy_ir": detect_strategy_ir, "outcome": normal},
        {
            "name": "anomalous",
            "source_tests": source_tests,
            "strategy_ir": detect_strategy_ir,
            "outcome": anomalous,
        },
        {
            "name": "error-partial",
            "source_tests": source_tests,
            "strategy_ir": trigger_strategy_ir,
            "outcome": partial_error,
        },
        {
            "name": "unsupported-empty",
            "source_tests": source_tests,
            "strategy_ir": trigger_strategy_ir,
            "outcome": unsupported,
        },
        {
            "name": "retry-same-input",
            "source_tests": source_tests,
            "strategy_ir": detect_strategy_ir,
            "outcome": retry,
        },
    ]


def test_python_v1_golden_matches_current_legacy_objects_without_overwriting_fixture():
    expected = decode_json_document(FIXTURE_FILE.read_bytes())

    assert expected["schema_version"] == "detection-outcome/1.0"
    assert expected["fixtures"] == build_fixture_set()


def test_python_v1_golden_checksum_is_current():
    checksums = {
        name: digest
        for digest, name in (
            line.split("  ", 1) for line in CHECKSUM_FILE.read_text(encoding="ascii").splitlines() if line
        )
    }

    assert hashlib.sha256(FIXTURE_FILE.read_bytes()).hexdigest() == checksums[FIXTURE_FILE.name]
    assert hashlib.sha256(GO_SEMANTIC_FILE.read_bytes()).hexdigest() == checksums[GO_SEMANTIC_FILE.name]


def test_retry_fixture_reuses_input_id_but_changes_transport_correlation():
    fixtures = {fixture["name"]: fixture for fixture in build_fixture_set()}
    anomalous = fixtures["anomalous"]["outcome"]
    retry = fixtures["retry-same-input"]["outcome"]

    assert retry["input_id"] == anomalous["input_id"]
    assert retry["batch_id"] != anomalous["batch_id"]


def test_fixture_set_itself_is_json_encodable_without_precision_loss():
    fixture_set = {"schema_version": "detection-outcome/1.0", "fixtures": build_fixture_set()}

    assert decode_json_document(encode_json_document(fixture_set)) == fixture_set


def test_go_semantic_projection_matches_python_contract_documents():
    go_projection = decode_json_document(GO_SEMANTIC_FILE.read_bytes())
    python_projection = {
        "schema_version": "detection-outcome/1.0",
        "fixtures": [
            {
                "name": fixture["name"],
                "strategy_ir": fixture["strategy_ir"],
                "outcome": fixture["outcome"],
            }
            for fixture in build_fixture_set()
        ],
    }

    assert go_projection == python_projection
