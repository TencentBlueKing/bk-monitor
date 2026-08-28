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
from contextlib import contextmanager

from core.prometheus import metrics

# This module is the only Django-facing seam of the alarmd package: the
# contract, encoder, publisher and reference modules stay importable without a
# settings module so their cross-language Golden runs standalone.

STAGE_REFERENCE = "reference"

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

STATUS_SOURCE = "source"
STATUS_PLANNED = "planned"
STATUS_ACKED = "acked"
STATUS_DROPPED = "dropped"
STATUS_ACK_UNKNOWN = "ack_unknown"


def record_shadow_async_job(stage: str, status: str) -> None:
    metrics.ALARMD_SHADOW_ASYNC_JOB_COUNT.labels(stage=stage, status=status).inc()


@contextmanager
def observe_shadow_publish(stage: str):
    """Record one isolated Shadow publish attempt and how long its ACK took.

    The bypass is fail-open for the Python main chain, so a broker rejection is only ever
    visible here and in the logs. Labels stay a bounded enum and never expand by
    strategy, topic, partition or error text.
    """

    started_at = time.time()
    try:
        yield
    except Exception:
        _observe(stage, STATUS_FAILED, time.time() - started_at)
        raise
    _observe(stage, STATUS_SUCCESS, time.time() - started_at)


def record_shadow_published_records(stage: str, count: int) -> None:
    """Record acknowledged records, the numerator Comparator coverage is measured against."""

    if count > 0:
        metrics.ALARMD_SHADOW_PUBLISH_RECORD_COUNT.labels(stage=stage).inc(count)


def record_shadow_access_funnel(
    *,
    source_records: int,
    planned_records: int,
    planned_messages: int,
    planned_bytes: int,
    acked_records: int,
    acked_messages: int,
    acked_bytes: int,
    dropped_records: int,
    dropped_messages: int,
    dropped_bytes: int,
    ack_unknown_records: int,
    ack_unknown_messages: int,
    ack_unknown_bytes: int,
) -> None:
    """Record one completed Access v2 job using three independent units."""

    values = (
        source_records,
        planned_records,
        planned_messages,
        planned_bytes,
        acked_records,
        acked_messages,
        acked_bytes,
        dropped_records,
        dropped_messages,
        dropped_bytes,
        ack_unknown_records,
        ack_unknown_messages,
        ack_unknown_bytes,
    )
    if any(value < 0 for value in values):
        raise ValueError("alarmd Access v2 funnel counters must be non-negative")
    if (
        planned_records > source_records
        or planned_records != acked_records + dropped_records + ack_unknown_records
        or planned_messages != acked_messages + dropped_messages + ack_unknown_messages
        or planned_bytes != acked_bytes + dropped_bytes + ack_unknown_bytes
    ):
        raise ValueError("alarmd Access v2 planned cohort does not conserve")

    _increment(metrics.ALARMD_SHADOW_ACCESS_RECORD_COUNT, STATUS_SOURCE, source_records)
    _increment(metrics.ALARMD_SHADOW_ACCESS_RECORD_COUNT, STATUS_ACKED, acked_records)
    _increment(
        metrics.ALARMD_SHADOW_ACCESS_RECORD_COUNT,
        STATUS_DROPPED,
        source_records - planned_records + dropped_records,
    )
    _increment(metrics.ALARMD_SHADOW_ACCESS_RECORD_COUNT, STATUS_ACK_UNKNOWN, ack_unknown_records)

    _increment(metrics.ALARMD_SHADOW_ACCESS_MESSAGE_COUNT, STATUS_PLANNED, planned_messages)
    _increment(metrics.ALARMD_SHADOW_ACCESS_MESSAGE_COUNT, STATUS_ACKED, acked_messages)
    _increment(metrics.ALARMD_SHADOW_ACCESS_MESSAGE_COUNT, STATUS_DROPPED, dropped_messages)
    _increment(metrics.ALARMD_SHADOW_ACCESS_MESSAGE_COUNT, STATUS_ACK_UNKNOWN, ack_unknown_messages)

    _increment(metrics.ALARMD_SHADOW_ACCESS_BYTES, STATUS_PLANNED, planned_bytes)
    _increment(metrics.ALARMD_SHADOW_ACCESS_BYTES, STATUS_ACKED, acked_bytes)
    _increment(metrics.ALARMD_SHADOW_ACCESS_BYTES, STATUS_DROPPED, dropped_bytes)
    _increment(metrics.ALARMD_SHADOW_ACCESS_BYTES, STATUS_ACK_UNKNOWN, ack_unknown_bytes)


def _increment(counter, status: str, count: int) -> None:
    if count > 0:
        counter.labels(status=status).inc(count)


def _observe(stage: str, status: str, elapsed: float) -> None:
    metrics.ALARMD_SHADOW_PUBLISH_COUNT.labels(stage=stage, status=status).inc()
    metrics.ALARMD_SHADOW_PUBLISH_TIME.labels(stage=stage, status=status).observe(elapsed)
