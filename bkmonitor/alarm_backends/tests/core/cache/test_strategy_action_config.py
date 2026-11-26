"""
策略增量刷新前同步近期变更套餐的回归测试。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import LockNotOwnedError, WatchError
from redis.lock import Lock

from alarm_backends.core.cache import action_config as config_module
from alarm_backends.core.cache import strategy as strategy_module
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager


def test_smart_refresh_updates_recent_action_configs_before_strategies(monkeypatch):
    calls = []

    def refresh(minutes):
        calls.append(("action_config", minutes))
        return True

    monkeypatch.setattr(
        ActionConfigCacheManager,
        "refresh",
        refresh,
    )
    monkeypatch.setattr(StrategyCacheManager, "smart_refresh", lambda: calls.append(("strategy", None)))

    strategy_module.smart_refresh()

    assert calls == [("action_config", 5), ("strategy", None)]


def test_smart_refresh_stops_when_action_config_refresh_fails(monkeypatch):
    strategy_refresh = mock.MagicMock()
    monkeypatch.setattr(
        ActionConfigCacheManager,
        "refresh",
        mock.MagicMock(side_effect=RuntimeError("action config refresh failed")),
    )
    monkeypatch.setattr(StrategyCacheManager, "smart_refresh", strategy_refresh)

    with pytest.raises(RuntimeError, match="action config refresh failed"):
        strategy_module.smart_refresh()

    strategy_refresh.assert_not_called()


def test_full_refresh_does_not_refresh_action_configs(monkeypatch):
    action_config_refresh = mock.MagicMock()
    strategy_refresh = mock.MagicMock()
    monkeypatch.setattr(ActionConfigCacheManager, "refresh", action_config_refresh)
    monkeypatch.setattr(StrategyCacheManager, "refresh", strategy_refresh)

    strategy_module.main()

    strategy_refresh.assert_called_once_with()
    action_config_refresh.assert_not_called()


@pytest.fixture
def cache(monkeypatch):
    cache = fakeredis.FakeRedis(server=fakeredis.FakeServer())
    monkeypatch.setattr(ActionConfigCacheManager, "cache", cache)
    monkeypatch.setattr(StrategyCacheManager, "cache", cache)
    return cache


@pytest.fixture
def clock(monkeypatch):
    clock = mock.Mock(wraps=datetime)
    clock.now.return_value = datetime(2025, 1, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(config_module, "datetime", clock)
    return clock


def test_first_failure_retries_window_and_applies_updates_and_deletes(cache, clock, monkeypatch):
    manager = ActionConfigCacheManager
    first = clock.now.return_value
    old_config = SimpleNamespace(id=1, is_deleted=False)
    deleted = SimpleNamespace(id=2, is_deleted=True)
    changes = {first - timedelta(minutes=4): [old_config, deleted]}
    plugin = mock.Mock()
    plugin.origin_objects.filter.return_value.values_list.return_value = []
    monkeypatch.setattr(config_module, "ActionPlugin", plugin)
    monkeypatch.setattr(config_module, "ActionPluginSlz", lambda **kwargs: SimpleNamespace(data=[]))
    monkeypatch.setattr(
        config_module,
        "ActionConfigDetailSlz",
        lambda instance, many: SimpleNamespace(data=[{"id": c.id, "name": "new"} for c in instance]),
    )
    model = mock.Mock()
    monkeypatch.setattr(config_module, "ActionConfig", model)
    for config in (old_config, deleted):
        manager.set_action_config_cache(config.id, {"name": "old"})
    model.origin_objects.filter.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        manager.refresh(minutes=5)
    start = first - timedelta(minutes=5)
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == int(start.timestamp())

    def recent(update_time__gte):
        return [config for timestamp, batch in changes.items() if timestamp >= update_time__gte for config in batch]

    model.origin_objects.filter.side_effect = recent
    clock.now.return_value = first + timedelta(minutes=10)
    assert manager.refresh(minutes=5)
    model.origin_objects.filter.assert_called_with(update_time__gte=start)
    assert manager.get_action_config_by_id(old_config.id)["name"] == "new"
    assert manager.get_action_config_by_id(deleted.id) == {}
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == int(clock.now.return_value.timestamp())
    clock.now.return_value += timedelta(minutes=1)
    assert manager.refresh(minutes=5)
    model.origin_objects.filter.assert_called_with(update_time__gte=clock.now.return_value - timedelta(minutes=5))


def test_incremental_conflict_preserves_new_publication(cache, clock, monkeypatch):
    manager = ActionConfigCacheManager
    start = int(clock.now.return_value.timestamp())
    cache.set(manager.LAST_REFRESH_KEY, start - 600)

    def queue_old(pipeline, since):
        with cache.pipeline() as newer:
            newer.set("config", "new")
            newer.set(manager.LAST_REFRESH_KEY, start + 1)
            newer.execute()
        pipeline.set("config", "old")

    monkeypatch.setattr(manager, "_queue_refresh", queue_old)
    assert not manager.refresh(minutes=5)
    assert cache.get("config") == b"new"
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == start + 1
    monkeypatch.setattr(manager, "_queue_refresh", mock.Mock())
    assert manager.refresh(minutes=5)
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == start + 1


def test_connection_failure_while_watching_is_reported(cache, clock, monkeypatch):
    def fail(*args, **kwargs):
        try:
            raise RedisConnectionError("disconnected")
        except RedisConnectionError:
            raise WatchError("connection lost")

    monkeypatch.setattr(ActionConfigCacheManager, "_queue_refresh", fail)
    with pytest.raises(WatchError):
        ActionConfigCacheManager.refresh(minutes=5)


def test_full_refresh_defers_strategies_and_preserves_incremental_window(cache, clock, monkeypatch):
    manager = ActionConfigCacheManager
    initial = int(clock.now.return_value.timestamp()) - 600
    cache.set(manager.LAST_REFRESH_KEY, initial)
    strategy_refresh = mock.Mock()
    monkeypatch.setattr(StrategyCacheManager, "smart_refresh", strategy_refresh)
    # fakeredis 无 Lua 扩展时不实现 redis-py 的原子释放脚本。
    monkeypatch.setattr(Lock, "do_release", lambda lock, token: cache.delete(lock.name))

    competing_full = mock.Mock(side_effect=manager.refresh)

    def during_full(pipeline, since=None):
        assert since is None
        competing_full.assert_not_called()
        assert not competing_full()  # 未取得锁的全量不能作废持有者的发布事务。
        strategy_module.smart_refresh()
        strategy_refresh.assert_not_called()
        pipeline.set("config", "full")

    monkeypatch.setattr(manager, "_queue_refresh", during_full)
    assert manager.refresh()
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == initial
    recent = mock.Mock()
    monkeypatch.setattr(manager, "_queue_refresh", recent)
    strategy_module.smart_refresh()
    assert recent.call_args.kwargs["since"].timestamp() == initial
    strategy_refresh.assert_called_once_with()


def test_full_refresh_losing_lease_cannot_publish(cache, clock, monkeypatch):
    manager = ActionConfigCacheManager
    start = int(clock.now.return_value.timestamp())

    def replace_owner(pipeline):
        cache.set(manager.FULL_REFRESH_LOCK, "new-owner")
        cache.set(manager.LAST_REFRESH_KEY, start)
        cache.set("config", "new")
        pipeline.set("config", "old")

    monkeypatch.setattr(manager, "_queue_refresh", replace_owner)
    monkeypatch.setattr(Lock, "do_release", mock.Mock(side_effect=LockNotOwnedError()))
    with pytest.raises(LockNotOwnedError):
        manager.refresh()
    assert cache.get(manager.FULL_REFRESH_LOCK) == b"new-owner"
    assert cache.get("config") == b"new"
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == start


def test_full_refresh_takeover_after_ownership_check_invalidates_old_transaction(cache, clock, monkeypatch):
    manager = ActionConfigCacheManager
    cache.set(manager.LAST_REFRESH_KEY, 123)
    cache.set("config", "published")
    monkeypatch.setattr(manager, "_queue_refresh", lambda pipeline: pipeline.set("config", "obsolete"))
    owned = Lock.owned

    def takeover_after_check(lock):
        result = owned(lock)
        if result:
            cache.delete(lock.name)  # 旧持有者在检查之后失去租约。
            with monkeypatch.context() as replacement:
                replacement.setattr(manager, "_queue_refresh", mock.Mock(side_effect=RuntimeError("read failed")))
                with pytest.raises(RuntimeError, match="read failed"):
                    manager.refresh()
        return result

    def release(lock, token):
        if cache.get(lock.name) == token:
            cache.delete(lock.name)

    monkeypatch.setattr(Lock, "owned", takeover_after_check)
    monkeypatch.setattr(Lock, "do_release", release)
    with pytest.raises(LockNotOwnedError):
        manager.refresh()
    assert cache.get("config") == b"published"
    assert int(cache.get(manager.LAST_REFRESH_KEY)) == 123
