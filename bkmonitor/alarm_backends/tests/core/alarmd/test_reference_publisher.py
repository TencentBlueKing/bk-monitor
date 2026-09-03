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

import pytest

from alarm_backends.core.alarmd import reference_publisher as reference_publisher_module
from alarm_backends.core.alarmd.encoder import decode_trigger_decision_batch
from alarm_backends.core.alarmd.reference import build_reference_trigger_decision_candidate
from alarm_backends.core.alarmd.reference_publisher import (
    KafkaReferenceDecisionPublisher,
    ReferenceDecisionPublishError,
    build_kafka_reference_decision_publisher,
)
from alarm_backends.tests.alarmd_fixtures import TRIGGER_POINT, TRIGGER_STRATEGY


class FakeProducer:
    def __init__(self, *, delivery_error=None, remaining=0):
        self.delivery_error = delivery_error
        self.remaining = remaining
        self.messages = []
        self.flush_calls = 0
        self.pending_payload_bytes = 0
        self.flushed_payload_bytes = []

    def produce(self, **message):
        self.messages.append(message)
        self.pending_payload_bytes += len(message["value"])

    def flush(self, timeout):
        self.flush_calls += 1
        self.flush_timeout = timeout
        self.flushed_payload_bytes.append(self.pending_payload_bytes)
        self.pending_payload_bytes = 0
        if not self.remaining:
            for message in self.messages:
                message["on_delivery"](self.delivery_error, None)
        return self.remaining


def test_reference_publisher_uses_official_codec_partition_key_and_broker_ack():
    producer = FakeProducer()
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )
    batch = _trigger_reference_batch()

    assert publisher.publish_batch(batch) == 1
    assert producer.flush_timeout == 4
    assert len(producer.messages) == 1
    message = producer.messages[0]
    assert message["topic"] == "alarmd-reference-shadow"
    assert message["key"].hex() == "d59d72356eecbb9f60b48ea1c80fd0c23c51e21da5185009580084806ba472bc"
    assert decode_trigger_decision_batch(message["value"]) == batch


def test_reference_publisher_batches_share_one_broker_ack_barrier():
    producer = FakeProducer()
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )
    first = _trigger_reference_batch()
    second = copy.deepcopy(first)
    second["batch_id"] = "batch-2"

    assert publisher.publish_batches([first, second]) == 2
    assert len(producer.messages) == 2
    assert producer.flush_calls == 1


def test_reference_publisher_bounds_each_ack_group_by_encoded_bytes():
    producer = FakeProducer()
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )
    first = _trigger_reference_batch()
    second = copy.deepcopy(first)
    second["batch_id"] = "batch-2"
    for batch in (first, second):
        batch["schema"]["minor"] = 1
        batch["padding"] = "x" * (300 * 1024)

    assert publisher.publish_batches([first, second]) == 2
    assert producer.flush_calls == 2
    assert all(payload_bytes <= 512 * 1024 for payload_bytes in producer.flushed_payload_bytes)


def test_reference_publisher_does_not_consume_past_one_size_lookahead_after_ack_failure():
    producer = FakeProducer(remaining=1)
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )
    batches = []
    for index in range(3):
        batch = _trigger_reference_batch()
        batch["batch_id"] = f"batch-{index}"
        batch["schema"]["minor"] = 1
        batch["padding"] = "x" * (300 * 1024)
        batches.append(batch)
    consumed = []

    def iter_batches():
        for batch in batches:
            consumed.append(batch["batch_id"])
            yield batch

    with pytest.raises(ReferenceDecisionPublishError, match="flush timeout"):
        publisher.publish_batches(iter_batches())

    assert consumed == ["batch-0", "batch-1"]
    assert producer.flush_calls == 1


def test_reference_publisher_reports_records_from_complete_ack_groups_before_later_failure():
    class FailSecondFlushProducer(FakeProducer):
        def flush(self, timeout):
            self.flush_calls += 1
            self.flush_timeout = timeout
            if self.flush_calls == 1:
                for message in self.messages:
                    message["on_delivery"](None, None)
                return 0
            return 1

    producer = FailSecondFlushProducer()
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )
    batches = []
    for index in range(2):
        batch = _trigger_reference_batch()
        batch["batch_id"] = f"batch-{index}"
        batch["schema"]["minor"] = 1
        batch["padding"] = "x" * (300 * 1024)
        batches.append(batch)

    with pytest.raises(ReferenceDecisionPublishError) as error:
        publisher.publish_batches(batches)

    assert error.value.acknowledged_records == 1
    assert producer.flush_calls == 2


@pytest.mark.parametrize(
    ("producer", "error"),
    [
        (FakeProducer(delivery_error=RuntimeError("broker rejected")), "broker rejected"),
        (FakeProducer(remaining=1), "flush timeout"),
    ],
)
def test_reference_publisher_requires_broker_ack(producer, error):
    publisher = KafkaReferenceDecisionPublisher(
        producer=producer,
        topic="alarmd-reference-shadow",
        flush_timeout=4,
    )

    with pytest.raises(ReferenceDecisionPublishError, match=error):
        publisher.publish_batch(_trigger_reference_batch())


def test_reference_publisher_config_uses_all_acks_without_idempotence():
    producer = FakeProducer()
    captured = {}

    def producer_factory(config):
        captured.update(config)
        return producer

    publisher = build_kafka_reference_decision_publisher(
        {
            "topic": "alarmd-reference-shadow",
            "bootstrap.servers": "kafka:9092",
            "message.timeout.ms": 2500,
        },
        producer_factory=producer_factory,
        allowed_topics={"alarmd-reference-shadow"},
    )

    assert publisher.producer is producer
    assert publisher.flush_timeout == 3.5
    assert captured == {
        "bootstrap.servers": "kafka:9092",
        "message.timeout.ms": 2500,
        "enable.idempotence": False,
        "acks": "all",
    }


@pytest.mark.parametrize(
    "config",
    [
        {"topic": "monitor-event", "bootstrap.servers": "kafka:9092"},
        {
            "topic": "alarmd-reference-shadow",
            "bootstrap.servers": "kafka:9092",
            "enable.idempotence": True,
        },
    ],
)
def test_reference_publisher_rejects_unsafe_config(config):
    with pytest.raises(ValueError):
        build_kafka_reference_decision_publisher(
            config,
            producer_factory=lambda _config: FakeProducer(),
            allowed_topics={"alarmd-reference-shadow"},
        )


@pytest.mark.parametrize("forbidden_topic", ["monitor-event", "monitor-event-nondefault"])
def test_reference_publisher_rejects_topics_that_are_explicitly_forbidden(forbidden_topic):
    with pytest.raises(ValueError, match="allowlist must not contain forbidden"):
        build_kafka_reference_decision_publisher(
            {"topic": forbidden_topic, "bootstrap.servers": "kafka:9092"},
            producer_factory=lambda _config: FakeProducer(),
            allowed_topics={forbidden_topic},
            forbidden_topics={forbidden_topic},
        )


def test_cached_reference_publisher_reuses_process_producer_and_logs_enabled_once(monkeypatch, caplog):
    reference_publisher_module.get_cached_kafka_reference_decision_publisher.cache_clear()
    caplog.set_level(logging.INFO, logger=reference_publisher_module.__name__)
    expected = object()
    calls = []

    def build(config, *, allowed_topics, forbidden_topics):
        calls.append((config, allowed_topics, forbidden_topics))
        return expected

    monkeypatch.setattr(reference_publisher_module, "build_kafka_reference_decision_publisher", build)
    config_json = json.dumps(
        {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
        sort_keys=True,
        separators=(",", ":"),
    )

    first = reference_publisher_module.get_cached_kafka_reference_decision_publisher(
        config_json, ("alarmd-reference-shadow",), ("monitor-event",)
    )
    second = reference_publisher_module.get_cached_kafka_reference_decision_publisher(
        config_json, ("alarmd-reference-shadow",), ("monitor-event",)
    )

    assert first is expected
    assert second is expected
    assert calls == [
        (
            {"topic": "alarmd-reference-shadow", "bootstrap.servers": "kafka:9092"},
            {"alarmd-reference-shadow"},
            {"monitor-event"},
        )
    ]
    enabled_logs = [record.getMessage() for record in caplog.records if "result=enabled" in record.getMessage()]
    assert len(enabled_logs) == 1
    assert "component=alarmd-python stage=reference result=enabled records=0 duration_ms=" in enabled_logs[0]
    assert "bootstrap.servers" not in enabled_logs[0]
    assert "kafka:9092" not in enabled_logs[0]
    reference_publisher_module.get_cached_kafka_reference_decision_publisher.cache_clear()


def _trigger_reference_batch():
    point = copy.deepcopy(TRIGGER_POINT)
    strategy = copy.deepcopy(TRIGGER_STRATEGY)
    strategy["update_time"] = 1569246480
    source_time = point["data"]["time"]
    event_record = copy.deepcopy(point)
    event_record["trigger"] = {
        "level": "3",
        "anomaly_ids": [f"55a76cf628e46c04a052f4e19bdb9dbf.{source_time}.1.1.3"],
    }
    return build_reference_trigger_decision_candidate(
        strategy=strategy,
        legacy_json=json.dumps(strategy, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        strategy_snapshot_key=point["strategy_snapshot_key"],
        tenant_id_resolver=lambda _bk_biz_id: "default",
        item_id=1,
        point=point,
        event_record=event_record,
    )
