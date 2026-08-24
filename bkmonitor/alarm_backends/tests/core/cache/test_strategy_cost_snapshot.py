"""Redis 策略成本快照核心逻辑测试。"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import mock

from alarm_backends.core.cache.strategy_cost_snapshot import (
    SNAPSHOT_HISTORY_LIMIT,
    RedisStrategyCostSnapshotCollector,
    StrategyCostSnapshotStore,
    build_strategy_cost_profile,
)


def _node(node_id=1):
    return SimpleNamespace(id=node_id)


def test_store_success_keeps_latest_six_and_refreshes_ttl():
    client = mock.Mock()
    pipeline = client.pipeline.return_value
    store = StrategyCostSnapshotStore(_node(), client=client)
    snapshot = {"schema_version": 1, "finished_at": "2026-08-24T10:00:00+00:00"}

    store.save(snapshot)

    saved_value = pipeline.lpush.call_args.args[1]
    saved_snapshot = json.loads(saved_value)
    assert saved_snapshot["snapshot_payload_bytes"] == len(saved_value.encode())
    pipeline.ltrim.assert_called_once_with(store.snapshot_key, 0, SNAPSHOT_HISTORY_LIMIT - 1)
    pipeline.expire.assert_called_once_with(store.snapshot_key, store.SNAPSHOT_TTL_SECONDS)
    pipeline.execute.assert_called_once_with()


def test_store_reads_latest_or_bounded_history_newest_first():
    client = mock.Mock()
    client.lrange.return_value = [
        json.dumps({"snapshot_id": "new"}),
        json.dumps({"snapshot_id": "old"}),
    ]
    store = StrategyCostSnapshotStore(_node(), client=client)

    snapshots = store.read(limit=2)

    assert snapshots == [{"snapshot_id": "new"}, {"snapshot_id": "old"}]
    client.lrange.assert_called_once_with(store.snapshot_key, 0, 1)


def test_store_lock_is_node_local_and_rechecked_by_caller():
    client = mock.Mock()
    client.set.return_value = True
    store = StrategyCostSnapshotStore(_node(7), client=client)

    assert store.try_lock("token") is True
    client.set.assert_called_once_with(store.lock_key, "token", nx=True, ex=store.LOCK_TTL_SECONDS)


def test_build_profile_reuses_production_retention_and_interval(mocker):
    point_required = mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.detect_result_point_required", return_value=30
    )
    control_strategy = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.ControlStrategy")
    control_strategy.return_value.get_interval.return_value = 60
    config = {"id": 11}

    profile = build_strategy_cost_profile(config)

    assert profile == {
        "point_required": 30,
        "interval_seconds": 60,
        "clean_interval_seconds": 7200,
        "growth_per_clean_cycle": 120,
        "peak_members_per_series": 150,
    }
    point_required.assert_called_once_with(config)
    control_strategy.assert_called_once_with(11, default_config=config)


def test_collector_fresh_snapshot_skips_lock_and_population_read(mocker):
    node = _node()
    client = mock.Mock()
    client.lrange.return_value = [json.dumps({"finished_at": datetime.now(UTC).isoformat()})]
    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    collector = RedisStrategyCostSnapshotCollector(client_factory=lambda _node: client)

    result = collector.collect([(node, {})])

    assert result["skipped_fresh"] == 1
    client.set.assert_not_called()
    strategy_manager.get_strategy_ids.assert_not_called()


def test_collector_rechecks_freshness_after_node_local_lock(mocker):
    node = _node()
    client = mock.Mock()
    client.lrange.side_effect = [[], [json.dumps({"finished_at": datetime.now(UTC).isoformat()})]]
    client.set.return_value = True
    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    collector = RedisStrategyCostSnapshotCollector(client_factory=lambda _node: client)

    result = collector.collect([(node, {})])

    assert result["skipped_fresh"] == 1
    client.set.assert_called_once()
    strategy_manager.get_strategy_ids.assert_not_called()


def test_collector_loads_population_once_and_uses_each_strategy_target_node(mocker):
    node_1 = _node(1)
    node_2 = _node(2)
    clients = {1: mock.Mock(), 2: mock.Mock()}
    for client in clients.values():
        client.lrange.return_value = []
        client.set.return_value = True
    clients[1].hlen.return_value = 10
    clients[2].hlen.return_value = 20

    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    strategy_manager.get_strategy_ids.return_value = [1, 2]
    strategy_manager.get_all_groups.return_value = {"group": json.dumps({"bk_biz_id": 7, "1": [101], "2": [202]})}
    strategy_manager.get_strategy_by_ids.return_value = [{"id": 1}, {"id": 2}]
    mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.build_strategy_cost_profile",
        return_value={
            "point_required": 30,
            "interval_seconds": 60,
            "clean_interval_seconds": 7200,
            "growth_per_clean_cycle": 120,
            "peak_members_per_series": 150,
        },
    )
    load_routes = mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.load_positive_routes",
        return_value=[{"strategy_score": 2, "node_id": 1}, {"strategy_score": 3, "node_id": 2}],
    )
    collector = RedisStrategyCostSnapshotCollector(client_factory=lambda node: clients[node.id])

    result = collector.collect([(node_1, {}), (node_2, {})])

    assert result["succeeded"] == 2
    strategy_manager.get_strategy_ids.assert_called_once_with()
    strategy_manager.get_all_groups.assert_called_once_with()
    strategy_manager.get_strategy_by_ids.assert_called_once_with([1, 2])
    load_routes.assert_called_once_with()
    clients[1].hlen.assert_called_once()
    clients[2].hlen.assert_called_once()
    assert ".1.101" in str(clients[1].hlen.call_args.args[0])
    assert ".2.202" in str(clients[2].hlen.call_args.args[0])


def test_collector_preserves_measured_no_group_config_missing_and_failed_coverage(mocker):
    node = _node()
    client = mock.Mock()
    client.lrange.return_value = []
    client.set.return_value = True

    def hlen(key):
        if ".4.404" in str(key):
            raise RuntimeError("redis unavailable")
        return {"1": 10, "3": 30}.get(str(key).split(".")[-2], 0)

    client.hlen.side_effect = hlen
    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    strategy_manager.get_strategy_ids.return_value = [1, 2, 3, 4]
    strategy_manager.get_all_groups.return_value = {
        "group": json.dumps({"bk_biz_id": 7, "1": [101], "3": [303], "4": [404]})
    }
    strategy_manager.get_strategy_by_ids.return_value = [{"id": 1}, {"id": 4}]
    snapshot_logger = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.logger")
    mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.build_strategy_cost_profile",
        return_value={"peak_members_per_series": 100},
    )
    mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.load_positive_routes",
        return_value=[{"strategy_score": 10, "node_id": 1}],
    )
    collector = RedisStrategyCostSnapshotCollector(client_factory=lambda _node: client)

    collector.collect([(node, {"used_memory": 123, "config_maxmemory": 456})])

    snapshot = json.loads(client.pipeline.return_value.lpush.call_args.args[1])
    assert snapshot["coverage"] == {
        "population_total": 4,
        "route_matched": 4,
        "config_resolved": 2,
        "group_mapped": 3,
        "item_requested": 3,
        "item_measured": 2,
        "item_failed": 1,
        "measured": 1,
        "no_group": 1,
        "config_missing": 1,
        "failed": 1,
    }
    strategies = {item["strategy_id"]: item for item in snapshot["strategies"]}
    assert strategies[1]["status"] == "measured"
    assert strategies[1]["series_upper_bound"] == 10
    assert strategies[1]["estimated_peak_members"] == 1000
    assert strategies[1]["item_measured"] == 1
    assert strategies[1]["item_failed"] == 0
    assert "items" not in strategies[1]
    assert strategies[2]["status"] == "no_group"
    assert strategies[3]["status"] == "config_missing"
    assert strategies[3]["series_upper_bound"] == 30
    assert strategies[4]["status"] == "failed"
    assert strategies[4]["error_code"] == "redis_read_failed"
    assert "error" not in strategies[4]
    assert snapshot["totals"] == {"series_upper_bound": 10, "estimated_peak_members": 1000}
    assert snapshot["node_memory"] == {"used_memory_bytes": 123, "maxmemory_bytes": 456}
    assert snapshot["routing"]["positive_routes"] == [{"strategy_score": 10, "node_id": 1}]
    assert snapshot["routing"]["digest"].startswith("sha256:")
    assert snapshot["commands"] == {
        "db8": {
            "scope": "shared_once_per_selfmonitor_call",
            "population_reads": 1,
            "group_reads": 1,
            "config_mget_batches": 1,
        },
        "db10": {
            "snapshot_precheck_reads": 2,
            "lock_writes": 1,
            "hlen_requested": 3,
            "hlen_measured": 2,
            "hlen_failed": 1,
            "store_commands": 3,
        },
    }
    log_messages = [call.args[0] for call in snapshot_logger.info.call_args_list]
    assert any("snapshot started" in message for message in log_messages)
    assert any("status=success" in message for message in log_messages)


def test_collector_node_failure_is_fail_open_for_later_nodes(mocker):
    failed_node = _node(1)
    healthy_node = _node(2)
    failed_client = mock.Mock()
    failed_client.lrange.side_effect = RuntimeError("node down")
    healthy_client = mock.Mock()
    healthy_client.lrange.return_value = []
    healthy_client.set.return_value = True
    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    strategy_manager.get_strategy_ids.return_value = []
    strategy_manager.get_all_groups.return_value = {}
    strategy_manager.get_strategy_by_ids.return_value = []
    mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.load_positive_routes", return_value=[])
    collector = RedisStrategyCostSnapshotCollector(
        client_factory=lambda node: failed_client if node.id == 1 else healthy_client
    )

    result = collector.collect([(failed_node, {}), (healthy_node, {})])

    assert result["failed"] == 1
    assert result["succeeded"] == 1
    healthy_client.pipeline.return_value.execute.assert_called_once_with()


def test_collector_budget_expiry_during_hlen_does_not_write_partial_snapshot(mocker):
    node = _node()
    clock = [0.0]
    client = mock.Mock()
    client.lrange.return_value = []
    client.set.return_value = True

    def hlen(_key):
        clock[0] = 21.0
        return 10

    client.hlen.side_effect = hlen
    strategy_manager = mocker.patch("alarm_backends.core.cache.strategy_cost_snapshot.StrategyCacheManager")
    strategy_manager.get_strategy_ids.return_value = [1]
    strategy_manager.get_all_groups.return_value = {"group": json.dumps({"bk_biz_id": 7, "1": [101]})}
    strategy_manager.get_strategy_by_ids.return_value = [{"id": 1}]
    mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.load_positive_routes",
        return_value=[{"strategy_score": 2, "node_id": 1}],
    )
    mocker.patch(
        "alarm_backends.core.cache.strategy_cost_snapshot.build_strategy_cost_profile",
        return_value={"peak_members_per_series": 100},
    )
    collector = RedisStrategyCostSnapshotCollector(
        client_factory=lambda _node: client,
        total_budget_seconds=20,
        monotonic_fn=lambda: clock[0],
    )

    result = collector.collect([(node, {})])

    assert result["budget_exhausted"] is True
    assert result["succeeded"] == 0
    client.pipeline.assert_not_called()
