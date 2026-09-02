"""
策略增量刷新前同步近期变更套餐的回归测试。
"""

from unittest import mock

import pytest

from alarm_backends.core.cache import strategy as strategy_module
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.strategy import StrategyCacheManager


def test_smart_refresh_updates_recent_action_configs_before_strategies(monkeypatch):
    calls = []

    monkeypatch.setattr(
        ActionConfigCacheManager,
        "refresh",
        lambda minutes=None: calls.append(("action_config", minutes)),
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
