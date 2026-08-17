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

from alarm_backends.core.alarm_engine import publisher as publisher_module
from alarm_backends.core.alarm_engine.encoder import decode_json_document
from alarm_backends.core.alarm_engine.publisher import (
    DetectionPublishError,
    KafkaDetectionPublisher,
    build_kafka_detection_publisher,
)
from alarm_backends.core.alarm_engine.runtime import prepare_finalized_threshold_batch
from alarm_backends.tests.alarm_engine_fixtures import DETECT_RECORDS, DETECT_STRATEGY


class FakeProducer:
    def __init__(self, *, delivery_error=None, remaining=0):
        self.delivery_error = delivery_error
        self.remaining = remaining
        self.messages = []

    def produce(self, **message):
        self.messages.append(message)

    def flush(self, timeout):
        self.flush_timeout = timeout
        for message in self.messages:
            message["on_delivery"](self.delivery_error, None)
        return self.remaining


def test_kafka_detection_publisher_waits_for_delivery_and_emits_self_contained_envelope():
    producer = FakeProducer()
    publisher = KafkaDetectionPublisher(producer=producer, topic="alarm-engine-detection-shadow", flush_timeout=4)
    batch = _batch()

    published = publisher.publish_batch(batch)

    assert published == 1
    assert producer.flush_timeout == 4
    assert len(producer.messages) == 1
    message = producer.messages[0]
    assert message["topic"] == "alarm-engine-detection-shadow"
    assert isinstance(message["key"], bytes)
    assert message["key"].hex() == "76822eff60b83ab18de1ec5ecf6c194f6e933f12af8b28e199f2a43f8a730c27"
    envelope = decode_json_document(message["value"])
    assert envelope == {
        "schema": {"name": "trigger-input", "major": 1, "minor": 0},
        "required_features": [],
        "partition_hash_version": "trigger-input-partition-v1",
        "strategy_ir": batch["strategy_ir"],
        "detection_outcome": batch["outcomes"][0],
    }


@pytest.mark.parametrize(
    ("producer", "error"),
    [
        (FakeProducer(delivery_error=RuntimeError("broker rejected")), "broker rejected"),
        (FakeProducer(remaining=1), "flush timeout"),
    ],
)
def test_kafka_detection_publisher_fails_when_broker_does_not_ack(producer, error):
    publisher = KafkaDetectionPublisher(producer=producer, topic="alarm-engine-detection-shadow", flush_timeout=4)

    with pytest.raises(DetectionPublishError, match=error):
        publisher.publish_batch(_batch())


def test_build_kafka_detection_publisher_enables_idempotence_and_bounded_delivery():
    producer = FakeProducer()
    captured = {}

    def producer_factory(config):
        captured.update(config)
        return producer

    publisher = build_kafka_detection_publisher(
        {
            "topic": "alarm-engine-detection-shadow",
            "bootstrap.servers": "kafka:9092",
            "message.timeout.ms": 2500,
        },
        producer_factory=producer_factory,
        allowed_topics={"alarm-engine-detection-shadow"},
    )

    assert publisher.producer is producer
    assert publisher.topic == "alarm-engine-detection-shadow"
    assert publisher.flush_timeout == 3.5
    assert captured == {
        "bootstrap.servers": "kafka:9092",
        "message.timeout.ms": 2500,
        "enable.idempotence": True,
    }


def test_build_kafka_detection_publisher_rejects_production_topic():
    with pytest.raises(ValueError, match="not in the Shadow allowlist"):
        build_kafka_detection_publisher(
            {"topic": "monitor-event", "bootstrap.servers": "kafka:9092"},
            producer_factory=lambda _config: FakeProducer(),
            allowed_topics={"alarm-engine-detection-shadow"},
        )


def test_build_kafka_detection_publisher_rejects_disabled_idempotence():
    with pytest.raises(ValueError, match="idempotence"):
        build_kafka_detection_publisher(
            {
                "topic": "alarm-engine-detection-shadow",
                "bootstrap.servers": "kafka:9092",
                "enable.idempotence": False,
            },
            producer_factory=lambda _config: FakeProducer(),
            allowed_topics={"alarm-engine-detection-shadow"},
        )


def test_cached_kafka_detection_publisher_reuses_process_producer(monkeypatch):
    publisher_module.get_cached_kafka_detection_publisher.cache_clear()
    expected = object()
    calls = []

    def build(config, *, allowed_topics):
        calls.append((config, allowed_topics))
        return expected

    monkeypatch.setattr(publisher_module, "build_kafka_detection_publisher", build)
    config_json = json.dumps(
        {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
        sort_keys=True,
        separators=(",", ":"),
    )

    first = publisher_module.get_cached_kafka_detection_publisher(config_json, ("alarm-engine-detection-shadow",))
    second = publisher_module.get_cached_kafka_detection_publisher(config_json, ("alarm-engine-detection-shadow",))

    assert first is expected
    assert second is expected
    assert calls == [
        (
            {"topic": "alarm-engine-detection-shadow", "bootstrap.servers": "kafka:9092"},
            {"alarm-engine-detection-shadow"},
        )
    ]
    publisher_module.get_cached_kafka_detection_publisher.cache_clear()


def _batch():
    strategy = copy.deepcopy(DETECT_STRATEGY)
    record = copy.deepcopy(DETECT_RECORDS[0])
    return prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=strategy,
        item_id=2,
        legacy_json=json.dumps(strategy).encode(),
        batch_id="batch-1",
        data_points=[record],
        anomaly_outputs=[
            {
                "data": record,
                "anomaly": {
                    "3": {
                        "anomaly_id": f"{record['record_id']}.1.2.3",
                        "anomaly_message": "threshold matched",
                    }
                },
            }
        ],
        finalized=True,
    )
