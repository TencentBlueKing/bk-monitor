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
import json

import pytest

from alarm_backends.core.alarm_engine.contract import (
    ContractValidationError,
    build_trigger_strategy_ir,
    derive_input_id,
)
from alarm_backends.core.alarm_engine.runtime import (
    DetectionNotFinalized,
    prepare_finalized_threshold_batch,
    project_detection_outcomes,
)
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY


def test_project_detection_outcomes_covers_every_record_and_required_level():
    strategy_ir = _strategy_ir()
    records = [
        {
            "record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.100",
            "time": 100,
            "value": 99,
            "values": {"timestamp": 100, "metric": 99},
            "dimensions": {"host": "host-1"},
        },
        {
            "record_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.110",
            "time": 110,
            "value": 10,
            "values": {"timestamp": 110, "metric": 10},
            "dimensions": {"host": "host-2"},
        },
    ]
    anomaly_outputs = [
        {
            "data": records[0],
            "anomaly": {
                "2": {
                    "anomaly_id": f"{records[0]['record_id']}.1.2.2",
                    "anomaly_message": "level 2 anomaly",
                },
                "3": {
                    "anomaly_id": f"{records[0]['record_id']}.1.2.3",
                    "anomaly_message": "level 3 anomaly",
                    "context": {"counter": 9007199254740993},
                },
            },
        }
    ]
    original_records = copy.deepcopy(records)
    original_outputs = copy.deepcopy(anomaly_outputs)

    outcomes = project_detection_outcomes(
        strategy_ir=strategy_ir,
        batch_id="batch-1",
        data_points=records,
        anomaly_outputs=anomaly_outputs,
    )

    assert [outcome["record"]["record_id"] for outcome in outcomes] == [
        records[0]["record_id"],
        records[1]["record_id"],
    ]
    assert [outcome["outcome"] for outcome in outcomes] == ["ANOMALOUS", "NORMAL"]
    assert outcomes[0]["evaluations"] == [
        {"level": 1, "result": "NORMAL"},
        {"level": 2, "result": "ANOMALOUS", "anomaly": anomaly_outputs[0]["anomaly"]["2"]},
        {"level": 3, "result": "ANOMALOUS", "anomaly": anomaly_outputs[0]["anomaly"]["3"]},
    ]
    assert outcomes[1]["evaluations"] == [
        {"level": 1, "result": "NORMAL"},
        {"level": 2, "result": "NORMAL"},
        {"level": 3, "result": "NORMAL"},
    ]
    assert outcomes[0]["record"]["data_raw"] == records[0]
    assert outcomes[0]["record"]["data_raw"] is not records[0]
    assert outcomes[0]["input_id"] == derive_input_id(
        tenant_id="default",
        purpose="DETECT",
        strategy_id="1",
        item_id="2",
        strategy_content_sha256=strategy_ir["strategy_ref"]["content_sha256"],
        record_id=records[0]["record_id"],
    )
    assert records == original_records
    assert anomaly_outputs == original_outputs


def test_project_detection_outcomes_rejects_anomaly_for_unaccepted_record():
    strategy_ir = _strategy_ir()
    records = [{"record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.100", "time": 100}]
    unexpected_record_id = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.110"

    with pytest.raises(ValueError, match="unaccepted record"):
        project_detection_outcomes(
            strategy_ir=strategy_ir,
            batch_id="batch-1",
            data_points=records,
            anomaly_outputs=[
                {
                    "data": {"record_id": unexpected_record_id, "time": 110},
                    "anomaly": {"1": {"anomaly_id": f"{unexpected_record_id}.1.2.1"}},
                }
            ],
        )


@pytest.mark.parametrize("anomalies", [{}, {"1": None}, {"1": "not-an-object"}])
def test_project_detection_outcomes_rejects_invalid_anomaly_payload(anomalies):
    record = {"record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.100", "time": 100}

    with pytest.raises(ContractValidationError, match="anomaly"):
        project_detection_outcomes(
            strategy_ir=_strategy_ir(),
            batch_id="batch-1",
            data_points=[record],
            anomaly_outputs=[{"data": record, "anomaly": anomalies}],
        )


def test_project_detection_outcomes_rejects_output_data_drift():
    record = {"record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.100", "time": 100, "value": 1}
    drifted_record = {**record, "value": 999}

    with pytest.raises(ContractValidationError, match="does not match accepted data"):
        project_detection_outcomes(
            strategy_ir=_strategy_ir(),
            batch_id="batch-1",
            data_points=[record],
            anomaly_outputs=[
                {
                    "data": drifted_record,
                    "anomaly": {"1": {"anomaly_id": f"{record['record_id']}.1.2.1"}},
                }
            ],
        )


def test_project_detection_outcomes_rejects_non_string_level_key():
    record = {"record_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.100", "time": 100}

    with pytest.raises(ContractValidationError, match="level keys must be strings"):
        project_detection_outcomes(
            strategy_ir=_strategy_ir(),
            batch_id="batch-1",
            data_points=[record],
            anomaly_outputs=[
                {
                    "data": record,
                    "anomaly": {
                        "1": {"anomaly_id": f"{record['record_id']}.1.2.1"},
                        4: {"anomaly_id": f"{record['record_id']}.1.2.4"},
                    },
                }
            ],
        )


def test_prepare_finalized_threshold_batch_uses_exact_strategy_snapshot():
    legacy_json = json.dumps(DETECT_STRATEGY).encode()
    record = copy.deepcopy(DETECT_RECORDS[0])
    anomaly_output = {
        "data": record,
        "anomaly": {
            "3": {
                "anomaly_id": f"{record['record_id']}.1.2.3",
                "anomaly_message": "threshold matched",
            }
        },
    }

    batch = prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=DETECT_STRATEGY,
        item_id=2,
        legacy_json=legacy_json,
        batch_id="batch-1",
        data_points=[record],
        anomaly_outputs=[anomaly_output],
        finalized=True,
    )

    assert batch["strategy_ir"]["legacy_json_b64"]
    assert batch["strategy_ir"]["strategy_ref"]["generation"] == str(DETECT_STRATEGY["update_time"])
    assert batch["outcomes"][0]["outcome"] == "ANOMALOUS"


@pytest.mark.parametrize("finalized", [False, None, 0, 1, "false", object()])
def test_prepare_finalized_threshold_batch_does_not_infer_normal_before_finalization(finalized):
    with pytest.raises(DetectionNotFinalized):
        prepare_finalized_threshold_batch(
            tenant_id="default",
            strategy=DETECT_STRATEGY,
            item_id=2,
            legacy_json=json.dumps(DETECT_STRATEGY).encode(),
            batch_id="batch-1",
            data_points=[copy.deepcopy(DETECT_RECORDS[1])],
            anomaly_outputs=[],
            finalized=finalized,
        )


def _strategy_ir():
    legacy_json = json.dumps({"id": 1, "items": [{"id": 2}]}, separators=(",", ":")).encode()
    return build_trigger_strategy_ir(
        tenant_id="default",
        purpose="DETECT",
        strategy_id=1,
        item_id=2,
        generation="1",
        legacy_json=legacy_json,
        check_window_unit_seconds=10,
        trigger_configs={
            1: {"check_window_size": 3, "trigger_count": 2},
            2: {"check_window_size": 3, "trigger_count": 2},
            3: {"check_window_size": 3, "trigger_count": 2},
        },
    )
