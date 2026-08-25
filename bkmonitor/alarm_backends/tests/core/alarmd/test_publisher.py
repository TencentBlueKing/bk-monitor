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

from alarm_backends.core.alarmd.encoder import decode_json_document
from alarm_backends.core.alarmd.publisher import (
    DetectionPublishError,
    KafkaDetectInputPublisher,
    build_kafka_detect_input_publisher,
    plan_detect_input_microbatches,
)
from alarm_backends.core.alarmd.runtime import prepare_detect_input_batch, prepare_finalized_threshold_batch
from alarm_backends.tests.alarmd_fixtures import DETECT_RECORDS, DETECT_STRATEGY


class FakeProducer:
    def __init__(self, *, delivery_error=None, remaining=0):
        self.delivery_error = delivery_error
        self.remaining = remaining
        self.messages = []

    def produce(self, **message):
        self.messages.append(message)

    def flush(self, timeout):
        self.flush_timeout = timeout
        if not self.remaining:
            for message in self.messages:
                message["on_delivery"](self.delivery_error, None)
        return self.remaining


def test_kafka_detect_input_publisher_emits_raw_records_for_go_detect():
    producer = FakeProducer()
    publisher = KafkaDetectInputPublisher(producer=producer, topic="alarmd-detect-input-shadow", flush_timeout=4)
    source = _batch(include_normal=True)
    batch = prepare_detect_input_batch(
        strategy_ir=source["strategy_ir"],
        batch_id="batch-1",
        data_points=copy.deepcopy(DETECT_RECORDS),
    )

    assert publisher.publish_batch(batch) == 2
    assert len(producer.messages) == 1
    message = producer.messages[0]
    assert message["topic"] == "alarmd-detect-input-shadow"
    assert isinstance(message["key"], bytes)
    assert decode_json_document(message["value"]) == batch


def test_kafka_detect_input_publisher_splits_microbatches_by_count():
    producer = FakeProducer()
    publisher = KafkaDetectInputPublisher(
        producer=producer,
        topic="alarmd-detect-input-shadow",
        flush_timeout=4,
        max_outcomes_per_message=1,
        max_envelope_bytes=512 * 1024,
    )
    source = _batch(include_normal=True)
    batch = prepare_detect_input_batch(
        strategy_ir=source["strategy_ir"], batch_id="batch-1", data_points=copy.deepcopy(DETECT_RECORDS)
    )

    assert publisher.publish_batch(batch) == 2
    assert len(producer.messages) == 2
    assert [len(decode_json_document(message["value"])["records"]) for message in producer.messages] == [1, 1]


def test_detect_input_job_ranges_are_bounded_by_encoded_bytes():
    source = _batch(include_normal=True)
    records = copy.deepcopy(DETECT_RECORDS)
    for record in records:
        record["values"]["payload"] = "x" * 300_000

    assert plan_detect_input_microbatches(source["strategy_ir"], "batch-1", records) == [(0, 1), (1, 2)]


@pytest.mark.parametrize(
    ("producer", "error"),
    [
        (FakeProducer(delivery_error=RuntimeError("broker rejected")), "broker rejected"),
        (FakeProducer(remaining=1), "flush timeout"),
    ],
)
def test_kafka_detect_input_publisher_fails_when_broker_does_not_ack(producer, error):
    publisher = KafkaDetectInputPublisher(producer=producer, topic="alarmd-detect-input-shadow", flush_timeout=4)
    source = _batch()
    batch = prepare_detect_input_batch(
        strategy_ir=source["strategy_ir"], batch_id="batch-1", data_points=copy.deepcopy(DETECT_RECORDS[:1])
    )

    with pytest.raises(DetectionPublishError, match=error):
        publisher.publish_batch(batch)


def test_build_kafka_detect_input_publisher_uses_all_acks_without_idempotence():
    producer = FakeProducer()
    captured = {}

    def producer_factory(config):
        captured.update(config)
        return producer

    publisher = build_kafka_detect_input_publisher(
        {
            "topic": "alarmd-detect-input-shadow",
            "bootstrap.servers": "kafka:9092",
            "message.timeout.ms": 2500,
        },
        producer_factory=producer_factory,
        allowed_topics={"alarmd-detect-input-shadow"},
    )

    assert publisher.producer is producer
    assert publisher.topic == "alarmd-detect-input-shadow"
    assert publisher.flush_timeout == 3.5
    assert captured == {
        "bootstrap.servers": "kafka:9092",
        "message.timeout.ms": 2500,
        "enable.idempotence": False,
        "acks": "all",
    }


def test_build_kafka_detect_input_publisher_rejects_production_topic():
    with pytest.raises(ValueError, match="not in the Shadow allowlist"):
        build_kafka_detect_input_publisher(
            {"topic": "monitor-event", "bootstrap.servers": "kafka:9092"},
            producer_factory=lambda _config: FakeProducer(),
            allowed_topics={"alarmd-detect-input-shadow"},
        )


def _batch(*, include_normal=False):
    strategy = copy.deepcopy(DETECT_STRATEGY)
    records = copy.deepcopy(DETECT_RECORDS if include_normal else DETECT_RECORDS[:1])
    record = records[0]
    return prepare_finalized_threshold_batch(
        tenant_id="default",
        strategy=strategy,
        item_id=2,
        legacy_json=json.dumps(strategy).encode(),
        batch_id="batch-1",
        data_points=records,
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
