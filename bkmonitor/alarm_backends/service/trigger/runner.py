"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from alarm_backends.core.cache.key import SERVICE_LOCK_TRIGGER
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.trigger.processor import TriggerProcessor
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("trigger")


def run_trigger_item(strategy_id, item_id, executor="trigger_worker"):
    logger.info(
        "[start][latency] strategy(%s), item(%s), executor(%s)",
        strategy_id,
        item_id,
        executor,
    )
    exc = None
    try:
        with service_lock(SERVICE_LOCK_TRIGGER, strategy_id=strategy_id, item_id=item_id):
            with metrics.TRIGGER_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).time():
                processor = TriggerProcessor(strategy_id, item_id)
                pulled_count = processor.process()
    except LockError:
        raise
    except Exception as error:
        exc = error
        pulled_count = 0
        logger.exception(
            "[process error] strategy(%s), item(%s), executor(%s), reason: %s",
            strategy_id,
            item_id,
            executor,
            error,
        )

    logger.info(
        "[end][latency] strategy(%s), item(%s), executor(%s)",
        strategy_id,
        item_id,
        executor,
    )
    if exc or pulled_count:
        metrics.TRIGGER_PROCESS_COUNT.labels(
            strategy_id=metrics.TOTAL_TAG,
            status=metrics.StatusEnum.from_exc(exc),
            exception=exc,
        ).inc()
    return pulled_count
