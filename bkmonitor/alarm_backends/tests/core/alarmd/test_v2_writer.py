import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

from alarm_backends.core.alarmd import contract, v2_writer
from alarm_backends.core.alarmd.encoder import decode_json_document
from alarm_backends.core.alarmd.v2_writer import (
    AccessPublishJob,
    BoundedAccessShadowPublisher,
    REASON_RECORD_TOO_LARGE,
    build_execution_messages,
    canonical_json_v2,
    derive_dimension_identity_digest_v2,
    derive_execution_payload_digest_v2,
    derive_plan_set_digest_v2,
    derive_record_id_v2,
)


M0_COMMIT = "6e65c0f9"
M0_GOLDEN = "pkg/alarmd/contract/testdata/go-v2"
TRIGGER_EVENT_FIELDS = set(
    "schema required_features event_id tenant_id business_id plan_ref record_ref evaluation_time event_kind "
    "primary_level_id level_results observed trace detect_plan_fingerprint trigger_state_fingerprint "
    "event_semantic_digest".split()
)
RECEIPT_FIELDS = set(
    "schema required_features receipt_id execution_id message_id payload_digest plan_set_digest source_window "
    "status counts per_plan reason_counts".split()
)
RECEIPT_COUNT_FIELDS = set("received selected processed unavailable terminal level_terminal_affected events".split())
PLAN_RECEIPT_FIELDS = set(
    "plan_id selected abnormal normal recovery unavailable terminal level_terminal_affected result_identity_digest".split()
)
PLAN_RECEIPT_COUNT_FIELDS = set(
    "selected abnormal normal recovery unavailable terminal level_terminal_affected".split()
)


def _read_m0_golden(name: str) -> dict:
    local_payload = (Path(__file__).parent / "testdata" / "m0-go-v2" / name).read_bytes()
    repo = os.getenv("BKMONITOR_DATALINK_REPO")
    if repo:
        source_payload = subprocess.check_output(
            ["git", "show", f"{M0_COMMIT}:{M0_GOLDEN}/{name}"],
            cwd=Path(repo),
        )
        assert local_payload == source_payload
    return decode_json_document(local_payload)


def _exact_fields(value, path: str, fields: set[str]):
    return contract._validate_fixed_fields(value, path, required=fields)


def _strict_verify_trigger_event_v1(document: dict) -> None:
    _exact_fields(document, "trigger_event", TRIGGER_EVENT_FIELDS)
    if contract._validate_header(document, name="trigger-event", required_features=set()) != 0:
        raise contract.ContractValidationError("trigger_event schema must be 1.0")
    results = document["level_results"]
    if not isinstance(results, list) or not results:
        raise contract.ContractValidationError("trigger_event.level_results must be non-empty")
    previous_level_id = 0
    for result in results:
        level_id, priority, outcome = result["level_id"], result["priority"], result["result"]
        if (
            type(level_id) is not int
            or level_id <= previous_level_id
            or type(priority) is not int
            or priority <= 0
            or outcome not in {"NORMAL", "ABNORMAL", "RECOVERY"}
        ):
            raise contract.ContractValidationError("trigger_event Level results are invalid or unsorted")
        previous_level_id = level_id
    event_kind = "ABNORMAL" if any(result["result"] == "ABNORMAL" for result in results) else "RECOVERY"
    candidates = [result for result in results if result["result"] == event_kind]
    if not candidates or document["event_kind"] != event_kind:
        raise contract.ContractValidationError("trigger_event event_kind does not match Level results")
    primary = min(candidates, key=lambda result: (result["priority"], result["level_id"]))["level_id"]
    if document["primary_level_id"] != primary:
        raise contract.ContractValidationError("trigger_event dynamic Level or primary result mismatch")


def _strict_verify_message_receipt_v1(document: dict) -> None:
    _exact_fields(document, "message_receipt", RECEIPT_FIELDS)
    if contract._validate_header(document, name="message-receipt", required_features=set()) != 0:
        raise contract.ContractValidationError("message_receipt schema must be 1.0")
    counts = _exact_fields(document["counts"], "message_receipt.counts", RECEIPT_COUNT_FIELDS)
    if any(type(counts[field]) is not int or counts[field] < 0 for field in RECEIPT_COUNT_FIELDS):
        raise contract.ContractValidationError("message_receipt counts must be non-negative integers")
    if not isinstance(document["per_plan"], list) or not isinstance(document["reason_counts"], list):
        raise contract.ContractValidationError("message_receipt per_plan and reason_counts must be arrays")
    if document["status"] == "REJECTED":
        if any(counts.values()) or document["per_plan"] or not document["reason_counts"]:
            raise contract.ContractValidationError(
                "REJECTED message_receipt must have zero counts, no plans and a reason"
            )
        return
    totals = {field: 0 for field in RECEIPT_COUNT_FIELDS if field != "received"}
    for index, plan in enumerate(document["per_plan"]):
        plan = _exact_fields(plan, f"message_receipt.per_plan[{index}]", PLAN_RECEIPT_FIELDS)
        if any(type(plan[field]) is not int or plan[field] < 0 for field in PLAN_RECEIPT_COUNT_FIELDS):
            raise contract.ContractValidationError("message_receipt per_plan counts must be non-negative integers")
        processed = plan["abnormal"] + plan["normal"] + plan["recovery"]
        if plan["selected"] != processed + plan["unavailable"] + plan["terminal"]:
            raise contract.ContractValidationError("message_receipt per_plan selected does not balance")
        if plan["selected"] > counts["received"]:
            raise contract.ContractValidationError("message_receipt per_plan selected exceeds received")
        if plan["level_terminal_affected"] > processed:
            raise contract.ContractValidationError("message_receipt affected cannot exceed processed")
        for field, value in {
            "selected": plan["selected"],
            "processed": processed,
            "unavailable": plan["unavailable"],
            "terminal": plan["terminal"],
            "level_terminal_affected": plan["level_terminal_affected"],
            "events": plan["abnormal"] + plan["recovery"],
        }.items():
            totals[field] += value
    if any(counts[field] != total for field, total in totals.items()):
        raise contract.ContractValidationError("message_receipt counts do not match per_plan totals")
    expected_status = (
        "COMPLETED_WITH_TERMINAL" if counts["terminal"] or counts["level_terminal_affected"] else "COMPLETED"
    )
    if document["status"] != expected_status:
        raise contract.ContractValidationError("message_receipt status does not match terminal counts")


def test_cross_reads_m0_go_canonical_and_envelope_golden():
    vectors = _read_m0_golden("canonical_vectors.json")
    identity = vectors["dimension_identity"]
    digest = derive_dimension_identity_digest_v2(identity["tenant_id"], identity["business_id"], identity["fields"])
    assert digest == identity["digest"]
    assert derive_record_id_v2(digest, identity["source_time"]) == identity["record_id"]

    negative = vectors["negative_business_identity"]
    negative_digest = derive_dimension_identity_digest_v2(
        negative["tenant_id"], negative["business_id"], negative["fields"]
    )
    assert negative_digest == negative["digest"]
    assert derive_record_id_v2(negative_digest, negative["source_time"]) == negative["record_id"]

    envelope = _read_m0_golden("execution_envelope_v2.json")
    assert derive_plan_set_digest_v2(envelope["plan_set"]) == envelope["plan_set"]["plan_set_digest"]
    assert derive_execution_payload_digest_v2(envelope) == envelope["payload_digest"]
    assert (
        canonical_json_v2(envelope)
        == json.dumps(envelope, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    )


def test_cross_reads_m0_go_trigger_event_and_mixed_level_receipt():
    event = _read_m0_golden("trigger_event_v1.json")
    _strict_verify_trigger_event_v1(event)
    assert event["event_kind"] == "ABNORMAL"
    assert event["primary_level_id"] == 5
    assert {result["level_id"]: result["result"] for result in event["level_results"]} == {1: "NORMAL", 5: "ABNORMAL"}

    receipt = _read_m0_golden("message_receipt_mixed_level_v1.json")
    _strict_verify_message_receipt_v1(receipt)
    assert receipt["status"] == "COMPLETED_WITH_TERMINAL"
    assert receipt["counts"]["processed"] == receipt["counts"]["level_terminal_affected"] == 1
    assert receipt["per_plan"][0]["level_terminal_affected"] == 1


def test_go_output_verifiers_reject_unknown_and_missing_fields():
    event = copy.deepcopy(_read_m0_golden("trigger_event_v1.json"))
    event["future"] = True
    with pytest.raises(contract.ContractValidationError, match="unknown field"):
        _strict_verify_trigger_event_v1(event)

    receipt = copy.deepcopy(_read_m0_golden("message_receipt_mixed_level_v1.json"))
    del receipt["counts"]["level_terminal_affected"]
    with pytest.raises(contract.ContractValidationError, match="missing required field"):
        _strict_verify_message_receipt_v1(receipt)

    receipt = copy.deepcopy(_read_m0_golden("message_receipt_mixed_level_v1.json"))
    receipt["counts"]["level_terminal_affected"] = 2
    receipt["per_plan"][0]["level_terminal_affected"] = 2
    with pytest.raises(contract.ContractValidationError, match="cannot exceed processed"):
        _strict_verify_message_receipt_v1(receipt)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda event: event.update(event_kind="NORMAL"),
        lambda event: event["level_results"][0].update(result="UNAVAILABLE"),
        lambda event: (event["level_results"][0].update(result="ABNORMAL"), event.update(primary_level_id=1)),
        lambda event: event["level_results"][0].update(result="ABNORMAL", priority=1),
        lambda event: event["level_results"].reverse(),
    ],
)
def test_trigger_event_verifier_rejects_invalid_aggregate_semantics(mutate):
    event = copy.deepcopy(_read_m0_golden("trigger_event_v1.json"))
    mutate(event)
    with pytest.raises(contract.ContractValidationError):
        _strict_verify_trigger_event_v1(event)


@pytest.mark.parametrize(("normal", "abnormal"), [(-1, 2), (True, 0)])
def test_receipt_verifier_rejects_invalid_plan_count(normal, abnormal):
    receipt = copy.deepcopy(_read_m0_golden("message_receipt_mixed_level_v1.json"))
    receipt["per_plan"][0].update(normal=normal, abnormal=abnormal)
    with pytest.raises(contract.ContractValidationError, match="non-negative integers"):
        _strict_verify_message_receipt_v1(receipt)


def test_receipt_verifier_enforces_selected_and_rejected_semantics():
    base = _read_m0_golden("message_receipt_mixed_level_v1.json")
    exceeds_received = copy.deepcopy(base)
    exceeds_received["counts"]["received"] = 0
    with pytest.raises(contract.ContractValidationError, match="exceeds received"):
        _strict_verify_message_receipt_v1(exceeds_received)

    rejected = copy.deepcopy(base)
    rejected["status"] = "REJECTED"
    rejected["counts"] = {field: 0 for field in RECEIPT_COUNT_FIELDS}
    rejected["per_plan"] = []
    rejected["reason_counts"] = [{"reason_code": "MALFORMED_JSON", "count": 1}]
    _strict_verify_message_receipt_v1(rejected)

    rejected["reason_counts"] = []
    with pytest.raises(contract.ContractValidationError, match="REJECTED"):
        _strict_verify_message_receipt_v1(rejected)


def _job(record_count=3, *, first_host_size=0):
    plan = {
        "plan_id": "1001",
        "strategy_ref": {"tenant_id": "default", "strategy_id": "1001", "revision": "r1"},
        "input_projection": {
            "value_fields": ["value"],
            "dimension_fields": ["host"],
            "business_identity_field": "bk_biz_id",
            "multi_value_alignment": "SINGLE_VALUE",
            "data_unit": "%",
            "missing_value_policy": "REQUIRED_VALUE",
        },
        "strategy_ir": {
            "schema": {"name": "alarmd-strategy-ir", "major": 2, "minor": 0},
            "required_features": [],
            "strategy_ref": {"tenant_id": "default", "strategy_id": "1001", "revision": "r1"},
            "execution_semantics": {
                "evaluation_scope": "SERIES",
                "query_window": 300,
                "aggregation_interval": 60,
                "evaluation_interval": 60,
                "lateness_tolerance": 120,
            },
            "input_projection": {
                "value_fields": ["value"],
                "dimension_fields": ["host"],
                "business_identity_field": "bk_biz_id",
                "multi_value_alignment": "SINGLE_VALUE",
                "data_unit": "%",
                "missing_value_policy": "REQUIRED_VALUE",
            },
            "levels": [
                {
                    "definition": {"level_id": 5, "priority": 1},
                    "connector": "AND",
                    "detect_plan": {
                        "algorithms": [
                            {
                                "type": "Threshold",
                                "version": 1,
                                "config": {
                                    "value_field": "value",
                                    "data_unit": "%",
                                    "threshold_unit_prefix": "",
                                    "precision": {"decimal_places": 6, "rounding": "HALF_EVEN"},
                                    "groups": [{"conditions": [{"operator": "GT", "threshold_decimal": "1"}]}],
                                },
                            }
                        ]
                    },
                    "trigger_plan": {
                        "type": "N_OF_M",
                        "version": 1,
                        "config": {"required_anomalies": 1, "step_seconds": 60, "window_size": 1},
                    },
                    "recovery_plan": {
                        "type": "CONTINUOUS_TRIGGER_MISS",
                        "version": 1,
                        "config": {"consecutive_windows": 1, "enabled": True},
                    },
                }
            ],
        },
    }
    plan_set = {"plan_set_digest": "", "plan_count": 1, "evaluation_plans": [plan]}
    plan_set["plan_set_digest"] = derive_plan_set_digest_v2(plan_set)
    records = []
    for index in range(record_count):
        host = "x" * first_host_size if index == 0 and first_host_size else f"host-{index}"
        fields = [{"name": "host", "value": host}]
        digest = derive_dimension_identity_digest_v2("default", "2", fields)
        records.append(
            {
                "record_id": derive_record_id_v2(digest, 1725000000 + index),
                "source_time": 1725000000 + index,
                "business_id": "2",
                "dimension_identity": {"fields": fields, "digest": digest},
                "values": {"value": index},
                "dimensions": {"host": host},
                "received_time": 1725000060,
            }
        )
    return AccessPublishJob.create(
        execution_id="execution-1",
        tenant_id="default",
        query_group={
            "key": "query-group-1",
            "query_md5": "query-group-1",
            "query_revision": "query-r1",
            "evaluation_time": 1725000060,
        },
        source_window={"from_time": 1724999700, "until_time": 1725000060},
        query_result={"completeness": "FULL"},
        dataset_contract={
            "schema_digest": "1" * 64,
            "normalization_digest": "2" * 64,
            "identity_fields": ["host"],
            "source_time_field": "time",
            "received_time_field": "received_time",
        },
        plan_set=plan_set,
        records=records,
        selections=[[(index % 2) == 0 for index in range(record_count)]],
    )


def test_messages_keep_full_plan_set_and_rebase_selectors():
    job = _job()
    messages, drops = build_execution_messages(
        job,
        max_records=2,
        max_envelope_bytes=32 * 1024,
        message_id_factory=iter(["message-1", "message-2"]).__next__,
    )

    assert drops == []
    assert len(messages) == 2
    decoded = [json.loads(message.payload) for message in messages]
    assert decoded[0]["plan_set"] == decoded[1]["plan_set"]
    assert decoded[0]["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert decoded[1]["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert [len(message["records"]) for message in decoded] == [2, 1]
    assert all(derive_execution_payload_digest_v2(message) == message["payload_digest"] for message in decoded)


def test_single_oversized_record_isolated_without_dropping_sibling():
    messages, drops = build_execution_messages(
        _job(record_count=2, first_host_size=20_000),
        max_records=10,
        max_envelope_bytes=8 * 1024,
        message_id_factory=lambda: "message-1",
    )

    assert [(drop.record_ordinal, drop.reason_code) for drop in drops] == [(0, REASON_RECORD_TOO_LARGE)]
    assert len(messages) == 1
    envelope = json.loads(messages[0].payload)
    assert len(envelope["records"]) == 1
    assert envelope["records"][0]["dimensions"] == {"host": "host-1"}
    assert envelope["selectors"][0]["selector"]["ranges"] == []


def test_large_batch_planning_encodes_each_final_message_once(mocker):
    build_envelope = mocker.patch.object(v2_writer, "_build_envelope", wraps=v2_writer._build_envelope)

    messages, drops = build_execution_messages(
        _job(record_count=10_000),
        max_records=500,
        max_envelope_bytes=4 * 1024 * 1024,
    )

    assert drops == []
    assert len(messages) == 20
    assert build_envelope.call_count == len(messages) + 1


def test_bounded_queue_rejects_before_snapshot_and_releases_budget():
    release = __import__("threading").Event()
    started = __import__("threading").Event()

    def run_job(_job):
        started.set()
        release.wait(timeout=1)

    publisher = BoundedAccessShadowPublisher(
        max_jobs=1,
        max_records=3,
        max_bytes=100_000,
        run_job=run_job,
    )
    job = _job()
    assert publisher.submit(job, record_count=job.record_count, retained_bytes=job.retained_bytes)
    assert started.wait(timeout=1)

    rejected = _job(1)
    assert not publisher.submit(
        rejected,
        record_count=rejected.record_count,
        retained_bytes=rejected.retained_bytes,
    )

    release.set()
    assert publisher.wait_empty(timeout=1)
    assert publisher.submit(
        rejected,
        record_count=rejected.record_count,
        retained_bytes=rejected.retained_bytes,
    )
    assert publisher.close(timeout=1)
