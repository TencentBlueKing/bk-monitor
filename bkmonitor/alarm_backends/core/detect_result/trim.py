"""Trigger-safe CHECK_RESULT trimming orchestration."""

import logging
from contextlib import contextmanager

from alarm_backends.core.cache.key import (
    ANOMALY_LIST_KEY,
    CHECK_RESULT_PRODUCER_INFLIGHT_KEY,
    SERVICE_LOCK_CHECK_RESULT_PRODUCER_GATE,
    SERVICE_LOCK_TRIGGER,
    TRIGGER_CHECK_RESULT_INFLIGHT_KEY,
)
from alarm_backends.core.detect_result import CheckResult, CheckResultTrimAborted
from alarm_backends.core.detect_result_retention import InvalidRetentionConfig
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.core.storage.redis_cluster import routing_snapshot
from bkmonitor.utils.common_utils import uniqid4
from core.errors.alarm_backends import LockError

logger = logging.getLogger("core.detect_result")


def begin_check_result_producer(strategy_id) -> str:
    """Register a CHECK_RESULT producer and pass the trim admission gate before writing."""
    token = uniqid4()
    producer_key = CHECK_RESULT_PRODUCER_INFLIGHT_KEY.get_key(strategy_id=strategy_id)
    try:
        CHECK_RESULT_PRODUCER_INFLIGHT_KEY.client.hset(producer_key, token, 1)
    except Exception:
        logger.exception("register check result producer failed for strategy(%s)", strategy_id)
        raise

    # Token is visible before waiting for the gate, so an active trim stops at its next bounded chunk.
    # The producer must pass the same gate before writing any CHECK_RESULT member.
    while True:
        try:
            with service_lock(SERVICE_LOCK_CHECK_RESULT_PRODUCER_GATE, strategy_id=strategy_id):
                break
        except LockError:
            continue
    return token


def end_check_result_producer(strategy_id, token) -> None:
    """Clear only the current producer token; failures intentionally remain fail-closed."""
    if not token:
        return
    producer_key = CHECK_RESULT_PRODUCER_INFLIGHT_KEY.get_key(strategy_id=strategy_id)
    try:
        CHECK_RESULT_PRODUCER_INFLIGHT_KEY.client.hdel(producer_key, token)
    except Exception:
        logger.exception("clear check result producer failed for strategy(%s)", strategy_id)


@contextmanager
def check_result_producer(strategy_id):
    token = begin_check_result_producer(strategy_id)
    try:
        yield token
    finally:
        end_check_result_producer(strategy_id, token)


def _is_only_check_result_producer(producer_key, producer_token) -> bool:
    if not producer_token:
        return False
    return CHECK_RESULT_PRODUCER_INFLIGHT_KEY.client.hlen(
        producer_key
    ) == 1 and CHECK_RESULT_PRODUCER_INFLIGHT_KEY.client.hexists(producer_key, producer_token)


def _is_trigger_idle(anomaly_list_key, inflight_key) -> bool:
    return not (
        ANOMALY_LIST_KEY.client.llen(anomaly_list_key) or TRIGGER_CHECK_RESULT_INFLIGHT_KEY.client.hlen(inflight_key)
    )


def _ensure_producer_lock(producer_lock) -> bool:
    if producer_lock is None:
        return False
    return producer_lock.refresh() or producer_lock.acquire(0.1)


def _can_trim_next_chunk(
    *,
    producer_key,
    producer_token,
    anomaly_list_key,
    inflight_key,
    producer_lock,
    trigger_lock,
    producer_gate_lock,
) -> bool:
    if not (producer_lock.refresh() and trigger_lock.refresh() and producer_gate_lock.refresh()):
        return False
    with routing_snapshot():
        return _is_only_check_result_producer(producer_key, producer_token) and _is_trigger_idle(
            anomaly_list_key,
            inflight_key,
        )


def trim_item_check_results_if_trigger_idle(item, producer_token, producer_lock) -> bool:
    """Trim a completed Detect/NoData batch only when producers and Trigger are idle.

    Standard Detect/NoData register a strategy producer token before writing and may trim.
    Access-Detect merge registers the same blocker token but never calls this function.
    """
    cache_keys = item.pop_check_result_trim_cache_keys()
    if not cache_keys or not item.is_detect_result_rank_trim_eligible():
        return False

    anomaly_list_key = ANOMALY_LIST_KEY.get_key(strategy_id=item.strategy.id, item_id=item.id)
    inflight_key = TRIGGER_CHECK_RESULT_INFLIGHT_KEY.get_key(strategy_id=item.strategy.id, item_id=item.id)
    producer_key = CHECK_RESULT_PRODUCER_INFLIGHT_KEY.get_key(strategy_id=item.strategy.id)
    try:
        point_remain = item.get_detect_result_retention_point_required()
        with routing_snapshot():
            if not _is_only_check_result_producer(producer_key, producer_token) or not _is_trigger_idle(
                anomaly_list_key, inflight_key
            ):
                return False
    except InvalidRetentionConfig as error:
        logger.warning(
            "skip check result rank trim for strategy(%s) item(%s): %s",
            item.strategy.id,
            item.id,
            error,
        )
        return False
    except Exception:
        logger.exception(
            "prepare check result rank trim failed for strategy(%s) item(%s)",
            item.strategy.id,
            item.id,
        )
        return False

    try:
        with (
            service_lock(SERVICE_LOCK_TRIGGER, strategy_id=item.strategy.id, item_id=item.id) as trigger_lock,
            service_lock(SERVICE_LOCK_CHECK_RESULT_PRODUCER_GATE, strategy_id=item.strategy.id) as producer_gate_lock,
        ):
            if not _ensure_producer_lock(producer_lock):
                return False
            with routing_snapshot():
                if not _is_only_check_result_producer(producer_key, producer_token) or not _is_trigger_idle(
                    anomaly_list_key, inflight_key
                ):
                    return False

                def before_chunk():
                    return _can_trim_next_chunk(
                        producer_key=producer_key,
                        producer_token=producer_token,
                        anomaly_list_key=anomaly_list_key,
                        inflight_key=inflight_key,
                        producer_lock=producer_lock,
                        trigger_lock=trigger_lock,
                        producer_gate_lock=producer_gate_lock,
                    )

                CheckResult.trim_check_result_caches(
                    cache_keys,
                    point_remain,
                    before_chunk=before_chunk,
                )
    except (LockError, CheckResultTrimAborted):
        return False
    except Exception:
        logger.exception(
            "trim check result cache failed for strategy(%s) item(%s)",
            item.strategy.id,
            item.id,
        )
        return False
    return True
