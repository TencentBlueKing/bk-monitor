"""Low-frequency CHECK_RESULT trimming for high-load Access merge groups."""

import logging
import zlib
from collections.abc import Mapping

from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.item import detect_result_point_required
from alarm_backends.core.detect_result import CheckResult
from alarm_backends.core.detect_result.clean import CleanResult

logger = logging.getLogger("core.detect_result")

OPPORTUNITY_PERIOD_SECONDS = 2 * 60 * 60
OPPORTUNITY_PHASE_START_MINUTE = 30
OPPORTUNITY_PHASE_MINUTES = 60
OPPORTUNITY_MARKER_TTL_SECONDS = 5 * 60


def opportunity_minute(strategy_group_key: str) -> int:
    """Return one stable minute in the middle half of each two-hour cycle."""
    group_hash = zlib.crc32(str(strategy_group_key).encode("utf-8"))
    return OPPORTUNITY_PHASE_START_MINUTE + group_hash % OPPORTUNITY_PHASE_MINUTES


def claim_opportunity_trim(strategy_group_key: str, timestamp: float) -> bool:
    """Claim this group's opportunity only during its stable candidate minute."""
    cycle_id, offset = divmod(int(timestamp), OPPORTUNITY_PERIOD_SECONDS)
    if offset // 60 != opportunity_minute(strategy_group_key):
        return False

    marker_key = key.CHECK_RESULT_OPPORTUNITY_TRIM_MARKER_KEY.get_key(
        strategy_group_key=strategy_group_key,
        cycle_id=cycle_id,
    )
    return bool(
        key.CHECK_RESULT_OPPORTUNITY_TRIM_MARKER_KEY.client.set(
            marker_key,
            1,
            ex=OPPORTUNITY_MARKER_TTL_SECONDS,
            nx=True,
        )
    )


def _is_no_data_window_safe(item: Mapping, point_remain: int) -> bool:
    no_data_config = item.get("no_data_config", {})
    if not isinstance(no_data_config, Mapping):
        return False
    if not no_data_config.get("is_enabled"):
        return True

    continuous = no_data_config.get("continuous")
    if isinstance(continuous, bool):
        return False
    try:
        continuous = int(continuous)
    except (TypeError, ValueError):
        return False
    return continuous > 0 and continuous + 2 <= point_remain


def _check_result_keys(strategy_id: int, item_id: int, checkpoint_fields) -> list[str]:
    cache_keys = []
    for field in checkpoint_fields:
        if isinstance(field, bytes):
            field = field.decode("utf-8")
        try:
            *_, dimensions_md5, level = field.split(".")
        except ValueError:
            logger.warning(
                "skip invalid CHECK_RESULT checkpoint field for strategy(%s) item(%s): %s",
                strategy_id,
                item_id,
                field,
            )
            continue
        cache_keys.append(
            key.CHECK_RESULT_CACHE_KEY.get_key(
                strategy_id=strategy_id,
                item_id=item_id,
                dimensions_md5=dimensions_md5,
                level=level,
            )
        )
    return cache_keys


def trim_strategy_group(strategy_group_key: str) -> dict[str, int]:
    """Trim current items in one group using bounded HSCAN and ZREM only."""
    stats = {
        "strategy_count": 0,
        "item_count": 0,
        "scanned_fields": 0,
        "zrem_commands": 0,
        "removed_members": 0,
    }
    group_detail = StrategyCacheManager.get_strategy_group_detail(strategy_group_key)
    if not isinstance(group_detail, Mapping) or not group_detail:
        return stats

    target_items = {}
    for raw_strategy_id, raw_item_ids in group_detail.items():
        try:
            strategy_id = int(raw_strategy_id)
            target_items[strategy_id] = {int(item_id) for item_id in raw_item_ids}
        except (TypeError, ValueError):
            logger.warning("skip invalid strategy group member: %s=%s", raw_strategy_id, raw_item_ids)

    strategies = StrategyCacheManager.get_strategy_by_ids(list(target_items))
    checkpoint_client = key.LAST_CHECKPOINTS_CACHE_KEY.client
    for strategy in strategies:
        strategy_id = strategy.get("id")
        if strategy_id not in target_items:
            continue
        try:
            point_remain = detect_result_point_required(strategy)
        except Exception:
            logger.exception("skip opportunity trim with invalid strategy(%s) retention", strategy_id)
            continue

        stats["strategy_count"] += 1
        for item in strategy.get("items") or []:
            item_id = item.get("id")
            if item_id not in target_items[strategy_id] or not _is_no_data_window_safe(item, point_remain):
                continue

            stats["item_count"] += 1
            checkpoint_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
            cursor = 0
            try:
                while True:
                    next_cursor, checkpoint_fields = CleanResult.scan_last_checkpoint_page(
                        checkpoint_client,
                        checkpoint_key,
                        cursor=cursor,
                        count=settings.CHECK_RESULT_CLEAN_HSCAN_COUNT,
                        max_fields=settings.CHECK_RESULT_CLEAN_HSCAN_MAX_FIELDS,
                    )
                    stats["scanned_fields"] += len(checkpoint_fields)
                    cache_keys = _check_result_keys(strategy_id, item_id, checkpoint_fields)
                    if cache_keys:
                        removed = CheckResult.trim_check_result_caches(cache_keys, point_remain)
                        stats["zrem_commands"] += len(cache_keys)
                        stats["removed_members"] += sum(int(value or 0) for value in removed)
                    if next_cursor == 0:
                        break
                    cursor = next_cursor
            except Exception:
                logger.exception(
                    "skip failed CHECK_RESULT opportunity trim for strategy(%s) item(%s)",
                    strategy_id,
                    item_id,
                )
    return stats
