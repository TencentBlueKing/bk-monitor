import copy
import json
from types import SimpleNamespace
from unittest import mock

from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.tests.alarmd_fixtures import DETECT_RECORDS, DETECT_STRATEGY


def test_alarmd_shadow_is_inert_when_disabled():
    processor = object.__new__(DetectProcess)
    with mock.patch.object(settings, "ALARMD_SHADOW_ENABLED", False, create=True):
        assert processor.prepare_alarmd_detection_batches() == []


def test_alarmd_shadow_projects_detect_input_and_python_terminal_for_all_threshold_records():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    anomalous_record, normal_record = copy.deepcopy(DETECT_RECORDS)
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    source_strategy = SimpleNamespace(id=1, config=strategy)
    processor.strategy = SimpleNamespace(
        id=1,
        bk_tenant_id="default",
        config=strategy,
        items=[SimpleNamespace(id=2)],
        snapshot_key="snapshot-key",
    )
    processor.inputs = {
        2: [
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda: anomalous_record),
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda: normal_record),
        ]
    }
    processor.outputs = {
        2: [
            {
                "data": anomalous_record,
                "anomaly": {"3": {"anomaly_id": f"{anomalous_record['record_id']}.1.2.3"}},
            }
        ]
    }

    with (
        mock.patch.object(settings, "ALARMD_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarmd_detection_batches()

    assert len(batches) == 1
    assert len(batches[0]["detect_input"]["records"]) == 2
    assert [outcome["outcome"] for outcome in batches[0]["outcomes"]] == ["ANOMALOUS", "NORMAL"]


def test_alarmd_shadow_splits_retained_async_jobs_at_500_records():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    source_strategy = SimpleNamespace(id=1, config=strategy)
    records = []
    inputs = []
    for index in range(501):
        record = copy.deepcopy(DETECT_RECORDS[1])
        record["time"] += index
        record["values"]["timestamp"] += index
        record["record_id"] = f"{index + 1:032x}.{record['time']}"
        records.append(record)
        inputs.append(
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda record=record: record)
        )

    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(
        id=1,
        bk_tenant_id="default",
        config=strategy,
        items=[SimpleNamespace(id=2)],
        snapshot_key="snapshot-key",
    )
    processor.inputs = {2: inputs}
    processor.outputs = {2: []}

    with (
        mock.patch.object(settings, "ALARMD_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarmd_detection_batches()

    assert [len(batch["detect_input"]["records"]) for batch in batches] == [500, 1]
    assert sum(len(batch["outcomes"]) for batch in batches) == len(records)


def test_alarmd_shadow_splits_on_the_complete_async_job_byte_limit():
    from alarm_backends.core.alarmd.async_publish import shadow_job_fits

    strategy = copy.deepcopy(DETECT_STRATEGY)
    records = copy.deepcopy(DETECT_RECORDS)
    for record in records:
        record["values"]["payload"] = "x" * 140_000
    source_strategy = SimpleNamespace(id=1, config=strategy)
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(
        id=1,
        bk_tenant_id="default",
        config=strategy,
        items=[SimpleNamespace(id=2)],
        snapshot_key="snapshot-key",
    )
    processor.inputs = {
        2: [
            SimpleNamespace(item=SimpleNamespace(strategy=source_strategy), as_dict=lambda record=record: record)
            for record in records
        ]
    }
    processor.outputs = {2: []}

    with (
        mock.patch.object(settings, "ALARMD_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarmd_detection_batches()

    assert [len(batch["detect_input"]["records"]) for batch in batches] == [1, 1]
    assert all(shadow_job_fits("detect_input", (batch,)) for batch in batches)


def test_detect_push_enqueues_one_bounded_job_per_batch_after_legacy_delivery():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    calls = []
    processor.prepare_alarmd_detection_batches = lambda: [{"batch_id": "one"}, {"batch_id": "two"}]
    processor.push_abnormal_data = lambda *_args, **_kwargs: calls.append("legacy") or 0

    def submit(operation, payload, *, max_jobs):
        calls.append((operation, payload, max_jobs))
        return True

    with (
        mock.patch("alarm_backends.core.alarmd.async_publish.submit_shadow_job", side_effect=submit),
        mock.patch.object(settings, "ALARMD_SHADOW_ASYNC_QUEUE_SIZE", 16, create=True),
    ):
        processor.push_data()

    assert calls == [
        "legacy",
        ("detect_input", ({"batch_id": "one"},), 16),
        ("detect_input", ({"batch_id": "two"},), 16),
    ]
