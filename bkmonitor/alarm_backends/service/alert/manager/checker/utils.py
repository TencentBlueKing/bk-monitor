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
from typing import NamedTuple

from redis.exceptions import WatchError

from alarm_backends.core.cache.key import NEW_SERIES_ACTIVE_KEY
from alarm_backends.core.control.record_parser import EventIDParser
from alarm_backends.core.storage.redis_cluster import routed_client
from bkmonitor.models import AlgorithmModel
from constants.strategy import NewSeriesAlertMode


class NewSeriesLifecycleState(NamedTuple):
    active_key: str
    claimed_key: str
    terminated_key: str
    fingerprint: str
    detect_range: int
    soft_ttl: int
    max_series: int


NEW_SERIES_STATE_UPDATE_RETRIES = 3


def is_auto_level_intelligent_detect(strategy_item: dict) -> bool:
    algorithms = strategy_item.get("algorithms") or []
    if len(algorithms) != 1:
        return False

    algorithm = algorithms[0]
    config = algorithm.get("config")
    return (
        algorithm.get("type") == AlgorithmModel.AlgorithmChoices.IntelligentDetect
        and isinstance(config, dict)
        and config.get("alert_level_mode") == "auto"
    )


def resolve_new_series_lifecycle_state(alert, strategy=None):
    """从告警快照和严格五段式 event_id 定位 continuous NewSeries 生命周期状态。"""
    strategy = strategy if strategy is not None else alert.get_extra_info("strategy")
    if not isinstance(strategy, dict):
        return None

    try:
        event_id = alert.top_event["event_id"]
        if not isinstance(event_id, str) or len(event_id.split(".")) != 5:
            return None
        parser = EventIDParser(event_id)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None

    matched = None
    for item in strategy.get("items") or []:
        for algorithm in item.get("algorithms") or []:
            config = algorithm.get("config") or {}
            try:
                is_matched = (
                    algorithm.get("type") == AlgorithmModel.AlgorithmChoices.NewSeries
                    and config.get("alert_mode", NewSeriesAlertMode.ONCE) == NewSeriesAlertMode.CONTINUOUS
                    and int(item.get("id")) == parser.item_id
                    and int(algorithm.get("level")) == parser.level
                )
            except (TypeError, ValueError):
                is_matched = False
            if is_matched:
                matched = item, config
                break
        if matched:
            break
    if not matched:
        return None

    from alarm_backends.service.detect.strategy.new_series import NewSeries

    item, config = matched
    try:
        detect_range = int(config["detect_range"])
        max_series = int(config.get("max_series", 100000))
        threshold = int(config.get("threshold", 0))
    except (KeyError, TypeError, ValueError):
        return None
    query_configs = item.get("query_configs") or []
    agg_dimension = query_configs[0].get("agg_dimension") if query_configs else None
    params = {
        "strategy_id": parser.strategy_id,
        "item_id": parser.item_id,
        "dimension_signature": NewSeries.signature_from_agg_dimension(agg_dimension),
        "threshold": threshold,
        "detect_range": detect_range,
        "level": parser.level,
    }
    return NewSeriesLifecycleState(
        active_key=NewSeries.active_state_key(**params),
        claimed_key=NewSeries.claimed_state_key(**params),
        terminated_key=NewSeries.terminated_state_key(**params),
        fingerprint=parser.dimensions_md5,
        detect_range=detect_range,
        soft_ttl=NewSeries.active_soft_ttl(detect_range),
        max_series=max_series,
    )


def is_same_new_series_lifecycle(first_alert, second_alert):
    """判断两个告警是否共同持有同一 continuous NewSeries 生命周期。"""
    if not first_alert.is_abnormal() or not second_alert.is_abnormal():
        return False

    first_state = resolve_new_series_lifecycle_state(first_alert)
    second_state = resolve_new_series_lifecycle_state(second_alert)
    return bool(
        first_state
        and second_state
        and first_state.active_key == second_state.active_key
        and first_state.fingerprint == second_state.fingerprint
    )


def terminate_new_series_lifecycle_state(alert, observed_at=None):
    """原子终止告警快照对应的 continuous 生命周期，并留下短期竞态屏障。"""
    state = resolve_new_series_lifecycle_state(alert)
    if state is None:
        return False

    observed_at = int(time.time()) if observed_at is None else int(observed_at)
    stale_before = observed_at - state.soft_ttl
    proxy = NEW_SERIES_ACTIVE_KEY.client
    with routed_client(proxy, state.active_key) as client:
        for attempt in range(NEW_SERIES_STATE_UPDATE_RETRIES):
            pipe = client.pipeline(transaction=True)
            try:
                pipe.watch(state.active_key, state.claimed_key, state.terminated_key)
                marker_score = pipe.zscore(state.terminated_key, state.fingerprint)
                marker_count = int(pipe.zcard(state.terminated_key))
                stale_count = int(pipe.zcount(state.terminated_key, "-inf", stale_before))
                live_count = max(0, marker_count - stale_count)
                marker_exists = marker_score is not None and int(float(marker_score)) > stale_before
                capacity = max(0, state.max_series)
                trim_excess = max(0, live_count + (0 if marker_exists else 1) - capacity)

                pipe.multi()
                pipe.zrem(state.active_key, state.fingerprint)
                pipe.zrem(state.claimed_key, state.fingerprint)
                pipe.zremrangebyscore(state.terminated_key, "-inf", stale_before)
                pipe.zadd(state.terminated_key, {state.fingerprint: observed_at})
                if trim_excess:
                    pipe.zremrangebyrank(state.terminated_key, 0, trim_excess - 1)
                pipe.expire(state.terminated_key, state.soft_ttl)
                pipe.execute()
                return True
            except WatchError:
                if attempt + 1 == NEW_SERIES_STATE_UPDATE_RETRIES:
                    raise
            finally:
                pipe.reset()
    raise RuntimeError(f"failed to terminate NewSeries lifecycle after retries: {state.active_key}")
