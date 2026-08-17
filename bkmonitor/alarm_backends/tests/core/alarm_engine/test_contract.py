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

import pytest

from alarm_backends.core.alarm_engine.contract import (
    ContractValidationError,
    build_detection_outcome,
    build_trigger_strategy_ir,
    build_trigger_strategy_ir_from_legacy_config,
    can_drive_trigger,
    derive_input_id,
    validate_detection_outcome,
    validate_trigger_strategy_ir,
)
from alarm_backends.core.alarm_engine.encoder import decode_json_document, encode_json_document


LEGACY_JSON = b'{"id":1,"update_time":1569246480}'
LEGACY_JSON_SHA256 = "8a340c044a560d3410cd4d53098151eac966b8321a5ad01b43547b05f960e2c3"
DIMENSIONS_MD5 = "55a76cf628e46c04a052f4e19bdb9dbf"
SOURCE_TIME = 1569246480
RECORD_ID = f"{DIMENSIONS_MD5}.{SOURCE_TIME}"
EXPECTED_INPUT_ID = "2c82173befc4a450616df467cfd27d903ac5417e44413c7144780dfe43a8ef44"


def make_strategy_ir():
    return build_trigger_strategy_ir(
        tenant_id="default",
        purpose="DETECT",
        strategy_id=1,
        item_id=1,
        generation="1569246480",
        legacy_json=LEGACY_JSON,
        check_window_unit_seconds=60,
        trigger_configs={
            1: {"check_window_size": 5, "trigger_count": 3},
            2: {"check_window_size": 5, "trigger_count": 2},
            3: {"check_window_size": 5, "trigger_count": 1},
        },
    )


def make_data_raw():
    return {
        "record_id": RECORD_ID,
        "value": 1.38,
        "values": {"timestamp": SOURCE_TIME, "huge_counter": 9007199254740993},
        "dimensions": {"ip": "10.0.0.1", "mixed": 7},
        "time": SOURCE_TIME,
    }


def normal_evaluations():
    return [{"level": level, "result": "NORMAL"} for level in (1, 2, 3)]


def anomalous_evaluations():
    return [
        {
            "level": level,
            "result": "ANOMALOUS",
            "anomaly": {
                "anomaly_id": f"{RECORD_ID}.1.1.{level}",
                "anomaly_message": "异常测试",
                "context": {"level": level, "mixed": [1, "2", {"nested": True}]},
            },
        }
        for level in (1, 2, 3)
    ]


def build_outcome(*, outcome="NORMAL", evaluations=None, error_code=None, batch_id="batch-1"):
    return build_detection_outcome(
        strategy_ir=make_strategy_ir(),
        batch_id=batch_id,
        data_raw=make_data_raw(),
        evaluations=normal_evaluations() if evaluations is None else evaluations,
        outcome=outcome,
        error_code=error_code,
    )


def test_input_id_uses_frozen_length_prefixed_tuple():
    input_id = derive_input_id(
        tenant_id="default",
        purpose="DETECT",
        strategy_id=1,
        item_id=1,
        strategy_content_sha256=LEGACY_JSON_SHA256,
        record_id=RECORD_ID,
    )

    assert input_id == EXPECTED_INPUT_ID


def test_input_id_uses_utf8_byte_length_and_rejects_invalid_surrogate():
    fields = {
        "tenant_id": "租户",
        "purpose": "DETECT",
        "strategy_id": 1,
        "item_id": 1,
        "strategy_content_sha256": LEGACY_JSON_SHA256,
        "record_id": RECORD_ID,
    }

    assert derive_input_id(**fields) == "4b25f5e001820e6de39c45a27bf65b27b665d542009d3a004a73ee1629f014d7"
    fields["tenant_id"] = "\ud800"
    with pytest.raises(ContractValidationError, match="UTF-8"):
        derive_input_id(**fields)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("purpose", "detect"),
        ("strategy_id", "01"),
        ("item_id", "+1"),
        ("strategy_content_sha256", LEGACY_JSON_SHA256.upper()),
        ("record_id", f"{DIMENSIONS_MD5}.01569246480"),
    ],
)
def test_input_id_rejects_noncanonical_fields(field, value):
    fields = {
        "tenant_id": "default",
        "purpose": "DETECT",
        "strategy_id": 1,
        "item_id": 1,
        "strategy_content_sha256": LEGACY_JSON_SHA256,
        "record_id": RECORD_ID,
    }
    fields[field] = value

    with pytest.raises(ContractValidationError):
        derive_input_id(**fields)


def test_strategy_ir_preserves_legacy_bytes_and_normalizes_trigger_levels():
    strategy_ir = make_strategy_ir()

    validate_trigger_strategy_ir(strategy_ir)
    assert strategy_ir["required_levels"] == [1, 2, 3]
    assert [config["level"] for config in strategy_ir["trigger_configs"]] == [1, 2, 3]
    assert strategy_ir["strategy_ref"]["content_sha256"] == LEGACY_JSON_SHA256
    assert base64.b64decode(strategy_ir["legacy_json_b64"], validate=True) == LEGACY_JSON


def test_strategy_ir_rejects_features_owned_by_another_contract():
    strategy_ir = make_strategy_ir()
    strategy_ir["required_features"].append("raw-json-v1")

    with pytest.raises(ContractValidationError, match="unsupported required feature"):
        validate_trigger_strategy_ir(strategy_ir)


def test_typed_contract_integers_are_bounded_to_int32():
    strategy_ir = make_strategy_ir()
    strategy_ir["schema"]["minor"] = 2**31
    with pytest.raises(ContractValidationError, match="32-bit"):
        validate_trigger_strategy_ir(strategy_ir)

    for mutate in (
        lambda value: value.update(check_window_unit_seconds=2**31),
        lambda value: value["trigger_configs"][0].update(trigger_count=2**31),
        lambda value: (
            value["required_levels"].__setitem__(0, 2**31),
            value["trigger_configs"][0].update(level=2**31),
        ),
    ):
        strategy_ir = make_strategy_ir()
        mutate(strategy_ir)
        with pytest.raises(ContractValidationError, match="32-bit|positive"):
            validate_trigger_strategy_ir(strategy_ir)

    strategy_ir = make_strategy_ir()
    strategy_ir["schema"]["minor"] = 2**31 - 1
    strategy_ir["check_window_unit_seconds"] = 2**31 - 1
    strategy_ir["required_levels"] = [2**31 - 1]
    strategy_ir["trigger_configs"] = [
        {
            "level": 2**31 - 1,
            "check_window_size": 2**31 - 1,
            "trigger_count": 2**31 - 1,
        }
    ]
    validate_trigger_strategy_ir(strategy_ir)

    outcome = build_outcome()
    outcome["evaluations"][0]["level"] = 2**31
    with pytest.raises(ContractValidationError, match="32-bit"):
        validate_detection_outcome(outcome, make_strategy_ir())

    strategy_ir = make_strategy_ir()
    strategy_ir["trigger_configs"][0]["check_window_size"] = 2**31
    with pytest.raises(ContractValidationError, match="32-bit"):
        validate_trigger_strategy_ir(strategy_ir)


def test_normal_and_anomalous_outcomes_require_complete_levels():
    normal = build_outcome()
    anomalous = build_outcome(outcome="ANOMALOUS", evaluations=anomalous_evaluations())

    validate_detection_outcome(normal, make_strategy_ir())
    validate_detection_outcome(anomalous, make_strategy_ir())
    assert can_drive_trigger(normal, make_strategy_ir()) is True
    assert can_drive_trigger(anomalous, make_strategy_ir()) is True

    incomplete = copy.deepcopy(normal)
    incomplete["evaluations"].pop()
    with pytest.raises(ContractValidationError, match="complete"):
        validate_detection_outcome(incomplete, make_strategy_ir())


def test_error_and_unsupported_allow_only_required_level_subsets():
    partial_error = build_outcome(
        outcome="ERROR",
        evaluations=[{"level": 1, "result": "NORMAL"}],
        error_code="ALGORITHM_ERROR",
    )
    unsupported = build_outcome(
        outcome="UNSUPPORTED",
        evaluations=[],
        error_code="UNSUPPORTED_STRATEGY",
    )

    validate_detection_outcome(partial_error, make_strategy_ir())
    validate_detection_outcome(unsupported, make_strategy_ir())
    assert can_drive_trigger(partial_error, make_strategy_ir()) is False
    assert can_drive_trigger(unsupported, make_strategy_ir()) is False

    duplicate = copy.deepcopy(partial_error)
    duplicate["evaluations"].append(copy.deepcopy(duplicate["evaluations"][0]))
    with pytest.raises(ContractValidationError, match="duplicate"):
        validate_detection_outcome(duplicate, make_strategy_ir())

    missing = copy.deepcopy(unsupported)
    missing.pop("evaluations")
    explicit_null = copy.deepcopy(unsupported)
    explicit_null["evaluations"] = None
    for invalid in (missing, explicit_null):
        with pytest.raises(ContractValidationError, match="evaluations"):
            validate_detection_outcome(invalid, make_strategy_ir())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["record"].update(record_id=f"{DIMENSIONS_MD5}.1569246481"),
        lambda value: value["record"]["data_raw"].update(time=1569246481),
        lambda value: value["strategy_ref"].update(item_id="2"),
        lambda value: value.update(input_id="0" * 64),
    ],
)
def test_outcome_rejects_cross_field_mismatches(mutate):
    outcome = build_outcome()
    mutate(outcome)

    with pytest.raises(ContractValidationError):
        validate_detection_outcome(outcome, make_strategy_ir())


def test_evaluation_anomaly_invariants_are_fail_closed():
    normal_with_anomaly = normal_evaluations()
    normal_with_anomaly[0]["anomaly"] = anomalous_evaluations()[0]["anomaly"]
    with pytest.raises(ContractValidationError, match="NORMAL"):
        build_outcome(evaluations=normal_with_anomaly)

    anomalous_without_payload = anomalous_evaluations()
    anomalous_without_payload[0].pop("anomaly")
    with pytest.raises(ContractValidationError, match="ANOMALOUS"):
        build_outcome(outcome="ANOMALOUS", evaluations=anomalous_without_payload)

    explicit_null = build_outcome()
    explicit_null["evaluations"][0]["anomaly"] = None
    with pytest.raises(ContractValidationError, match="NORMAL"):
        validate_detection_outcome(explicit_null, make_strategy_ir())


def test_unknown_major_feature_and_business_enum_are_rejected():
    cases = []
    unknown_major = build_outcome()
    unknown_major["schema"]["major"] = 2
    cases.append(unknown_major)
    unknown_feature = build_outcome()
    unknown_feature["required_features"].append("future-required-feature")
    cases.append(unknown_feature)
    unknown_outcome = build_outcome()
    unknown_outcome["outcome"] = "DEFERRED"
    cases.append(unknown_outcome)

    for case in cases:
        with pytest.raises(ContractValidationError):
            validate_detection_outcome(case, make_strategy_ir())

    boolean_major = build_outcome()
    boolean_major["schema"]["major"] = True
    unhashable_purpose = build_outcome()
    unhashable_purpose["purpose"] = []
    unhashable_result = build_outcome()
    unhashable_result["evaluations"][0]["result"] = []
    for case in (boolean_major, unhashable_purpose, unhashable_result):
        with pytest.raises(ContractValidationError):
            validate_detection_outcome(case, make_strategy_ir())


def test_business_outcome_rejects_explicit_null_error_code():
    outcome = build_outcome()
    outcome["error_code"] = None

    with pytest.raises(ContractValidationError, match="error_code"):
        validate_detection_outcome(outcome, make_strategy_ir())


def test_higher_minor_ignores_unknown_optional_fields_when_features_are_supported():
    outcome = build_outcome()
    outcome["schema"]["minor"] = 1
    outcome["future_optional_diagnostic"] = {"ignored": True}

    validate_detection_outcome(outcome, make_strategy_ir())


@pytest.mark.parametrize("field", ["future_optional_diagnostic", "Schema"])
def test_v1_rejects_unknown_or_case_colliding_fixed_fields(field):
    outcome = build_outcome()
    outcome[field] = {"ignored": True}

    with pytest.raises(ContractValidationError, match="field"):
        validate_detection_outcome(outcome, make_strategy_ir())


def test_json_encoder_preserves_large_integers_and_rejects_nonfinite_numbers():
    outcome = build_outcome(outcome="ANOMALOUS", evaluations=anomalous_evaluations())

    decoded = decode_json_document(encode_json_document(outcome))
    assert decoded == outcome
    assert decoded["record"]["data_raw"]["values"]["huge_counter"] == 9007199254740993

    outcome["record"]["data_raw"]["value"] = float("nan")
    with pytest.raises(ValueError):
        encode_json_document(outcome)


def test_json_decoder_rejects_duplicate_fields_and_nonfinite_numbers():
    with pytest.raises(ContractValidationError, match="duplicate"):
        decode_json_document(b'{"input_id":"first","input_id":"second"}')
    with pytest.raises(ContractValidationError, match="non-finite"):
        decode_json_document(b'{"value":NaN}')
    with pytest.raises(ContractValidationError, match="non-finite"):
        decode_json_document(b'{"value":1e400}')


def test_json_codec_rejects_nonstring_keys_surrogates_and_bom():
    with pytest.raises(ContractValidationError, match="keys must be strings"):
        encode_json_document({"raw": {1: "numeric-key"}})
    with pytest.raises(ContractValidationError, match="UTF-8"):
        encode_json_document({"raw": "\ud800"})
    with pytest.raises(ContractValidationError, match="UTF-8"):
        decode_json_document(b'{"raw":"\\ud800"}')
    with pytest.raises(ContractValidationError, match="BOM"):
        decode_json_document(b'\xef\xbb\xbf{"raw":true}')

    valid = {"raw": "\ufffd😀"}
    assert decode_json_document(encode_json_document(valid)) == valid


def test_strategy_ir_rejects_ambiguous_or_nonfinite_legacy_json():
    for legacy_json in (b'{"id":1,"id":2}', b'{"value":NaN}', b"null", b'\xef\xbb\xbf{"id":1}'):
        with pytest.raises(ContractValidationError):
            build_trigger_strategy_ir(
                tenant_id="default",
                purpose="DETECT",
                strategy_id=1,
                item_id=1,
                generation="1",
                legacy_json=legacy_json,
                check_window_unit_seconds=60,
                trigger_configs={1: {"check_window_size": 1, "trigger_count": 1}},
            )


def test_record_source_coordinates_reject_boolean_timestamps():
    data_raw = make_data_raw()
    data_raw["record_id"] = f"{DIMENSIONS_MD5}.1"
    data_raw["time"] = True
    data_raw["values"]["timestamp"] = True

    with pytest.raises(ContractValidationError):
        build_detection_outcome(
            strategy_ir=make_strategy_ir(),
            batch_id="batch-1",
            data_raw=data_raw,
            evaluations=normal_evaluations(),
            outcome="NORMAL",
        )


@pytest.mark.parametrize("values", [[1, "2"], "opaque", 7])
def test_record_values_remain_open_raw_json(values):
    data_raw = make_data_raw()
    data_raw["values"] = values

    outcome = build_detection_outcome(
        strategy_ir=make_strategy_ir(),
        batch_id="batch-1",
        data_raw=data_raw,
        evaluations=normal_evaluations(),
        outcome="NORMAL",
    )

    assert outcome["record"]["data_raw"]["values"] == values


def test_contract_builders_reject_wrong_container_types_with_validation_error():
    with pytest.raises(ContractValidationError):
        build_trigger_strategy_ir(
            tenant_id="default",
            purpose="DETECT",
            strategy_id=1,
            item_id=1,
            generation="1",
            legacy_json=b'{"id":1}',
            check_window_unit_seconds=60,
            trigger_configs=[],
        )


def test_retry_changes_batch_id_but_not_input_id():
    first = build_outcome(batch_id="batch-1")
    retry = build_outcome(batch_id="batch-retry-2")

    assert first["batch_id"] != retry["batch_id"]
    assert first["input_id"] == retry["input_id"] == EXPECTED_INPUT_ID


def test_strategy_ir_adapter_uses_threshold_strategy_semantics_without_reencoding_legacy_json():
    # Reduced from the current three-level Trigger fixture in service/trigger/test_checker.py.
    strategy = {
        "id": 1,
        "update_time": SOURCE_TIME,
        "items": [
            {
                "id": 1,
                "query_configs": [{"agg_interval": 60}],
                "algorithms": [
                    {"level": 1, "type": "Threshold"},
                    {"level": 2, "type": "Threshold"},
                    {"level": 3, "type": "Threshold"},
                ],
                "no_data_config": {"is_enabled": False},
            }
        ],
        "detects": [
            {"level": 1, "trigger_config": {"count": 3, "check_window": 5}},
            {"level": 2, "trigger_config": {"count": 2, "check_window": 5}},
            {"level": 3, "trigger_config": {"count": 1, "check_window": 5}},
        ],
    }
    legacy_json = b'{ "update_time": 1569246480, "id": 1, "items": [{"id": 1, "query_configs": [{"agg_interval": 60}], "algorithms": [{"level": 1, "type": "Threshold"}, {"level": 2, "type": "Threshold"}, {"level": 3, "type": "Threshold"}], "no_data_config": {"is_enabled": false}}], "detects": [{"level": 1, "trigger_config": {"count": 3, "check_window": 5}}, {"level": 2, "trigger_config": {"count": 2, "check_window": 5}}, {"level": 3, "trigger_config": {"count": 1, "check_window": 5}}] }'

    strategy_ir = build_trigger_strategy_ir_from_legacy_config(
        tenant_id="default",
        purpose="DETECT",
        strategy=strategy,
        item_id=1,
        legacy_json=legacy_json,
    )

    assert strategy_ir["required_levels"] == [1, 2, 3]
    assert strategy_ir["check_window_unit_seconds"] == 60
    assert [config["trigger_count"] for config in strategy_ir["trigger_configs"]] == [3, 2, 1]
    assert base64.b64decode(strategy_ir["legacy_json_b64"], validate=True) == legacy_json


def test_strategy_ir_adapter_rejects_boolean_integer_type_drift():
    strategy = {
        "id": 1,
        "update_time": SOURCE_TIME,
        "items": [
            {
                "id": 1,
                "query_configs": [{"agg_interval": 60}],
                "algorithms": [{"level": 1, "type": "Threshold"}],
                "no_data_config": {"is_enabled": False},
            }
        ],
        "detects": [{"level": 1, "trigger_config": {"count": 1, "check_window": 5}}],
    }
    legacy_json = encode_json_document({**strategy, "id": True})

    with pytest.raises(ContractValidationError, match="semantic drift"):
        build_trigger_strategy_ir_from_legacy_config(
            tenant_id="default",
            purpose="DETECT",
            strategy=strategy,
            item_id=1,
            legacy_json=legacy_json,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda strategy: strategy["items"][0]["algorithms"][0].update(type="IntelligentDetect"),
        lambda strategy: strategy["items"][0]["no_data_config"].update(is_enabled=True),
        lambda strategy: strategy["detects"][0]["trigger_config"].update(uptime={"time_ranges": []}),
    ],
)
def test_strategy_ir_adapter_rejects_features_outside_first_threshold_slice(mutate):
    strategy = {
        "id": 1,
        "update_time": SOURCE_TIME,
        "items": [
            {
                "id": 1,
                "query_configs": [{"agg_interval": 60}],
                "algorithms": [{"level": 1, "type": "Threshold"}],
                "no_data_config": {"is_enabled": False},
            }
        ],
        "detects": [{"level": 1, "trigger_config": {"count": 1, "check_window": 5}}],
    }
    mutate(strategy)
    legacy_json = encode_json_document(strategy)

    with pytest.raises(ContractValidationError, match="unsupported"):
        build_trigger_strategy_ir_from_legacy_config(
            tenant_id="default",
            purpose="DETECT",
            strategy=strategy,
            item_id=1,
            legacy_json=legacy_json,
        )
