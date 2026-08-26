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
import threading
from collections.abc import Mapping
from functools import lru_cache

from alarm_backends.core.alarmd.contract import validate_trigger_strategy_ir
from alarm_backends.core.alarmd.encoder import decode_json_document, encode_json_document

DEFAULT_DELIVERY_TIMEOUT_MS = 3000
DEFAULT_MAX_ENVELOPE_BYTES = 512 * 1024
DEFAULT_MAX_OUTCOMES_PER_MESSAGE = 500
PARTITION_HASH_VERSION = "trigger-input-partition-v1"
PRODUCER_SCOPE_POST_DETECTION = "post_detection"


class DetectionPublishError(RuntimeError):
    """Raised when an outcome batch is not acknowledged within the configured bound."""


class KafkaPublishReceipt:
    """Track delivery callbacks for one stage on a process-shared producer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending_messages = 0
        self._acknowledged_records = 0
        self._delivery_errors = []
        self.enqueue_error = None

    def reserve(self, record_count: int):
        state = {"pending": True}
        with self._lock:
            self._pending_messages += 1

        def on_delivery(error, _message):
            with self._lock:
                if not state["pending"]:
                    return
                state["pending"] = False
                self._pending_messages -= 1
                if error is None:
                    self._acknowledged_records += record_count
                else:
                    self._delivery_errors.append(error)

        def cancel():
            with self._lock:
                if state["pending"]:
                    state["pending"] = False
                    self._pending_messages -= 1

        return on_delivery, cancel

    def fail_enqueue(self, error: Exception) -> None:
        with self._lock:
            if self.enqueue_error is None:
                self.enqueue_error = error

    @property
    def pending_messages(self) -> int:
        with self._lock:
            return self._pending_messages

    @property
    def acknowledged_records(self) -> int:
        with self._lock:
            return self._acknowledged_records

    @property
    def first_delivery_error(self):
        with self._lock:
            return self._delivery_errors[0] if self._delivery_errors else None


class _KafkaBoundedPublisher:
    def __init__(
        self,
        *,
        producer,
        topic: str,
        flush_timeout: float,
        max_outcomes_per_message: int = DEFAULT_MAX_OUTCOMES_PER_MESSAGE,
        max_envelope_bytes: int = DEFAULT_MAX_ENVELOPE_BYTES,
    ):
        if not isinstance(topic, str) or not topic:
            raise ValueError("detection topic must be non-empty")
        if isinstance(flush_timeout, bool) or not isinstance(flush_timeout, (int, float)) or flush_timeout <= 0:
            raise ValueError("flush_timeout must be positive")
        if (
            isinstance(max_outcomes_per_message, bool)
            or not isinstance(max_outcomes_per_message, int)
            or max_outcomes_per_message <= 0
            or max_outcomes_per_message > DEFAULT_MAX_OUTCOMES_PER_MESSAGE
        ):
            raise ValueError(f"max_outcomes_per_message must be between 1 and {DEFAULT_MAX_OUTCOMES_PER_MESSAGE}")
        if (
            isinstance(max_envelope_bytes, bool)
            or not isinstance(max_envelope_bytes, int)
            or max_envelope_bytes <= 0
            or max_envelope_bytes > DEFAULT_MAX_ENVELOPE_BYTES
        ):
            raise ValueError(f"max_envelope_bytes must be between 1 and {DEFAULT_MAX_ENVELOPE_BYTES}")
        self.producer = producer
        self.topic = topic
        self.flush_timeout = flush_timeout
        self.max_outcomes_per_message = max_outcomes_per_message
        self.max_envelope_bytes = max_envelope_bytes


class KafkaDetectInputPublisher(_KafkaBoundedPublisher):
    """Publish accepted raw records for the isolated Go Detect→Trigger path."""

    def publish_batch(self, batch: Mapping) -> int:
        receipt = self.enqueue_batch(batch)
        try:
            remaining = self.producer.flush(timeout=self.flush_timeout)
        except Exception as error:
            raise DetectionPublishError(f"detect input publish failed: {error}") from error
        return self.resolve_receipt(receipt, remaining=remaining)

    def prepare_batch(self, batch: Mapping):
        if not isinstance(batch, Mapping):
            raise DetectionPublishError("detect input batch must be an object")
        strategy_ir = batch.get("strategy_ir")
        batch_id = batch.get("batch_id")
        records = batch.get("records")
        validate_trigger_strategy_ir(strategy_ir)
        if not isinstance(batch_id, str) or not batch_id:
            raise DetectionPublishError("detect input batch_id must be non-empty")
        if not isinstance(records, list) or not records:
            raise DetectionPublishError("detect input records must be a non-empty array")

        partition_key = trigger_partition_key(strategy_ir)
        microbatches = self._plan_detect_input_microbatches(strategy_ir, batch_id, records)
        return [
            (
                partition_key,
                encode_json_document(_detect_input_envelope(strategy_ir, batch_id, records[start:end])),
                end - start,
            )
            for start, end in microbatches
        ]

    def enqueue_batch(self, batch: Mapping) -> KafkaPublishReceipt:
        return self.enqueue_prepared(self.prepare_batch(batch))

    def enqueue_prepared(self, prepared) -> KafkaPublishReceipt:
        receipt = KafkaPublishReceipt()
        for partition_key, payload, record_count in prepared:
            on_delivery, cancel = receipt.reserve(record_count)
            try:
                self.producer.produce(
                    topic=self.topic,
                    key=partition_key,
                    value=payload,
                    on_delivery=on_delivery,
                )
                if hasattr(self.producer, "poll"):
                    self.producer.poll(0)
            except Exception as error:
                cancel()
                receipt.fail_enqueue(error)
                break
        return receipt

    @staticmethod
    def resolve_receipt(receipt: KafkaPublishReceipt, *, remaining=None) -> int:
        if receipt.enqueue_error is not None:
            raise DetectionPublishError(f"detect input publish failed: {receipt.enqueue_error}")
        if remaining and receipt.pending_messages:
            raise DetectionPublishError(f"detect input publish flush timeout: {remaining} message(s) unacknowledged")
        if receipt.first_delivery_error is not None:
            raise DetectionPublishError(f"detect input publish broker rejected message: {receipt.first_delivery_error}")
        if receipt.pending_messages:
            raise DetectionPublishError(
                f"detect input publish flush timeout: {receipt.pending_messages} message(s) unacknowledged"
            )
        return receipt.acknowledged_records

    def _plan_detect_input_microbatches(
        self, strategy_ir: Mapping, batch_id: str, records: list[Mapping]
    ) -> list[tuple[int, int]]:
        return plan_detect_input_microbatches(
            strategy_ir,
            batch_id,
            records,
            max_records=self.max_outcomes_per_message,
            max_envelope_bytes=self.max_envelope_bytes,
        )


def _build_kafka_bounded_publisher(
    config: Mapping,
    *,
    allowed_topics,
    producer_factory=None,
    producer_scope=PRODUCER_SCOPE_POST_DETECTION,
):
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
    max_outcomes_per_message = producer_config.pop(
        "alarm.engine.max.outcomes.per.message", DEFAULT_MAX_OUTCOMES_PER_MESSAGE
    )
    max_envelope_bytes = producer_config.pop("alarm.engine.max.envelope.bytes", DEFAULT_MAX_ENVELOPE_BYTES)
    if producer_config.get("enable.idempotence", False) is not False:
        raise ValueError("detection Kafka producer idempotence must be disabled")
    producer_config["enable.idempotence"] = False
    producer_config["acks"] = "all"
    producer = _build_kafka_producer(
        producer_config,
        producer_factory=producer_factory,
        producer_scope=producer_scope,
    )
    return _KafkaBoundedPublisher(
        producer=producer,
        topic=topic,
        flush_timeout=flush_timeout,
        max_outcomes_per_message=max_outcomes_per_message,
        max_envelope_bytes=max_envelope_bytes,
    )


def build_kafka_detect_input_publisher(config: Mapping, *, allowed_topics, producer_factory=None):
    publisher = _build_kafka_bounded_publisher(
        config,
        allowed_topics=allowed_topics,
        producer_factory=producer_factory,
        producer_scope=PRODUCER_SCOPE_POST_DETECTION,
    )
    return KafkaDetectInputPublisher(
        producer=publisher.producer,
        topic=publisher.topic,
        flush_timeout=publisher.flush_timeout,
        max_outcomes_per_message=publisher.max_outcomes_per_message,
        max_envelope_bytes=publisher.max_envelope_bytes,
    )


@lru_cache(maxsize=1)
def get_cached_kafka_detect_input_publisher(config_json: str, allowed_topics: tuple[str, ...]):
    config = decode_json_document(config_json)
    return build_kafka_detect_input_publisher(config, allowed_topics=set(allowed_topics))


def _build_kafka_producer(producer_config: Mapping, *, producer_factory=None, producer_scope: str):
    if producer_factory is not None:
        return producer_factory(dict(producer_config))
    config_json = encode_json_document(dict(producer_config)).decode("utf-8")
    return _get_cached_default_kafka_producer(producer_scope, config_json)


@lru_cache(maxsize=8)
def _get_cached_default_kafka_producer(_producer_scope: str, config_json: str):
    from confluent_kafka import Producer

    return Producer(decode_json_document(config_json))


def trigger_partition_key(document: Mapping) -> bytes:
    ref = document["strategy_ref"]
    fields = (
        PARTITION_HASH_VERSION,
        document["tenant_id"],
        document["purpose"],
        ref["strategy_id"],
        ref["item_id"],
    )
    payload = bytearray()
    for field in fields:
        encoded = field.encode("utf-8")
        payload.extend(struct.pack(">I", len(encoded)))
        payload.extend(encoded)
    return hashlib.sha256(payload).digest()


def _detect_input_envelope(strategy_ir: Mapping, batch_id: str, records: list[Mapping]) -> dict:
    return {
        "schema": {"name": "detect-input", "major": 1, "minor": 0},
        "required_features": [],
        "partition_hash_version": PARTITION_HASH_VERSION,
        "strategy_ir": strategy_ir,
        "batch_id": batch_id,
        "records": records,
    }


def plan_detect_input_microbatches(
    strategy_ir: Mapping,
    batch_id: str,
    records: list[Mapping],
    *,
    max_records: int = DEFAULT_MAX_OUTCOMES_PER_MESSAGE,
    max_envelope_bytes: int = DEFAULT_MAX_ENVELOPE_BYTES,
) -> list[tuple[int, int]]:
    """Return record ranges that are independently safe to retain and publish."""

    base_size = len(encode_json_document(_detect_input_envelope(strategy_ir, batch_id, [])))
    current_start = 0
    current_count = 0
    current_size = base_size
    microbatches = []
    record_ids = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise DetectionPublishError("detect input record must be an object")
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise DetectionPublishError("detect input record_id must be non-empty")
        if record_id in record_ids:
            raise DetectionPublishError("detect input records must not contain duplicate record_id")
        record_ids.add(record_id)
        record_size = len(encode_json_document(record))
        added_size = record_size + (1 if current_count else 0)
        if current_count and (current_count >= max_records or current_size + added_size > max_envelope_bytes):
            microbatches.append((current_start, index))
            current_start = index
            current_count = 0
            current_size = base_size
            added_size = record_size
        if current_size + added_size > max_envelope_bytes:
            raise DetectionPublishError("single detect input record exceeds the envelope byte limit")
        current_count += 1
        current_size += added_size
    if current_count:
        microbatches.append((current_start, len(records)))
    return microbatches
