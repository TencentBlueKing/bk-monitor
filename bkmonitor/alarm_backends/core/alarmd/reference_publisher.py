"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable, Mapping
from functools import lru_cache

from alarm_backends.core.alarmd.encoder import (
    MAX_TRIGGER_DECISION_BATCH_BYTES,
    decode_json_document,
    encode_trigger_decision_batch,
)
from alarm_backends.core.alarmd.publisher import DEFAULT_DELIVERY_TIMEOUT_MS, trigger_partition_key


class ReferenceDecisionPublishError(RuntimeError):
    """Raised when a reference decision batch is not acknowledged."""


class KafkaReferenceDecisionPublisher:
    def __init__(self, *, producer, topic: str, flush_timeout: float):
        if not isinstance(topic, str) or not topic:
            raise ValueError("reference decision topic must be non-empty")
        if isinstance(flush_timeout, bool) or not isinstance(flush_timeout, (int, float)) or flush_timeout <= 0:
            raise ValueError("flush_timeout must be positive")
        self.producer = producer
        self.topic = topic
        self.flush_timeout = flush_timeout

    def publish_batch(self, batch: Mapping) -> int:
        return self.publish_batches([batch])

    def publish_batches(self, batches: Iterable[Mapping]) -> int:
        def publish_prepared(prepared):
            delivery_errors = []

            def on_delivery(error, _message):
                if error is not None:
                    delivery_errors.append(error)

            for partition_key, payload, _decision_count in prepared:
                self.producer.produce(
                    topic=self.topic,
                    key=partition_key,
                    value=payload,
                    on_delivery=on_delivery,
                )
                if hasattr(self.producer, "poll"):
                    self.producer.poll(0)
            remaining = self.producer.flush(timeout=self.flush_timeout)
            if remaining:
                raise ReferenceDecisionPublishError(
                    f"reference decision publish flush timeout: {remaining} message(s) unacknowledged"
                )
            if delivery_errors:
                raise ReferenceDecisionPublishError(
                    f"reference decision publish broker rejected message: {delivery_errors[0]}"
                )
            return sum(decision_count for _partition_key, _payload, decision_count in prepared)

        published = 0
        prepared = []
        prepared_bytes = 0
        try:
            for batch in batches:
                # One encoded lookahead is needed to decide whether the current ACK group is full;
                # official per-message validation bounds both the group and lookahead to 512 KiB each.
                payload = encode_trigger_decision_batch(batch)
                if prepared and prepared_bytes + len(payload) > MAX_TRIGGER_DECISION_BATCH_BYTES:
                    published += publish_prepared(prepared)
                    prepared = []
                    prepared_bytes = 0
                prepared.append((trigger_partition_key(batch), payload, len(batch["decisions"])))
                prepared_bytes += len(payload)
            if prepared:
                published += publish_prepared(prepared)
        except ReferenceDecisionPublishError:
            raise
        except Exception as error:
            raise ReferenceDecisionPublishError(f"reference decision publish failed: {error}") from error
        return published


def build_kafka_reference_decision_publisher(
    config: Mapping,
    *,
    allowed_topics,
    forbidden_topics=(),
    producer_factory=None,
):
    if not isinstance(config, Mapping):
        raise ValueError("reference decision Kafka config must be an object")
    if (
        not isinstance(allowed_topics, (set, frozenset))
        or not allowed_topics
        or any(not isinstance(topic, str) or not topic for topic in allowed_topics)
    ):
        raise ValueError("reference decision Shadow topic allowlist must be a non-empty string set")
    forbidden_topics = set(forbidden_topics)
    if any(not isinstance(topic, str) or not topic for topic in forbidden_topics):
        raise ValueError("reference decision forbidden topics must contain non-empty strings")
    if set(allowed_topics) & forbidden_topics:
        raise ValueError("reference decision allowlist must not contain forbidden topics")

    producer_config = dict(config)
    topic = producer_config.pop("topic", None)
    if topic not in allowed_topics or topic in forbidden_topics:
        raise ValueError(f"reference decision Kafka topic is not in the isolated Shadow allowlist: {topic}")

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
        raise ValueError("reference decision Kafka producer idempotence must be enabled")
    producer_config["enable.idempotence"] = True
    if producer_factory is None:
        from confluent_kafka import Producer

        producer_factory = Producer
    producer = producer_factory(producer_config)
    return KafkaReferenceDecisionPublisher(producer=producer, topic=topic, flush_timeout=flush_timeout)


@lru_cache(maxsize=1)
def get_cached_kafka_reference_decision_publisher(
    config_json: str,
    allowed_topics: tuple[str, ...],
    forbidden_topics: tuple[str, ...],
):
    config = decode_json_document(config_json)
    return build_kafka_reference_decision_publisher(
        config,
        allowed_topics=set(allowed_topics),
        forbidden_topics=set(forbidden_topics),
    )
