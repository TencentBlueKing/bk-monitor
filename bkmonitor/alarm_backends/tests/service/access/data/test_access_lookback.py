import copy
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


LOG_COUNT_QUERY = {
    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
    "data_type_label": DataTypeLabel.LOG,
    "alias": "a",
    "index_set_id": 1,
    "result_table_id": "1",
    "query_string": "error",
    "agg_interval": 60,
    "agg_dimension": [],
    "agg_condition": [],
    "time_field": "dtEventTimeStamp",
}
COLLECTOR_LOG_COUNT_QUERY = {
    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    "data_type_label": DataTypeLabel.LOG,
    "alias": "a",
    "result_table_id": "2_bkmonitor_event_1",
    "metric_field": "event.count",
    "agg_method": "COUNT",
    "agg_interval": 60,
    "agg_dimension": [],
    "agg_condition": [],
}
TIME_SERIES_COUNT_QUERY = {
    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
    "data_type_label": DataTypeLabel.TIME_SERIES,
    "alias": "a",
    "result_table_id": "system.cpu_summary",
    "metric_field": "usage",
    "agg_method": "COUNT",
    "agg_interval": 60,
    "agg_dimension": [],
    "agg_condition": [],
}
GTE_0 = [[{"method": "gte", "threshold": 0}]]
GTE_1 = [[{"method": "gte", "threshold": 1}]]
GTE_5 = [[{"method": "gte", "threshold": 5}]]
GTE_10 = [[{"method": "gte", "threshold": 10}]]
LT_1 = [[{"method": "lt", "threshold": 1}]]
# 重复读到的 0 不再送检，迟到日志使计数变为非零后仍会被检测
LATE = ([0, 0, 1, 1], [1, 0, 1, 0])
DEDUPED = ([0, 1, 1], [1, 0, 0])
# 日志计数按取值去重：同一取值不重复送检，不同取值都会送检
CROSSED = ([0, 2, 7, 7], [1, 1, 1, 0])
VALUE_CHANGE = ([0, 1, 1], [1, 1, 0])
LOG_TS_COUNT_QUERY = {
    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
    "data_type_label": DataTypeLabel.TIME_SERIES,
    "alias": "a",
    "index_set_id": 1,
    "result_table_id": "",
    "metric_field": "_index",
    "agg_method": "COUNT",
    "agg_interval": 60,
    "agg_dimension": [],
    "agg_condition": [],
}


@pytest.mark.parametrize(
    "query_config,item_thresholds,connector,reads",
    [
        (LOG_COUNT_QUERY, [[GTE_1]], "and", LATE),
        # 同一取值不重复送检；计数继续增大（例如再跨过更高阈值）仍会送检
        (LOG_COUNT_QUERY, [[GTE_5]], "and", CROSSED),
        (LOG_TS_COUNT_QUERY, [[GTE_10]], "and", ([1, 11, 150, 150], [1, 1, 1, 0])),
        # 0 与 1 是不同取值，后一个不再被前一个挡住
        (LOG_COUNT_QUERY, [[LT_1]], "and", VALUE_CHANGE),
        (LOG_COUNT_QUERY, [[GTE_1], [LT_1]], "and", VALUE_CHANGE),
        # 同级别多个算法按连接符组合后判断是否异常
        (LOG_COUNT_QUERY, [[GTE_0, GTE_1]], "and", LATE),
        (LOG_COUNT_QUERY, [[GTE_0, GTE_1]], "or", VALUE_CHANGE),
        (COLLECTOR_LOG_COUNT_QUERY, [[GTE_1]], "and", LATE),
        ({**COLLECTOR_LOG_COUNT_QUERY, "agg_method": "AVG"}, [[GTE_1]], "and", DEDUPED),
        (TIME_SERIES_COUNT_QUERY, [[GTE_1]], "and", DEDUPED),
    ],
)
def test_log_count_zero_point_stays_retryable_within_lookback(mocker, query_config, item_thresholds, connector, reads):
    client = redis.StrictRedis(
        connection_pool=redis.ConnectionPool(
            connection_class=fakeredis.FakeConnection, server=fakeredis.FakeServer(), decode_responses=True
        )
    )

    def new_duplicate(*args, **kwargs):
        duplicate = Duplicate(*args, **kwargs)
        duplicate.client = client
        return duplicate

    mocker.patch("alarm_backends.service.access.data.processor.Duplicate", side_effect=new_duplicate)
    strategy = SimpleNamespace(
        id=1,
        bk_biz_id=2,
        bk_tenant_id="system",
        config={"detects": [{"level": 2, "connector": connector}]},
        priority=None,
        priority_group_key=None,
        scenario="os",
    )
    items = [
        Item(
            {
                "id": item_id,
                "name": "COUNT",
                "expression": "a",
                "query_configs": [copy.deepcopy(query_config)],
                "algorithms": [
                    {"type": "Threshold", "level": 2, "config": threshold, "unit_prefix": ""}
                    for threshold in thresholds
                ],
            },
            strategy,
        )
        for item_id, thresholds in enumerate(item_thresholds, start=1)
    ]

    def pull(value):
        process = AccessDataProcess("log-count-group")
        process.items = items
        process.from_timestamp = process.until_timestamp = 0
        process.filter_duplicates([{"_time_": 3600, "_result_": value}])
        process.dup_obj.refresh_cache()
        return len(process.record_list)

    # 同一时间点在回看窗口内依次读到的计数，及每轮进入检测的点数
    values, detected = reads
    assert [pull(value) for value in values] == detected


def test_log_count_threshold_cross_replaces_same_timestamp(mocker):
    client = redis.StrictRedis(
        connection_pool=redis.ConnectionPool(
            connection_class=fakeredis.FakeConnection, server=fakeredis.FakeServer(), decode_responses=True
        )
    )

    def new_duplicate(*args, **kwargs):
        duplicate = Duplicate(*args, **kwargs)
        duplicate.client = client
        return duplicate

    mocker.patch("alarm_backends.service.access.data.processor.Duplicate", side_effect=new_duplicate)
    strategy = SimpleNamespace(
        id=1,
        bk_biz_id=2,
        bk_tenant_id="system",
        config={"detects": [{"level": 2, "connector": "and"}]},
        priority=None,
        priority_group_key=None,
        scenario="os",
    )
    item = Item(
        {
            "id": 1,
            "name": "COUNT",
            "expression": "a",
            "query_configs": [copy.deepcopy(LOG_TS_COUNT_QUERY)],
            "algorithms": [{"type": "Threshold", "level": 2, "config": GTE_10, "unit_prefix": ""}],
        },
        strategy,
    )

    def pull(value):
        process = AccessDataProcess("log-count-group")
        process.items = [item]
        process.from_timestamp = process.until_timestamp = 0
        process.filter_duplicates([{"_time_": 3600, "_result_": value}])
        process.dup_obj.refresh_cache()
        return process.record_list

    below = pull(1)
    assert len(below) == 1
    assert getattr(below[0], "replaces_check_result", False) is False

    crossed = pull(11)
    assert len(crossed) == 1
    assert crossed[0].replaces_check_result is True
    assert crossed[0].clean().data["replaces_check_result"] is True

    higher = pull(150)
    assert len(higher) == 1
    assert higher[0].replaces_check_result is True
    assert pull(150) == []


def test_partial_log_count_does_not_overwrite_a_complete_value(mocker):
    client = redis.StrictRedis(
        connection_pool=redis.ConnectionPool(
            connection_class=fakeredis.FakeConnection, server=fakeredis.FakeServer(), decode_responses=True
        )
    )

    def new_duplicate(*args, **kwargs):
        duplicate = Duplicate(*args, **kwargs)
        duplicate.client = client
        return duplicate

    mocker.patch("alarm_backends.service.access.data.processor.Duplicate", side_effect=new_duplicate)
    strategy = SimpleNamespace(
        id=1,
        bk_biz_id=2,
        bk_tenant_id="system",
        config={"detects": [{"level": 2, "connector": "and"}]},
        priority=None,
        priority_group_key=None,
        scenario="os",
    )
    item = Item(
        {
            "id": 1,
            "name": "COUNT",
            "expression": "a",
            "query_configs": [copy.deepcopy(LOG_TS_COUNT_QUERY)],
            "algorithms": [{"type": "Threshold", "level": 2, "config": GTE_10, "unit_prefix": ""}],
        },
        strategy,
    )

    def pull(value, partial=False):
        item.query.is_partial = partial
        process = AccessDataProcess("log-count-group")
        process.items = [item]
        process.from_timestamp = process.until_timestamp = 0
        process.filter_duplicates([{"_time_": 3600, "_result_": value}])
        process.dup_obj.refresh_cache()
        return process.record_list

    assert len(pull(11)) == 1
    assert pull(1, partial=True) == []
    assert pull(11) == []


def test_same_batch_uses_the_latest_value_for_the_check_result():
    from alarm_backends.core.control.mixins.detect import select_check_result_records

    earlier = SimpleNamespace(record_id="md5.3600", value=0, timestamp=3600)
    latest = SimpleNamespace(record_id="md5.3600", value=1, timestamp=3600)
    anomaly = SimpleNamespace(data_point=earlier)

    last_by_record_id, anomaly_record_ids = select_check_result_records([earlier, latest], [anomaly])

    assert last_by_record_id["md5.3600"] is latest
    assert anomaly_record_ids == set()
