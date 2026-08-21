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
import logging
import struct
import time
from collections.abc import Mapping
from functools import lru_cache

from alarm_backends.core.alarmd.contract import validate_detection_outcome, validate_trigger_strategy_ir
from alarm_backends.core.alarmd.encoder import decode_json_document, encode_json_document

DEFAULT_DELIVERY_TIMEOUT_MS = 3000
DEFAULT_MAX_ENVELOPE_BYTES = 512 * 1024
DEFAULT_MAX_OUTCOMES_PER_MESSAGE = 500
PARTITION_HASH_VERSION = "trigger-input-partition-v1"

logger = logging.getLogger(__name__)


class DetectionPublishError(RuntimeError):
    """Raised when an outcome batch is not acknowledged within the configured bound."""


class KafkaDetectionPublisher:
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

        partition_key = trigger_partition_key(strategy_ir)
        microbatches = self._plan_microbatches(strategy_ir, outcomes)
        delivery_errors = []

        def on_delivery(error, _message):
            if error is not None:
                delivery_errors.append(error)

        try:
            for start, end in microbatches:
                self.producer.produce(
                    topic=self.topic,
                    key=partition_key,
                    value=encode_json_document(_trigger_input_envelope(strategy_ir, outcomes[start:end])),
                    on_delivery=on_delivery,
                )
                if hasattr(self.producer, "poll"):
                    self.producer.poll(0)
            remaining = self.producer.flush(timeout=self.flush_timeout)
        except Exception as error:
            raise DetectionPublishError(f"detection publish failed: {error}") from error
        if remaining:
            raise DetectionPublishError(f"detection publish flush timeout: {remaining} message(s) unacknowledged")
        if delivery_errors:
            raise DetectionPublishError(f"detection publish broker rejected message: {delivery_errors[0]}")
        return len(outcomes)

    def _plan_microbatches(self, strategy_ir: Mapping, outcomes: list[Mapping]) -> list[tuple[int, int]]:
        base_size = len(encode_json_document(_trigger_input_envelope(strategy_ir, [])))
        current_start = 0
        current_count = 0
        current_size = base_size
        microbatches = []
        batch_id = None
        input_ids = set()
        for index, outcome in enumerate(outcomes):
            validate_detection_outcome(outcome, strategy_ir)
            if batch_id is None:
                batch_id = outcome["batch_id"]
            elif outcome["batch_id"] != batch_id:
                raise DetectionPublishError("detection outcomes must share one batch_id")
            if outcome["input_id"] in input_ids:
                raise DetectionPublishError("detection outcomes must not contain duplicate input_id")
            input_ids.add(outcome["input_id"])
            outcome_size = len(encode_json_document(outcome))
            added_size = outcome_size + (1 if current_count else 0)
            if current_count and (
                current_count >= self.max_outcomes_per_message or current_size + added_size > self.max_envelope_bytes
            ):
                microbatches.append((current_start, index))
                current_start = index
                current_count = 0
                current_size = base_size
                added_size = outcome_size
            if current_size + added_size > self.max_envelope_bytes:
                raise DetectionPublishError("single detection outcome exceeds the envelope byte limit")
            current_count += 1
            current_size += added_size
        if current_count:
            microbatches.append((current_start, len(outcomes)))
        return microbatches


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
    max_outcomes_per_message = producer_config.pop(
        "alarm.engine.max.outcomes.per.message", DEFAULT_MAX_OUTCOMES_PER_MESSAGE
    )
    max_envelope_bytes = producer_config.pop("alarm.engine.max.envelope.bytes", DEFAULT_MAX_ENVELOPE_BYTES)
    if producer_config.get("enable.idempotence", True) is not True:
        raise ValueError("detection Kafka producer idempotence must be enabled")
    producer_config["enable.idempotence"] = True
    if producer_factory is None:
        from confluent_kafka import Producer

        producer_factory = Producer
    producer = producer_factory(producer_config)
    return KafkaDetectionPublisher(
        producer=producer,
        topic=topic,
        flush_timeout=flush_timeout,
        max_outcomes_per_message=max_outcomes_per_message,
        max_envelope_bytes=max_envelope_bytes,
    )


@lru_cache(maxsize=1)
def get_cached_kafka_detection_publisher(config_json: str, allowed_topics: tuple[str, ...]):
    started_at = time.monotonic()
    config = decode_json_document(config_json)
    publisher = build_kafka_detection_publisher(config, allowed_topics=set(allowed_topics))
    duration_ms = max(0, round((time.monotonic() - started_at) * 1000))
    logger.info(
        "[alarmd shadow] component=alarmd-python stage=detection result=enabled records=0 duration_ms=%s",
        duration_ms,
    )
    return publisher


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


def _trigger_input_envelope(strategy_ir: Mapping, outcomes: list[Mapping]) -> dict:
    return {
        "schema": {"name": "trigger-input", "major": 1, "minor": 0},
        "required_features": [],
        "partition_hash_version": PARTITION_HASH_VERSION,
        "strategy_ir": strategy_ir,
        "detection_outcomes": outcomes,
    }
