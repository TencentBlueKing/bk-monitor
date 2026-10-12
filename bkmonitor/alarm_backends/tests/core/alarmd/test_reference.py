"""Tests for the actual Python Trigger ABNORMAL Shadow reference."""

import copy
import json

import pytest

from alarm_backends.core.alarmd.contract import ContractValidationError
from alarm_backends.core.alarmd.reference import build_reference_trigger_decision_candidate
from alarm_backends.tests.alarmd_fixtures import TRIGGER_POINT, TRIGGER_STRATEGY


def _legacy_bytes(strategy):
    return json.dumps(strategy, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _triggered_event(point):
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


def _build_reference(*, point=None, strategy=None, event_record=None):
    point = point or copy.deepcopy(TRIGGER_POINT)
    strategy = strategy or copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    return build_reference_trigger_decision_candidate(
        strategy=strategy,
        legacy_json=_legacy_bytes(strategy),
        strategy_snapshot_key=point["strategy_snapshot_key"],
        tenant_id_resolver=lambda _bk_biz_id: "default",
        item_id=1,
        point=point,
        event_record=event_record if event_record is not None else _triggered_event(point),
    )


def test_reference_projects_only_actual_trigger_as_abnormal():
    point = copy.deepcopy(TRIGGER_POINT)
    first = _build_reference(point=point)
    retry = _build_reference(point=point)

    assert first == retry
    decision = first["decisions"][0]
    assert decision["outcome"] == "TRIGGER"
    assert decision["reason_code"] == "TRIGGER_CONDITION_MET"
    assert decision["level"] == 3
    assert decision["anomaly_timestamps"] == [point["data"]["time"]]


def test_reference_rejects_missing_trigger_event():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480

    with pytest.raises(ContractValidationError, match="actual Trigger event"):
        build_reference_trigger_decision_candidate(
            strategy=strategy,
            legacy_json=_legacy_bytes(strategy),
            strategy_snapshot_key=point["strategy_snapshot_key"],
            tenant_id_resolver=lambda _bk_biz_id: "default",
            item_id=1,
            point=point,
            event_record=None,
        )


def test_reference_rejects_snapshot_or_event_identity_drift():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480

    with pytest.raises(ContractValidationError, match="exact strategy snapshot"):
        build_reference_trigger_decision_candidate(
            strategy=strategy,
            legacy_json=_legacy_bytes(strategy),
            strategy_snapshot_key="another-snapshot",
            tenant_id_resolver=lambda _bk_biz_id: "default",
            item_id=1,
            point=point,
            event_record=_triggered_event(point),
        )

    stale_event = _triggered_event(point)
    stale_event["data"]["value"] = 999
    with pytest.raises(ContractValidationError, match="event_record data"):
        _build_reference(point=point, strategy=strategy, event_record=stale_event)


def test_reference_rejects_invalid_anomaly_payload():
    point = copy.deepcopy(TRIGGER_POINT)
    point["anomaly"]["1"] = None

    with pytest.raises(ContractValidationError, match="object"):
        _build_reference(point=point, event_record=_triggered_event(point))
