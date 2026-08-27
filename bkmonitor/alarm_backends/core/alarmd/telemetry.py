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


def _observe(stage: str, status: str, elapsed: float) -> None:
    metrics.ALARMD_SHADOW_PUBLISH_COUNT.labels(stage=stage, status=status).inc()
    metrics.ALARMD_SHADOW_PUBLISH_TIME.labels(stage=stage, status=status).observe(elapsed)
