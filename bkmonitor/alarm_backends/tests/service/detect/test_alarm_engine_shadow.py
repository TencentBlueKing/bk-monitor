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
from types import SimpleNamespace
from unittest import mock

import pytest
from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.alarm_engine import publisher as publisher_module
from alarm_backends.core.alarm_engine import reference_publisher as reference_publisher_module
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY


def test_alarm_engine_shadow_is_inert_when_disabled():
    processor = object.__new__(DetectProcess)

    with mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", False, create=True):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_alarm_engine_shadow_requires_an_explicit_strategy_selector():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (), create=True),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


@pytest.mark.parametrize("selector", [(True,), (1.9,), ("01",), (" 1 ",), "1,"])
def test_alarm_engine_shadow_rejects_noncanonical_strategy_selectors(selector):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"

    with (
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", selector, create=True),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_alarm_engine_shadow_projects_finalized_threshold_records():
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
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        batches = processor.prepare_alarm_engine_detection_batches()

    assert len(batches) == 1
    assert [outcome["outcome"] for outcome in batches[0]["outcomes"]] == ["ANOMALOUS", "NORMAL"]
    assert "_alarm_engine" not in processor.outputs[2][0]


@pytest.mark.parametrize("stale_update_time", ["stale", True, 1.0])
def test_alarm_engine_shadow_rejects_inputs_from_a_stale_strategy_snapshot(stale_update_time):
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
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_ENABLED", True, create=True),
        mock.patch.object(settings, "ALARM_ENGINE_DETECTION_SHADOW_STRATEGY_IDS", (1,), create=True),
        mock.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", []),
        mock.patch.object(key.STRATEGY_SNAPSHOT_KEY.client, "get", return_value=json.dumps(strategy).encode()),
    ):
        assert processor.prepare_alarm_engine_detection_batches() == []


def test_detect_push_keeps_legacy_delivery_before_shadow_publish():
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "1"
    processor.strategy = SimpleNamespace(bk_biz_id=2, name="strategy")
    processor.inputs = {}
    processor.outputs = {}
    calls = []
    processor.prepare_alarm_engine_detection_batches = lambda: calls.append("prepare") or ["batch"]
    processor.push_abnormal_data = lambda *_args: calls.append("legacy") or 0
    processor.publish_alarm_engine_detection_batches = lambda batches: calls.append(("shadow", batches))

    processor.push_data()

    assert calls == ["legacy", "prepare", ("shadow", ["batch"])]


def test_alarm_engine_shadow_publishes_with_process_cached_producer():
    published = []
    fake_publisher = SimpleNamespace(publish_batch=lambda batch: published.append(batch) or len(batch["outcomes"]))
    batches = [{"strategy_ir": {}, "outcomes": [{"input_id": "one"}]}]

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=fake_publisher),
    ):
        assert DetectProcess.publish_alarm_engine_detection_batches(batches) == 1

    assert published == batches


def test_alarm_engine_shadow_publishes_terminal_reference_only_after_detection_ack():
    calls = []
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(
        publish_batch=lambda value: calls.append(("detection", value)) or len(value["outcomes"])
    )
    reference_publisher = SimpleNamespace(publish_batch=lambda value: calls.append(("reference", value)) or 1)

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-reference-shadow",),
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
        assert DetectProcess.publish_alarm_engine_detection_batches([batch]) == 2

    assert [name for name, _value in calls] == ["detection", "reference-factory", "reference"]
    assert calls[2][1]["decisions"][0]["reason_code"] == "INPUT_NORMAL"
    factory_args = reference_factory.call_args.args
    assert factory_args[2] == ("alarm-engine-detection-shadow", "monitor-event-nondefault")


def test_alarm_engine_reference_failure_does_not_change_acknowledged_detection_result():
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=lambda value: len(value["outcomes"]))
    reference_publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("reference failed")))

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-reference-shadow",),
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
        assert DetectProcess.publish_alarm_engine_detection_batches([batch]) == 2

    reference_publisher.publish_batch.assert_called_once()


@pytest.mark.parametrize(
    ("reference_config", "reference_allowed_topics"),
    [
        ({"topic": object()}, ("alarm-engine-reference-shadow",)),
        ({"topic": "alarm-engine-reference-shadow"}, (["not-hashable"],)),
    ],
)
def test_invalid_reference_config_does_not_block_detection_ack(reference_config, reference_allowed_topics):
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(return_value=len(batch["outcomes"])))

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            reference_config,
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
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
        assert DetectProcess.publish_alarm_engine_detection_batches([batch]) == len(batch["outcomes"])

    detection_publisher.publish_batch.assert_called_once_with(batch)
    reference_factory.assert_not_called()


def test_detection_publish_failure_never_initializes_or_sends_reference():
    batch = _prepared_detection_batch()
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(side_effect=RuntimeError("detection failed")))

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
        ) as reference_factory,
    ):
        with pytest.raises(RuntimeError, match="detection failed"):
            DetectProcess.publish_alarm_engine_detection_batches([batch])

    reference_factory.assert_not_called()


def test_all_anomalous_detection_batch_does_not_initialize_terminal_reference():
    batch = _prepared_detection_batch()
    batch["outcomes"] = [batch["outcomes"][0]]
    detection_publisher = SimpleNamespace(publish_batch=mock.Mock(return_value=1))

    with (
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
        ) as reference_factory,
    ):
        assert DetectProcess.publish_alarm_engine_detection_batches([batch]) == 1

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
            "ALARM_ENGINE_DETECTION_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_DETECTION_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-detection-shadow",),
            create=True,
        ),
        mock.patch.object(settings, "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ENABLED", True, create=True),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_KAFKA_CONFIG",
            {"topic": "alarm-engine-reference-shadow", "bootstrap.servers": "kafka:9092"},
            create=True,
        ),
        mock.patch.object(
            settings,
            "ALARM_ENGINE_TRIGGER_REFERENCE_SHADOW_ALLOWED_TOPICS",
            ("alarm-engine-reference-shadow",),
            create=True,
        ),
        mock.patch.object(MonitorEventAdapter, "get_output_topic", return_value="monitor-event-nondefault"),
        mock.patch.object(publisher_module, "get_cached_kafka_detection_publisher", return_value=detection_publisher),
        mock.patch(
            "alarm_backends.core.alarm_engine.reference.build_terminal_reference_decision_batches",
            side_effect=[RuntimeError("projection failed"), [{"decisions": [{"input_id": "second"}]}]],
        ),
        mock.patch.object(
            reference_publisher_module,
            "get_cached_kafka_reference_decision_publisher",
            return_value=reference_publisher,
        ),
    ):
        assert DetectProcess.publish_alarm_engine_detection_batches([first_batch, second_batch]) == 3

    assert calls == [{"decisions": [{"input_id": "second"}]}]


def _prepared_detection_batch():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    anomalous_record, normal_record = copy.deepcopy(DETECT_RECORDS)
    from alarm_backends.core.alarm_engine.runtime import prepare_finalized_threshold_batch

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
