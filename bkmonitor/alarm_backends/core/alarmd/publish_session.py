"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from alarm_backends.core.alarmd.publisher import KafkaDetectInputPublisher
from alarm_backends.core.alarmd.reference_publisher import KafkaReferenceDecisionPublisher


@dataclass(frozen=True)
class ShadowPublishResult:
    acknowledged_records: int
    elapsed: float
    error: Exception | None = None
    shared_flush: bool = False


def publish_post_detection_shadow(
    *,
    detect_input_publisher=None,
    detect_input: Mapping | None = None,
    reference_publisher=None,
    reference_batches: Iterable[Mapping] = (),
) -> tuple[ShadowPublishResult | None, ShadowPublishResult | None]:
    """Publish post-detection Shadow stages, sharing one ACK barrier when safe."""

    has_detect_input = detect_input_publisher is not None and detect_input is not None
    reference_batches = list(reference_batches)
    has_reference = reference_publisher is not None and bool(reference_batches)
    if not has_detect_input and not has_reference:
        return None, None

    if not _can_share_flush(detect_input_publisher, reference_publisher, has_detect_input, has_reference):
        return (
            _publish_detect_input(detect_input_publisher, detect_input) if has_detect_input else None,
            _publish_reference(reference_publisher, reference_batches) if has_reference else None,
        )

    detect_started_at = time.monotonic()
    try:
        detect_prepared = detect_input_publisher.prepare_batch(detect_input)
    except Exception as error:
        return (
            _failed_result(detect_started_at, error),
            _publish_reference(reference_publisher, reference_batches),
        )

    reference_started_at = time.monotonic()
    try:
        reference_prepared = reference_publisher.prepare_single_ack_group(reference_batches)
    except Exception as error:
        return (
            _publish_detect_input(detect_input_publisher, detect_input),
            _failed_result(reference_started_at, error),
        )
    if reference_prepared is None:
        return (
            _publish_detect_input(detect_input_publisher, detect_input),
            _publish_reference(reference_publisher, reference_batches),
        )

    detect_receipt = detect_input_publisher.enqueue_prepared(detect_prepared)
    reference_receipt = reference_publisher.enqueue_prepared(reference_prepared)
    try:
        detect_input_publisher.producer.flush(timeout=detect_input_publisher.flush_timeout)
    except Exception:
        # Delivery callbacks are scoped to each stage; a shared Producer flush error
        # must not invalidate a stage whose own records were already acknowledged.
        pass

    return (
        _resolve_shared(
            detect_input_publisher.resolve_receipt,
            detect_receipt,
            detect_started_at,
        ),
        _resolve_shared(
            reference_publisher.resolve_receipt,
            reference_receipt,
            reference_started_at,
        ),
    )


def _can_share_flush(detect_input_publisher, reference_publisher, has_detect_input: bool, has_reference: bool) -> bool:
    return (
        has_detect_input
        and has_reference
        and isinstance(detect_input_publisher, KafkaDetectInputPublisher)
        and isinstance(reference_publisher, KafkaReferenceDecisionPublisher)
        and detect_input_publisher.producer is reference_publisher.producer
        and detect_input_publisher.flush_timeout == reference_publisher.flush_timeout
    )


def _publish_detect_input(publisher, batch: Mapping) -> ShadowPublishResult:
    started_at = time.monotonic()
    try:
        acknowledged = publisher.publish_batch(batch)
    except Exception as error:
        return _failed_result(started_at, error)
    return _successful_result(started_at, acknowledged)


def _publish_reference(publisher, batches: list[Mapping]) -> ShadowPublishResult:
    started_at = time.monotonic()
    acknowledged = 0
    try:
        if hasattr(publisher, "publish_batches"):
            acknowledged = publisher.publish_batches(batches)
        else:
            for batch in batches:
                acknowledged += publisher.publish_batch(batch)
    except Exception as error:
        acknowledged += getattr(error, "acknowledged_records", 0)
        return _failed_result(started_at, error, acknowledged_records=acknowledged)
    return _successful_result(started_at, acknowledged)


def _resolve_shared(resolve, receipt, started_at: float) -> ShadowPublishResult:
    try:
        acknowledged = resolve(receipt)
    except Exception as error:
        return _failed_result(
            started_at,
            error,
            acknowledged_records=receipt.acknowledged_records,
            shared_flush=True,
        )
    return _successful_result(started_at, acknowledged, shared_flush=True)


def _successful_result(started_at: float, acknowledged_records: int, *, shared_flush: bool = False):
    return ShadowPublishResult(
        acknowledged_records=acknowledged_records,
        elapsed=max(0, time.monotonic() - started_at),
        shared_flush=shared_flush,
    )


def _failed_result(
    started_at: float,
    error: Exception,
    *,
    acknowledged_records: int = 0,
    shared_flush: bool = False,
):
    acknowledged_records = max(acknowledged_records, getattr(error, "acknowledged_records", 0))
    return ShadowPublishResult(
        acknowledged_records=acknowledged_records,
        elapsed=max(0, time.monotonic() - started_at),
        error=error,
        shared_flush=shared_flush,
    )
