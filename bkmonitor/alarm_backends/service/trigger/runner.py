"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
import uuid
from collections import deque
from contextlib import nullcontext

from django.conf import settings

from alarm_backends.core.cache.key import (
    ANOMALY_LIST_KEY,
    ANOMALY_SIGNAL_KEY,
    EVENT_INLINE_TRIGGER_LEASE_KEY,
    SERVICE_LOCK_TRIGGER,
)
from alarm_backends.core.cache.delay_queue import DelayQueueManager
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.processor.base import BaseAbnormalPushProcessor
from alarm_backends.core.storage.redis_cluster import routed_client
from alarm_backends.service.trigger.processor import TriggerProcessor
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("trigger")

EVENT_TRIGGER_BATCH_SIZE = 1000
EVENT_TRIGGER_LEASE_TTL = 300
EVENT_TRIGGER_LEASE_RENEW_INTERVAL = 60

EVENT_TRIGGER_ACQUIRE_LEASE_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[4]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return 1
"""

EVENT_TRIGGER_RENEW_LEASE_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if not redis.call('ZSCORE', KEYS[1], ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
return 1
"""

EVENT_TRIGGER_RELEASE_LEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
if redis.call('ZCARD', KEYS[1]) == 0 then
    redis.call('DEL', KEYS[1])
end
return redis.call('LLEN', KEYS[2])
"""

EVENT_TRIGGER_SCHEDULE_RETRY_SCRIPT = """
if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then
    return 0
end
redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
redis.call('ZADD', KEYS[2], ARGV[3], ARGV[1])
return 1
"""


def _event_trigger_keys(strategy_id, item_id):
    lease_key = EVENT_INLINE_TRIGGER_LEASE_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
    anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
    return lease_key, anomaly_list_key


def _acquire_event_trigger_lease(strategy_id, item_id, token, max_concurrency):
    lease_key, _ = _event_trigger_keys(strategy_id, item_id)
    now = int(time.time())
    with routed_client(EVENT_INLINE_TRIGGER_LEASE_KEY.client, lease_key) as client:
        acquired = client.eval(
            EVENT_TRIGGER_ACQUIRE_LEASE_SCRIPT,
            1,
            lease_key,
            now,
            now + EVENT_TRIGGER_LEASE_TTL,
            token,
            max_concurrency,
            EVENT_TRIGGER_LEASE_TTL * 2,
        )
    return bool(acquired)


def _renew_event_trigger_lease(strategy_id, item_id, token):
    lease_key, _ = _event_trigger_keys(strategy_id, item_id)
    now = int(time.time())
    with routed_client(EVENT_INLINE_TRIGGER_LEASE_KEY.client, lease_key) as client:
        renewed = client.eval(
            EVENT_TRIGGER_RENEW_LEASE_SCRIPT,
            1,
            lease_key,
            now,
            now + EVENT_TRIGGER_LEASE_TTL,
            token,
            EVENT_TRIGGER_LEASE_TTL * 2,
        )
    return bool(renewed)


def _release_event_trigger_lease(strategy_id, item_id, token):
    lease_key, anomaly_list_key = _event_trigger_keys(strategy_id, item_id)
    with routed_client(EVENT_INLINE_TRIGGER_LEASE_KEY.client, lease_key) as client:
        return int(
            client.eval(
                EVENT_TRIGGER_RELEASE_LEASE_SCRIPT,
                2,
                lease_key,
                anomaly_list_key,
                token,
            )
        )


def _schedule_event_trigger_retry_signal(strategy_id, item_id):
    """租约占满时原子登记一次延迟 Signal，避免持有者退出后没有后续输入唤醒。"""
    signal_queue_key = ANOMALY_SIGNAL_KEY.get_key()
    signal = f"{strategy_id}.{item_id}"
    task_id = f"event-inline-trigger-retry:{signal}"
    scheduled_at = time.time() + EVENT_TRIGGER_LEASE_TTL
    message = json.dumps([task_id, "lpush", signal_queue_key, [signal], scheduled_at])
    with routed_client(ANOMALY_SIGNAL_KEY.client, signal_queue_key) as client:
        scheduled = client.eval(
            EVENT_TRIGGER_SCHEDULE_RETRY_SCRIPT,
            2,
            DelayQueueManager.TASK_STORAGE_QUEUE,
            DelayQueueManager.TASK_DELAY_QUEUE,
            task_id,
            message,
            scheduled_at,
        )
    return bool(scheduled)


def run_trigger_item(
    strategy_id,
    item_id,
    executor="trigger_worker",
    acquire_lock=True,
    max_process_count=None,
    requeue_on_full=True,
    raise_process_error=False,
    concurrent_rate_limit=None,
    progress_callback=None,
):
    logger.info(
        "[start][latency] strategy(%s), item(%s), executor(%s)",
        strategy_id,
        item_id,
        executor,
    )
    inline_trigger_enabled = (
        settings.ENABLE_DETECT_INLINE_TRIGGER or getattr(settings, "ENABLE_EVENT_INLINE_TRIGGER", False) is True
    )
    exc = None
    pulled_count = 0
    process_started_at = None
    try:
        lock_context = (
            service_lock(SERVICE_LOCK_TRIGGER, strategy_id=strategy_id, item_id=item_id)
            if acquire_lock
            else nullcontext()
        )
        with lock_context:
            process_started_at = time.monotonic()
            if (
                max_process_count is None
                and requeue_on_full
                and concurrent_rate_limit is None
                and progress_callback is None
            ):
                processor = TriggerProcessor(strategy_id, item_id)
            else:
                processor_kwargs = {
                    "max_process_count": max_process_count,
                    "requeue_on_full": requeue_on_full,
                    "concurrent_rate_limit": concurrent_rate_limit,
                }
                if progress_callback is not None:
                    processor_kwargs["progress_callback"] = progress_callback
                processor = TriggerProcessor(strategy_id, item_id, **processor_kwargs)
            pulled_count = processor.process()
    except LockError:
        if process_started_at is not None:
            metrics.TRIGGER_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(
                time.monotonic() - process_started_at
            )
        raise
    except Exception as error:
        exc = error
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
    should_record_metrics = exc is not None or pulled_count > 0 or not inline_trigger_enabled
    if should_record_metrics:
        if process_started_at is not None:
            metrics.TRIGGER_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(
                time.monotonic() - process_started_at
            )
        metrics.TRIGGER_PROCESS_COUNT.labels(
            strategy_id=metrics.TOTAL_TAG,
            status=metrics.StatusEnum.from_exc(exc),
            exception=exc,
        ).inc()
    if exc is not None and raise_process_error:
        raise exc
    return pulled_count


def run_event_trigger_item(strategy_id, item_id):
    """在 Event Worker 内取得租约并处理一个有限批次，返回当前策略项是否仍有待处理数据。"""
    max_concurrency = max(1, int(settings.EVENT_INLINE_TRIGGER_MAX_CONCURRENCY_PER_ITEM))
    token = uuid.uuid4().hex
    try:
        acquired = _acquire_event_trigger_lease(strategy_id, item_id, token, max_concurrency)
    except Exception:
        logger.exception(
            "[event inline trigger] acquire lease failed for strategy(%s), item(%s); publish fallback signal",
            strategy_id,
            item_id,
        )
        try:
            BaseAbnormalPushProcessor.publish_anomaly_signals([f"{strategy_id}.{item_id}"])
        except Exception:
            logger.exception(
                "[event inline trigger] fallback signal failed for strategy(%s), item(%s)",
                strategy_id,
                item_id,
            )
        return False

    if not acquired:
        try:
            scheduled = _schedule_event_trigger_retry_signal(strategy_id, item_id)
            logger.debug(
                "[event inline trigger] concurrency full for strategy(%s), item(%s), retry_scheduled(%s)",
                strategy_id,
                item_id,
                scheduled,
            )
        except Exception:
            logger.exception(
                "[event inline trigger] schedule retry failed for strategy(%s), item(%s); publish fallback signal",
                strategy_id,
                item_id,
            )
            try:
                BaseAbnormalPushProcessor.publish_anomaly_signals([f"{strategy_id}.{item_id}"])
            except Exception:
                logger.exception(
                    "[event inline trigger] fallback signal failed for strategy(%s), item(%s)",
                    strategy_id,
                    item_id,
                )
        return False

    last_renewed_at = time.monotonic()
    lease_active = True

    def renew_lease_on_progress():
        nonlocal last_renewed_at, lease_active
        if not lease_active:
            return
        now = time.monotonic()
        if now - last_renewed_at < EVENT_TRIGGER_LEASE_RENEW_INTERVAL:
            return
        last_renewed_at = now
        try:
            renewed = _renew_event_trigger_lease(strategy_id, item_id, token)
        except Exception:
            logger.exception(
                "[event inline trigger] renew lease failed for strategy(%s), item(%s)",
                strategy_id,
                item_id,
            )
            return
        if not renewed:
            lease_active = False
            logger.warning(
                "[event inline trigger] lease expired for strategy(%s), item(%s); finish current claimed batch",
                strategy_id,
                item_id,
            )

    try:
        run_trigger_item(
            strategy_id,
            item_id,
            executor="event_inline",
            acquire_lock=False,
            max_process_count=EVENT_TRIGGER_BATCH_SIZE,
            requeue_on_full=False,
            raise_process_error=True,
            concurrent_rate_limit=True,
            progress_callback=renew_lease_on_progress,
        )
        return _release_event_trigger_lease(strategy_id, item_id, token) > 0
    except Exception:
        logger.exception(
            "[event inline trigger] process failed for strategy(%s), item(%s)",
            strategy_id,
            item_id,
        )
        try:
            remaining_count = _release_event_trigger_lease(strategy_id, item_id, token)
        except Exception:
            logger.exception(
                "[event inline trigger] release lease failed for strategy(%s), item(%s)",
                strategy_id,
                item_id,
            )
            remaining_count = 0
        if remaining_count > 0:
            try:
                BaseAbnormalPushProcessor.publish_anomaly_signals([f"{strategy_id}.{item_id}"])
            except Exception:
                logger.exception(
                    "[event inline trigger] fallback signal failed for strategy(%s), item(%s)",
                    strategy_id,
                    item_id,
                )
        return False


def run_event_trigger_items(items):
    """按有限批次轮转 Event 策略项，避免热点项持续非空时阻塞同批后续项。"""
    pending_items = deque(items)
    while pending_items:
        strategy_id, item_id = pending_items.popleft()
        if run_event_trigger_item(strategy_id, item_id):
            pending_items.append((strategy_id, item_id))
