from types import SimpleNamespace

import fakeredis
import pytest
import redis

from alarm_backends.core.control.checkpoint import Checkpoint
from alarm_backends.core.control.item import Item
from alarm_backends.service.access.data.duplicate import Duplicate
from alarm_backends.service.access.data.processor import AccessDataProcess
from constants.data_source import DataSourceLabel, DataTypeLabel


def make_process(override, updated_at=0):
    process = AccessDataProcess("query-group")
    process.items = [
        SimpleNamespace(
            query_configs=[{"agg_interval": 60}],
            item_config={"update_time": updated_at},
            access_lookback_periods=override,
            time_delay=0,
            data_source_labels={DataSourceLabel.BK_LOG_SEARCH},
            data_source_types={(DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG)},
        )
    ]
    return process


@pytest.mark.parametrize("override,default,expected", [(None, 1, 1), (None, 3, 3), (1, 3, 1), (15, 1, 15)])
def test_window_uses_override_without_changing_until(mocker, settings, override, default, expected):
    settings.NUM_OF_COUNT_FREQ_ACCESS = default
    settings.ACCESS_DATA_TIME_DELAY = 10
    checkpoint = mocker.patch.object(Checkpoint, "get", return_value=3605)
    process = make_process(override, updated_at=3000)
    process.get_query_time_range(3730)
    assert process.from_timestamp == 3600 - expected * 60
    assert process.until_timestamp == 3660
    checkpoint.assert_called_once_with(3000, interval=60)


def test_fresh_group_and_return_to_existing_group_follow_existing_checkpoint_rules(mocker, settings):
    settings.MIN_DATA_ACCESS_CHECKPOINT = 1800
    settings.ACCESS_DATA_TIME_DELAY = 10
    mocker.patch("alarm_backends.core.control.checkpoint.time.time", return_value=7200)
    checkpoint_client = mocker.Mock()
    mocker.patch.object(Checkpoint, "_key", "checkpoint")
    mocker.patch("alarm_backends.core.control.checkpoint.key.STRATEGY_CHECKPOINT_KEY", client=checkpoint_client)
    process = make_process(15, updated_at=7200)
    checkpoint_client.get.return_value = None
    process.get_query_time_range(7200)
    assert process.from_timestamp == 6300
    checkpoint_client.get.return_value = "6960"
    process.get_query_time_range(7200)
    assert process.from_timestamp == 6060
    checkpoint_client.set.assert_not_called()


@pytest.mark.parametrize("override", [None, 15])
def test_runtime_item_receives_override(mocker, override):
    mocker.patch("alarm_backends.core.control.item.UnifyQuery")
    config = {"id": 1, "query_configs": [], "algorithms": [], "expression": "a"}
    if override is not None:
        config["access_lookback_periods"] = override
    strategy = SimpleNamespace(id=1, bk_biz_id=2, bk_tenant_id="system", config={})
    item = Item(config, strategy)
    assert item.access_lookback_periods == override


def test_wide_window_keeps_old_buckets_deduplicated_and_accepts_late_series():
    # conftest 替换 redis.Redis 后 fakeredis 无法从其签名读取 decode_responses，直接指定连接池。
    client = redis.StrictRedis(
        connection_pool=redis.ConnectionPool(
            connection_class=fakeredis.FakeConnection, server=fakeredis.FakeServer(), decode_responses=True
        )
    )
    # 连续 16 轮回看同一个旧桶，每轮模拟 TTL 接近到期。
    for cycle in range(16):
        duplicate = Duplicate("wide-lookback", ttl=600)
        duplicate.client = client
        assert duplicate.is_duplicate_by_id("known.3600", 3600) is (cycle > 0)
        if cycle == 0:
            duplicate.add_record_by_id("known.3600", 3600)
        if cycle == 14:
            assert not duplicate.is_duplicate_by_id("late.3600", 3600)
            duplicate.add_record_by_id("late.3600", 3600)
        if cycle == 15:
            assert duplicate.is_duplicate_by_id("late.3600", 3600)
        duplicate.refresh_cache()
        for cache_key in duplicate.record_ids_cache:
            assert "known.3600" in client.smembers(cache_key)
            assert client.ttl(cache_key) == 600
            # 模拟接近到期，下一轮必须重新续期。
            client.expire(cache_key, 1)
