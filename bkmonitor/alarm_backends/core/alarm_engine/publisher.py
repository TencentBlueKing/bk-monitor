"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import struct
from collections.abc import Mapping
from functools import lru_cache

from alarm_backends.core.alarm_engine.contract import validate_detection_outcome, validate_trigger_strategy_ir
from alarm_backends.core.alarm_engine.encoder import decode_json_document, encode_json_document

DEFAULT_DELIVERY_TIMEOUT_MS = 3000
PARTITION_HASH_VERSION = "trigger-input-partition-v1"


class DetectionPublishError(RuntimeError):
    """Raised when an outcome batch is not acknowledged within the configured bound."""


class KafkaDetectionPublisher:
    def __init__(self, *, producer, topic: str, flush_timeout: float):
        if not isinstance(topic, str) or not topic:
            raise ValueError("detection topic must be non-empty")
        if isinstance(flush_timeout, bool) or not isinstance(flush_timeout, (int, float)) or flush_timeout <= 0:
            raise ValueError("flush_timeout must be positive")
        self.producer = producer
        self.topic = topic
        self.flush_timeout = flush_timeout

    def publish_batch(self, batch: Mapping) -> int:
        if not isinstance(batch, Mapping):
            raise DetectionPublishError("detection batch must be an object")
        strategy_ir = batch.get("strategy_ir")
        outcomes = batch.get("outcomes")
        validate_trigger_strategy_ir(strategy_ir)
        if not isinstance(outcomes, list):
            raise DetectionPublishError("detection batch outcomes must be an array")
        if not outcomes:
            return 0

        partition_key = _partition_key(strategy_ir)
        delivery_errors = []

        def on_delivery(error, _message):
            if error is not None:
                delivery_errors.append(error)

        try:
            for outcome in outcomes:
                validate_detection_outcome(outcome, strategy_ir)
                envelope = {
                    "schema": {"name": "trigger-input", "major": 1, "minor": 0},
                    "required_features": [],
                    "partition_hash_version": PARTITION_HASH_VERSION,
                    "strategy_ir": strategy_ir,
                    "detection_outcome": outcome,
                }
                self.producer.produce(
                    topic=self.topic,
                    key=partition_key,
                    value=encode_json_document(envelope),
                    on_delivery=on_delivery,
                )
            remaining = self.producer.flush(timeout=self.flush_timeout)
        except Exception as error:
            raise DetectionPublishError(f"detection publish failed: {error}") from error
        if remaining:
            raise DetectionPublishError(f"detection publish flush timeout: {remaining} message(s) unacknowledged")
        if delivery_errors:
            raise DetectionPublishError(f"detection publish broker rejected message: {delivery_errors[0]}")
        return len(outcomes)


def build_kafka_detection_publisher(config: Mapping, *, allowed_topics, producer_factory=None):
    if not isinstance(config, Mapping):
        raise ValueError("detection Kafka config must be an object")
    if (
        not isinstance(allowed_topics, (set, frozenset))
        or not allowed_topics
        or any(not isinstance(topic, str) or not topic for topic in allowed_topics)
    ):
        raise ValueError("detection Shadow topic allowlist must be a non-empty string set")
    producer_config = dict(config)
    topic = producer_config.pop("topic", None)
    if topic not in allowed_topics:
        raise ValueError(f"detection Kafka topic is not in the Shadow allowlist: {topic}")

    configured_timeouts = [
        producer_config[name] for name in ("message.timeout.ms", "delivery.timeout.ms") if name in producer_config
    ]
    if len(configured_timeouts) > 1:
        raise ValueError("configure only one delivery timeout alias")
    raw_timeout = configured_timeouts[0] if configured_timeouts else DEFAULT_DELIVERY_TIMEOUT_MS
    if isinstance(raw_timeout, bool):
        raise ValueError("delivery timeout must be a positive number")
    try:
        timeout_ms = int(float(raw_timeout))
    except (TypeError, ValueError) as error:
        raise ValueError("delivery timeout must be a positive number") from error
    if timeout_ms <= 0:
        raise ValueError("delivery timeout must be a positive number")
    if not configured_timeouts:
        producer_config["message.timeout.ms"] = timeout_ms

    flush_timeout = producer_config.pop("alarm.engine.flush.timeout.seconds", timeout_ms / 1000 + 1)
    if producer_config.get("enable.idempotence", True) is not True:
        raise ValueError("detection Kafka producer idempotence must be enabled")
    producer_config["enable.idempotence"] = True
    if producer_factory is None:
        from confluent_kafka import Producer

        producer_factory = Producer
    producer = producer_factory(producer_config)
    return KafkaDetectionPublisher(producer=producer, topic=topic, flush_timeout=flush_timeout)


@lru_cache(maxsize=1)
def get_cached_kafka_detection_publisher(config_json: str, allowed_topics: tuple[str, ...]):
    config = decode_json_document(config_json)
    return build_kafka_detection_publisher(config, allowed_topics=set(allowed_topics))


def _partition_key(strategy_ir: Mapping) -> bytes:
    ref = strategy_ir["strategy_ref"]
    fields = (
        PARTITION_HASH_VERSION,
        strategy_ir["tenant_id"],
        strategy_ir["purpose"],
        ref["strategy_id"],
        ref["item_id"],
    )
    payload = bytearray()
    for field in fields:
        encoded = field.encode("utf-8")
        payload.extend(struct.pack(">I", len(encoded)))
        payload.extend(encoded)
    return hashlib.sha256(payload).digest()
