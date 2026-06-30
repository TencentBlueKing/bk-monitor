"""
处理套餐缓存未传播兜底相关单测:

覆盖"新建/克隆策略秒级出告警, 套餐尚未刷入 action_config 缓存"被误判为已删除/停用的场景,
验证读路径按策略变更时效门控的 DB 兜底 + 写回 + 负缓存防穿透, 以及无效文案的区分。
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor

pytestmark = pytest.mark.django_db(databases="__all__")


class _StubProcessor:
    """最小替身, 仅承载 resolve_missing_action_config 依赖的属性。"""

    def __init__(self, strategy, strategy_id=1):
        self.strategy = strategy
        self.strategy_id = strategy_id


def _resolve(strategy, config_id=100):
    stub = _StubProcessor(strategy)
    return CreateActionProcessor.resolve_missing_action_config(stub, config_id)


def _recent_ts():
    return int(time.time()) - 10


def _old_ts():
    return int(time.time()) - 100000


class _FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, timeout=None):
        self.store[key] = value


# ---------------- resolve_missing_action_config 门控 ----------------


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=False)
def test_resolve_disabled_skips_db():
    with patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db:
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_old_strategy_skips_db_no_penetration():
    # 稳定老策略缓存缺失 = 真删, 不回查 DB(防穿透), 也不写负缓存
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db,
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _old_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()
    m_neg.assert_not_called()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_recent_strategy_db_hit_writes_back():
    db_cfg = {"id": 100, "is_enabled": True, "plugin_id": "1", "name": "x"}
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", return_value=db_cfg) as m_db,
        patch.object(ActionConfigCacheManager, "set_action_config_cache") as m_set,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == db_cfg
    assert pending is False
    m_db.assert_called_once()
    m_set.assert_called_once()


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True, ACTION_CONFIG_NEGATIVE_CACHE_TTL=60)
def test_resolve_recent_strategy_db_miss_negative_cache():
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", return_value={}) as m_db,
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is False
    m_db.assert_called_once()
    m_neg.assert_called_once()
    assert m_neg.call_args[0][1] == 60  # ttl 透传


@override_settings(ACTION_CONFIG_CACHE_DB_FALLBACK_ENABLED=True)
def test_resolve_recent_strategy_db_error_marks_pending():
    with (
        patch.object(ActionConfigCacheManager, "get_action_config_from_db", side_effect=RuntimeError("boom")),
        patch.object(ActionConfigCacheManager, "set_negative_cache") as m_neg,
    ):
        cfg, pending = _resolve({"update_time": _recent_ts()})
    assert cfg == {}
    assert pending is True  # 异常无法确认, 标记疑似尚未生效
    m_neg.assert_not_called()


def test_resolve_without_update_time_skips_db():
    with patch.object(ActionConfigCacheManager, "get_action_config_from_db") as m_db:
        cfg, pending = _resolve({})
    assert cfg == {}
    assert pending is False
    m_db.assert_not_called()


# ---------------- is_action_config_valid 文案分支 ----------------


def _run_valid(action_config, config_id, suspected_pending):
    alert = MagicMock()
    alert.id = "1"
    with patch("alarm_backends.service.fta_action.tasks.create_action.AlertLog") as m_log:
        ret = CreateActionProcessor.is_action_config_valid(alert, action_config, config_id, suspected_pending)
    return ret, m_log


def test_valid_enabled_config_no_log():
    ret, m_log = _run_valid({"is_enabled": True, "name": "x"}, 100, False)
    assert ret is True
    m_log.bulk_create.assert_not_called()


def test_invalid_deleted_message():
    ret, m_log = _run_valid({}, 100, False)
    assert ret is False
    assert "已经被删除或禁用" in m_log.call_args.kwargs["description"]


def test_invalid_pending_message():
    ret, m_log = _run_valid({}, 100, True)
    assert ret is False
    assert "配置尚未生效" in m_log.call_args.kwargs["description"]


def test_negative_sentinel_is_invalid_with_deleted_message():
    sentinel = {"id": 100, "is_enabled": False, ActionConfigCacheManager.NEGATIVE_CACHE_FLAG: True}
    ret, m_log = _run_valid(sentinel, 100, False)
    assert ret is False
    assert "已经被删除或禁用" in m_log.call_args.kwargs["description"]


# ---------------- 缓存管理方法 ----------------


def test_negative_cache_roundtrip_is_truthy_but_disabled():
    fake = _FakeCache()
    with patch.object(ActionConfigCacheManager, "cache", fake):
        ActionConfigCacheManager.set_negative_cache(100, 60)
        got = ActionConfigCacheManager.get_action_config_by_id(100)
    assert got  # 非空, 故不会再次触发 DB 兜底
    assert got.get("is_enabled") is False
    assert got.get(ActionConfigCacheManager.NEGATIVE_CACHE_FLAG) is True


def test_get_from_db_missing_returns_empty():
    with patch("alarm_backends.core.cache.action_config.ActionConfig") as m_ac:
        m_ac.objects.filter.return_value.first.return_value = None
        assert ActionConfigCacheManager.get_action_config_from_db(100) == {}


def test_get_from_db_found_serializes():
    with (
        patch("alarm_backends.core.cache.action_config.ActionConfig") as m_ac,
        patch("alarm_backends.core.cache.action_config.ActionConfigDetailSlz") as m_slz,
    ):
        m_ac.objects.filter.return_value.first.return_value = object()
        m_slz.return_value.data = {"id": 100, "is_enabled": True}
        out = ActionConfigCacheManager.get_action_config_from_db(100)
    assert out == {"id": 100, "is_enabled": True}
