"""bkm-cli Redis 策略成本快照只读操作测试。"""

from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot import read_redis_strategy_cost_snapshots


def _node(node_id: int):
    return SimpleNamespace(
        id=node_id,
        node_alias=f"node-{node_id}",
        cluster_name="default",
        cache_type="RedisCache",
        is_default=node_id == 1,
        is_enable=True,
    )


def _patch_nodes(mocker, nodes):
    queryset = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.CacheNode.objects.filter"
    ).return_value
    queryset.order_by.return_value = nodes
    mocker.patch("kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.get_cluster").return_value.name = "default"
    return queryset


def test_latest_returns_one_snapshot_per_enabled_node_with_safe_identity(mocker):
    nodes = [_node(1), _node(2)]
    queryset = _patch_nodes(mocker, nodes)
    reader = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots",
        side_effect=lambda node, limit, remaining_seconds: [{"snapshot_id": f"s{node.id}"}],
    )

    result = read_redis_strategy_cost_snapshots({"operation": "latest"})

    assert result == {
        "operation": "latest",
        "cluster_name": "default",
        "limit": 1,
        "nodes": [
            {
                "node": {
                    "id": 1,
                    "node_alias": "node-1",
                    "cluster_name": "default",
                    "cache_type": "RedisCache",
                    "is_default": True,
                    "is_enable": True,
                },
                "snapshot_count": 1,
                "snapshots": [{"snapshot_id": "s1"}],
            },
            {
                "node": {
                    "id": 2,
                    "node_alias": "node-2",
                    "cluster_name": "default",
                    "cache_type": "RedisCache",
                    "is_default": False,
                    "is_enable": True,
                },
                "snapshot_count": 1,
                "snapshots": [{"snapshot_id": "s2"}],
            },
        ],
    }
    queryset.order_by.assert_called_once_with("id")
    assert reader.call_count == 2


def test_latest_node_failures_are_isolated(mocker):
    nodes = [_node(1), _node(2)]
    _patch_nodes(mocker, nodes)
    reader = mocker.patch("kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots")

    def read_node(node, limit, remaining_seconds):
        if node.id == 2:
            raise RuntimeError("redis unavailable")
        return [{"snapshot_id": "s1"}]

    reader.side_effect = read_node

    result = read_redis_strategy_cost_snapshots({"operation": "latest"})

    assert result["limit"] == 1
    assert result["nodes"][0]["snapshot_count"] == 1
    assert result["nodes"][1]["snapshot_count"] == 0
    assert result["nodes"][1]["snapshots"] == []
    assert result["nodes"][1]["error"] == "snapshot_read_failed"
    assert reader.call_count == 2


def test_latest_uses_bounded_isolated_clients_and_closes_them(mocker):
    node = _node(1)
    _patch_nodes(mocker, [node])
    source_client = object()
    isolated_client = mocker.MagicMock()
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.REDIS_STRATEGY_COST_SNAPSHOT_KEY.client.get_client",
        return_value=source_client,
    )
    isolated = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.IsolatedSnapshotRedisClient",
        return_value=isolated_client,
    )
    store = mocker.patch("kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.StrategyCostSnapshotStore")
    store.return_value.read.return_value = [{"snapshot_id": "s1"}]

    result = read_redis_strategy_cost_snapshots({"operation": "latest"})

    assert result["nodes"][0]["snapshots"] == [{"snapshot_id": "s1"}]
    isolated.assert_called_once_with(source_client, 1.0)
    store.assert_called_once_with(node, client=isolated_client)
    isolated_client.close.assert_called_once_with()


def test_latest_stops_reading_after_total_budget_is_exhausted(mocker):
    nodes = [_node(1), _node(2)]
    _patch_nodes(mocker, nodes)
    reader = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots",
        return_value=[{"snapshot_id": "s1"}],
    )
    mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot.monotonic",
        side_effect=[0.0, 0.1, 3.1],
    )

    result = read_redis_strategy_cost_snapshots({"operation": "latest"})

    assert result["nodes"][0]["snapshot_count"] == 1
    assert result["nodes"][1]["error"] == "snapshot_read_budget_exhausted"
    reader.assert_called_once_with(nodes[0], 1, 2.9)


def test_history_requires_node_and_defaults_to_six(mocker):
    node = _node(2)
    _patch_nodes(mocker, [_node(1), node])
    reader = mocker.patch(
        "kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots",
        return_value=[{"snapshot_id": "s2", "finished_at": "2026-08-24T10:00:00+00:00"}],
    )

    result = read_redis_strategy_cost_snapshots({"operation": "history", "node_id": 2})

    assert result["limit"] == 6
    assert [entry["node"]["id"] for entry in result["nodes"]] == [2]
    reader.assert_called_once_with(node, 6, mocker.ANY)


def test_latest_can_filter_one_node(mocker):
    node = _node(2)
    _patch_nodes(mocker, [_node(1), node])
    reader = mocker.patch("kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots", return_value=[])

    result = read_redis_strategy_cost_snapshots({"operation": "latest", "node_id": 2})

    assert [entry["node"]["id"] for entry in result["nodes"]] == [2]
    reader.assert_called_once_with(node, 1, mocker.ANY)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"operation": None},
        {"operation": True},
        {"operation": []},
        {"operation": " latest "},
        {"operation": "unknown"},
        {"operation": "history"},
        {"operation": "latest", "limit": 1},
        {"operation": "latest", "node_id": None},
        {"operation": "latest", "node_id": True},
        {"operation": "latest", "node_id": 1.0},
        {"operation": "latest", "node_id": "1"},
        {"operation": "history", "node_id": True},
        {"operation": "history", "node_id": 1.0},
        {"operation": "history", "node_id": "1"},
        {"operation": "history", "node_id": 1, "limit": None},
        {"operation": "history", "node_id": 1, "limit": True},
        {"operation": "history", "node_id": 1, "limit": 1.0},
        {"operation": "history", "node_id": 1, "limit": "1"},
        {"operation": "history", "node_id": 1, "limit": 0},
        {"operation": "history", "node_id": 1, "limit": 7},
        {"operation": "latest", "refresh": True},
        {"operation": "latest", "scan": True},
        {"operation": "latest", "force": True},
        {"operation": "latest", "unexpected": 1},
    ],
)
def test_invalid_operation_or_limit_is_rejected(params):
    with pytest.raises(CustomException):
        read_redis_strategy_cost_snapshots(params)


@pytest.mark.parametrize("limit", range(1, 7))
def test_history_accepts_each_bounded_limit(mocker, limit):
    node = _node(1)
    _patch_nodes(mocker, [node])
    reader = mocker.patch("kernel_api.rpc.functions.bkm_cli.cache_cost_snapshot._read_node_snapshots", return_value=[])

    result = read_redis_strategy_cost_snapshots({"operation": "history", "node_id": 1, "limit": limit})

    assert result["limit"] == limit
    reader.assert_called_once_with(node, limit, mocker.ANY)


def test_unknown_node_id_is_rejected(mocker):
    _patch_nodes(mocker, [_node(1)])

    with pytest.raises(CustomException):
        read_redis_strategy_cost_snapshots({"operation": "latest", "node_id": 99})


def test_operation_is_registered_readonly_without_confirmation():
    op = BkmCliOpRegistry.resolve("read-redis-strategy-cost-snapshots")

    assert op.func_name == "bkm_cli.read_redis_strategy_cost_snapshots"
    assert op.capability_level == "readonly"
    assert op.risk_level == "low"
    assert op.requires_confirmation is False
