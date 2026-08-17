from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import kafka_status
from kernel_api.rpc.registry import KernelRPCRegistry


def test_kafka_status_function_registered():
    detail = KernelRPCRegistry.get_function_detail("admin.datasource.kafka_status_batch")

    assert detail is not None
    assert detail["func_name"] == "admin.datasource.kafka_status_batch"
    assert "bk_data_ids" in detail["params_schema"]


def test_normalize_bk_data_ids_deduplicates_and_preserves_order():
    assert kafka_status._normalize_bk_data_ids([3, "2", 3, 1]) == [3, 2, 1]


@pytest.mark.parametrize("invalid_value", [None, [], [0], [True], ["bad"], list(range(1, 22))])
def test_normalize_bk_data_ids_rejects_invalid_values(invalid_value):
    with pytest.raises(CustomException):
        kafka_status._normalize_bk_data_ids(invalid_value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1_786_000_000, 1_786_000_000),
        (1_786_000_000_000, 1_786_000_000),
        ("1786000000000000", 1_786_000_000),
        (1_786_000_000_000_000_000, 1_786_000_000),
        ("2026-07-29T12:00:00Z", 1_785_326_400),
    ],
)
def test_parse_timestamp_value_supports_common_time_formats(value, expected):
    parsed = kafka_status._parse_timestamp_value(value)

    assert parsed is not None
    assert int(parsed.timestamp()) == expected


def test_extract_payload_timestamp_uses_field_priority_and_latest_nested_record():
    payload = {
        "time": 1_786_000_000,
        "timestamp": 1_786_000_100,
        "data": [
            {"utctime": "2026-07-29T12:00:00Z"},
            {"dtEventTimeStamp": 1_786_009_000_000},
        ],
    }

    timestamp, field = kafka_status._extract_payload_timestamp(payload)

    assert int(timestamp.timestamp()) == 1_786_009_000
    assert field == "dtEventTimeStamp"


def test_check_datasource_uses_metadata_kafka_tail_and_extracts_latest_time():
    checked_at = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    payload = {"time": int((checked_at - timedelta(seconds=60)).timestamp()), "value": 1}

    with patch.object(kafka_status.resource.metadata, "kafka_tail", return_value=[payload]) as kafka_tail:
        item = kafka_status._check_datasource("tenant-a", 1001, checked_at)

    kafka_tail.assert_called_once_with(
        bk_tenant_id="tenant-a",
        bk_data_id=1001,
        size=1,
        use_gse_config=True,
    )
    assert item["status"] == "fresh"
    assert item["has_data"] is True
    assert item["age_seconds"] == 60
    assert item["timestamp_field"] == "time"
    assert item["topics"] == []
    assert item["partitions_checked"] == 0


def test_check_datasource_reports_unknown_time_for_payload_without_time():
    with patch.object(kafka_status.resource.metadata, "kafka_tail", return_value=[{"value": 1}]):
        item = kafka_status._check_datasource("tenant-a", 1001, datetime.now(tz=UTC))

    assert item["status"] == "unknown_time"
    assert item["has_data"] is True
    assert item["latest_timestamp"] is None


def test_check_datasource_reports_no_data_for_empty_tail_result():
    with patch.object(kafka_status.resource.metadata, "kafka_tail", return_value=[]):
        item = kafka_status._check_datasource("tenant-a", 1001, datetime.now(tz=UTC))

    assert item["status"] == "no_data"
    assert item["has_data"] is False


def test_check_datasource_reports_error_when_kafka_tail_fails():
    with patch.object(kafka_status.resource.metadata, "kafka_tail", side_effect=RuntimeError("down")):
        item = kafka_status._check_datasource("tenant-a", 1001, datetime.now(tz=UTC))

    assert item["status"] == "error"
    assert item["has_data"] is None
    assert item["error"] == "Kafka Tail 检查失败: down"


def test_check_datasource_uses_exact_freshness_boundary():
    checked_at = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    payload = {"timestamp": int((checked_at - timedelta(seconds=180)).timestamp())}

    with patch.object(kafka_status.resource.metadata, "kafka_tail", return_value=[payload]):
        item = kafka_status._check_datasource("tenant-a", 1001, checked_at)

    assert item["status"] == "fresh"
    assert item["age_seconds"] == 180


def test_kafka_status_batch_preserves_input_order_and_summary():
    def fake_check(_tenant_id, bk_data_id, _checked_at):
        return {
            "bk_data_id": bk_data_id,
            "status": "fresh" if bk_data_id != 9999 else "no_data",
            "has_data": bk_data_id != 9999,
            "latest_timestamp": "2026-07-29T12:00:00Z" if bk_data_id != 9999 else None,
            "timestamp_field": "time" if bk_data_id != 9999 else None,
            "age_seconds": 0 if bk_data_id != 9999 else None,
            "route_count": 0,
            "partitions_checked": 0,
            "topics": [],
            "duration_ms": 1,
            "warnings": [],
            "error": None,
        }

    with (
        patch.object(kafka_status, "_check_datasource", side_effect=fake_check),
        patch.object(kafka_status, "close_old_connections"),
    ):
        response = kafka_status.kafka_status_batch(
            {"bk_tenant_id": "tenant-a", "bk_data_ids": [1002, 1001, 9999, 1002]}
        )

    assert [item["bk_data_id"] for item in response["data"]["items"]] == [1002, 1001, 9999]
    assert response["data"]["summary"] == {
        "fresh": 2,
        "stale": 0,
        "unknown_time": 0,
        "no_data": 1,
        "error": 0,
    }
