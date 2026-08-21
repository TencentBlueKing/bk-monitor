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
import logging
from types import SimpleNamespace
from unittest import mock

import pytest
from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.alarmd import publisher as publisher_module
from alarm_backends.core.alarmd import reference_publisher as reference_publisher_module
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.tests.alarmd_fixtures import DETECT_RECORDS, DETECT_STRATEGY


def test_alarmd_shadow_is_inert_when_disabled():
    processor = object.__new__(DetectProcess)

    with mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", False, create=True):
        assert processor.prepare_alarmd_detection_batches() == []


def test_alarmd_shadow_requires_an_explicit_strategy_selector():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", (), create=True),
    ):
        assert processor.prepare_alarmd_detection_batches() == []


@pytest.mark.parametrize("selector", [(True,), (1.9,), ("01",), (" 1 ",), "1,"])
def test_alarmd_shadow_rejects_noncanonical_strategy_selectors(selector):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", selector, create=True),
    ):
        assert processor.prepare_alarmd_detection_batches() == []


def test_alarmd_shadow_projects_finalized_threshold_records():
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
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarmd_detection_batches()

    assert len(batches) == 1
    assert [outcome["outcome"] for outcome in batches[0]["outcomes"]] == ["ANOMALOUS", "NORMAL"]
    assert "_alarmd" not in processor.outputs[2][0]


@pytest.mark.parametrize("stale_update_time", ["stale", True, 1.0])
def test_alarmd_shadow_rejects_inputs_from_a_stale_strategy_snapshot(stale_update_time):
    strategy = copy.deepcopy(DETECT_STRATEGY)
    stale_strategy = copy.deepcopy(strategy)
    strategy["update_time"] = 1
    stale_strategy["update_time"] = stale_update_time
    record = copy.deepcopy(DETECT_RECORDS[0])
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
            SimpleNamespace(
                item=SimpleNamespace(strategy=SimpleNamespace(id=1, config=stale_strategy)),
                as_dict=lambda: record,
            )
        ]
    }
    processor.outputs = {2: []}

    with (
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARMD_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        assert processor.prepare_alarmd_detection_batches() == []


def test_detect_push_keeps_legacy_delivery_before_shadow_publish():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    calls = []
    processor.prepare_alarmd_detection_batches = lambda: calls.append("prepare") or ["batch"]
    processor.push_abnormal_data = lambda *_args: calls.append("legacy") or 0
    processor.publish_alarmd_detection_batches = lambda batches: calls.append(("shadow", batches))

    processor.push_data()

    assert calls == ["legacy", "prepare", ("shadow", ["batch"])]


def test_alarmd_shadow_publishes_with_process_cached_producer():
    published = []
    fake_publisher = SimpleNamespace(publish_batch=lambda batch: published.append(batch) or len(batch["outcomes"]))
    batches = [{"strategy_ir": {}, "outcomes": [{"input_id": "one"}]}]

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=fake_publisher),
    ):
        assert DetectProcess.publish_alarmd_detection_batches(batches) == 1

    assert published == batches


def test_alarmd_detect_input_failure_does_not_change_detection_ack(caplog):
    from alarm_backends.core.alarmd.runtime import prepare_detect_input_batch

    caplog.set_level(logging.ERROR, logger="detect")
    batch = _prepared_detection_batch()
    batch["detect_input"] = prepare_detect_input_batch(
        strategy_ir=batch["strategy_ir"],
        batch_id="batch-1",
        data_points=copy.deepcopy(DETECT_RECORDS),
    )
    detection_publisher = SimpleNamespace(publish_batch=lambda value: len(value["outcomes"]))
    detect_input_publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("shadow failed")))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_DETECT_INPUT_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_DETECT_INPUT_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detect-input-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECT_INPUT_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detect-input-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", False, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            publisher_module,
            "get_cached_kafka_detect_input_publisher",
            return_value=detect_input_publisher,
        ),
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == 2

    assert detect_input_publisher.publish_batch.call_count == 1
    assert any("stage=detect_input result=fail_open" in record.getMessage() for record in caplog.records)


def test_alarmd_shadow_publishes_terminal_reference_only_after_detection_ack(caplog):
    caplog.set_level(logging.INFO, logger="detect")
    calls = []
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(
        publish_batch=lambda value: calls.append(("detection", value)) or len(value["outcomes"])
    )
    reference_publisher = SimpleNamespace(publish_batch=lambda value: calls.append(("reference", value)) or 1)

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            side_effect=lambda *_args: calls.append(("reference-factory", None)) or reference_publisher,
        ) as reference_factory,
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == 2

    assert [name for name, _value in calls] == ["detection", "reference-factory", "reference"]
    assert calls[2][1]["decisions"][0]["reason_code"] == "INPUT_NORMAL"
    factory_args = reference_factory.call_args.args
    assert factory_args[2] == ("alarmd-detection-shadow", "monitor-event-nondefault")
    ack_logs = [record.getMessage() for record in caplog.records if "result=broker_ack" in record.getMessage()]
    assert len(ack_logs) == 2
    assert "component=alarmd-python stage=detection result=broker_ack records=2 duration_ms=" in ack_logs[0]
    assert "component=alarmd-python stage=reference result=broker_ack records=1 duration_ms=" in ack_logs[1]
    assert all("strategy(1) batch_id=batch-1" in message for message in ack_logs)
    assert all("bootstrap.servers" not in message and "input_id" not in message for message in ack_logs)


def test_alarmd_reference_failure_does_not_change_acknowledged_detection_result(caplog):
    caplog.set_level(logging.WARNING, logger="detect")
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=lambda value: len(value["outcomes"]))
    reference_publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("reference failed")))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=reference_publisher,
        ),
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == 2

    reference_publisher.publish_batch.assert_called_once()
    fail_open_logs = [record.getMessage() for record in caplog.records if "result=fail_open" in record.getMessage()]
    assert len(fail_open_logs) == 1
    assert (
        "component=alarmd-python stage=reference result=fail_open operation=broker_publish "
        "records=0 duration_ms=" in fail_open_logs[0]
    )
    assert "strategy(1) batch_id=batch-1" in fail_open_logs[0]
    assert "reference failed" in caplog.text


def test_terminal_reference_failure_logs_records_from_prior_broker_acks(caplog):
    caplog.set_level(logging.WARNING, logger="detect")
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=lambda value: len(value["outcomes"]))
    reference_publisher = SimpleNamespace(
        publish_batch=mock.Mock(side_effect=[1, RuntimeError("later reference failed")])
    )

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_terminal_reference_decision_batches",
            return_value=[{"decisions": [{"input_id": "one"}]}, {"decisions": [{"input_id": "two"}]}],
        ),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=reference_publisher,
        ),
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == len(batch["outcomes"])

    fail_open_logs = [record.getMessage() for record in caplog.records if "result=fail_open" in record.getMessage()]
    assert len(fail_open_logs) == 1
    assert "stage=reference result=fail_open operation=broker_publish records=1" in fail_open_logs[0]
    assert "strategy(1) batch_id=batch-1" in fail_open_logs[0]


def test_detection_multi_batch_failure_logs_only_the_failed_batch(caplog):
    caplog.set_level(logging.INFO, logger="detect")
    first_batch = _prepared_detection_batch()
    second_batch = _prepared_detection_batch()
    second_batch["outcomes"] = [second_batch["outcomes"][0]]
    second_batch["outcomes"][0]["batch_id"] = "batch-2"
    publisher = SimpleNamespace(
        publish_batch=mock.Mock(side_effect=[len(first_batch["outcomes"]), RuntimeError("second batch failed")])
    )

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", False, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=publisher),
    ):
        with pytest.raises(RuntimeError, match="second batch failed") as error:
            DetectProcess.publish_alarmd_detection_batches([first_batch, second_batch])

    assert type(error.value).__name__ == "_LoggedAlarmdDetectionPublishError"
    assert isinstance(error.value.__cause__, RuntimeError)
    assert str(error.value.__cause__) == "second batch failed"
    ack_logs = [record.getMessage() for record in caplog.records if "result=broker_ack" in record.getMessage()]
    assert len(ack_logs) == 1
    assert "records=2" in ack_logs[0] and "batch_id=batch-1" in ack_logs[0]
    fail_open_logs = [record.getMessage() for record in caplog.records if "result=fail_open" in record.getMessage()]
    assert len(fail_open_logs) == 1
    assert "stage=detection result=fail_open operation=broker_publish records=1" in fail_open_logs[0]
    assert "strategy(1) batch_id=batch-2" in fail_open_logs[0]


def test_detect_push_fails_open_without_duplicate_publish_failure_log(caplog):
    caplog.set_level(logging.WARNING, logger="detect")
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    processor.push_abnormal_data = mock.Mock(return_value=0)
    processor.prepare_alarmd_detection_batches = mock.Mock(return_value=[_prepared_detection_batch()])
    publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("detection publish failed")))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", False, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=publisher),
    ):
        processor.push_data()

    fail_open_logs = [record.getMessage() for record in caplog.records if "result=fail_open" in record.getMessage()]
    assert len(fail_open_logs) == 1
    assert "operation=broker_publish" in fail_open_logs[0]


def test_detect_push_logs_generic_publisher_initialization_failure_once(caplog):
    caplog.set_level(logging.WARNING, logger="detect")
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    processor.push_abnormal_data = mock.Mock(return_value=0)
    processor.prepare_alarmd_detection_batches = mock.Mock(return_value=[_prepared_detection_batch()])

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(
            publisher_module,
            "get_cached_kafka_detection_publisher",
            side_effect=RuntimeError("publisher initialization failed"),
        ),
    ):
        processor.push_data()

    fail_open_logs = [record.getMessage() for record in caplog.records if "result=fail_open" in record.getMessage()]
    assert len(fail_open_logs) == 1
    assert "stage=detection result=fail_open operation=initialize records=0" in fail_open_logs[0]
    assert "strategy(1) batch_id=unknown" in fail_open_logs[0]


@pytest.mark.parametrize(
    ("reference_config", "reference_allowed_topics"),
    [
        ({"topic": object()}, ("alarmd-reference-shadow",)),
        ({"topic": "alarmd-reference-shadow"}, (["not-hashable"],)),
    ],
)
def test_invalid_reference_config_does_not_block_detection_ack(reference_config, reference_allowed_topics):
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(return_value=len(batch["outcomes"])))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            reference_config,
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            reference_allowed_topics,
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
        ) as reference_factory,
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == len(batch["outcomes"])

    detection_publisher.publish_batch.assert_called_once_with(batch)
    reference_factory.assert_not_called()


def test_detection_publish_failure_never_initializes_or_sends_reference():
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("detection failed")))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
        ) as reference_factory,
    ):
        with pytest.raises(RuntimeError, match="detection failed"):
            DetectProcess.publish_alarmd_detection_batches([batch])

    reference_factory.assert_not_called()


def test_all_anomalous_detection_batch_does_not_initialize_terminal_reference():
    batch = _prepared_detection_batch()
    batch["outcomes"] = [batch["outcomes"][0]]
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(return_value=1))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
        ) as reference_factory,
    ):
        assert DetectProcess.publish_alarmd_detection_batches([batch]) == 1

    reference_factory.assert_not_called()


def test_reference_projection_failure_does_not_disable_later_batches():
    first_batch = _prepared_detection_batch()
    second_batch = _prepared_detection_batch()
    second_batch["outcomes"] = [second_batch["outcomes"][1]]
    calls = []
    detection_publisher = SimpleNamespace(publish_batch=lambda batch: len(batch["outcomes"]))
    reference_publisher = SimpleNamespace(publish_batch=lambda batch: calls.append(batch) or len(batch["decisions"]))

    with (
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarmd-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARMD_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARMD_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarmd-reference-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch(
            "alarm_backends.core.alarmd.reference.build_terminal_reference_decision_batches",
            side_effect=[RuntimeError("projection failed"), [{"decisions": [{"input_id": "second"}]}]],
        ),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=reference_publisher,
        ),
    ):
        assert DetectProcess.publish_alarmd_detection_batches([first_batch, second_batch]) == 3

    assert calls == [{"decisions": [{"input_id": "second"}]}]


def _prepared_detection_batch():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    anomalous_record, normal_record = copy.deepcopy(DETECT_RECORDS)
    from alarm_backends.core.alarmd.runtime import prepare_finalized_threshold_batch

    return prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=strategy,
        item_id=2,
        legacy_json=json.dumps(strategy).encode(),
        batch_id="batch-1",
        data_points=[anomalous_record, normal_record],
        anomaly_outputs=[
            {
                "data": anomalous_record,
                "anomaly": {"3": {"anomaly_id": f"{anomalous_record['record_id']}.1.2.3"}},
            }
        ],
        finalized=True,
    )
