"""bkm-cli Redis 策略成本快照只读操作。"""

from __future__ import annotations

from typing import Any

from alarm_backends.core.cache.strategy_cost_snapshot import (
    SNAPSHOT_HISTORY_LIMIT,
    StrategyCostSnapshotStore,
    serialize_cache_node,
)
from alarm_backends.core.cluster import get_cluster
from bkmonitor.models import CacheNode
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

OPERATION_LATEST = "latest"
OPERATION_HISTORY = "history"
ALLOWED_FIELDS = {"operation", "node_id", "limit"}


def _history_limit(params: dict[str, Any], operation: str) -> int:
    if operation == OPERATION_LATEST:
        return 1
    value = params.get("limit", SNAPSHOT_HISTORY_LIMIT)
    try:
        limit = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="limit must be an integer") from error
    if limit < 1 or limit > SNAPSHOT_HISTORY_LIMIT:
        raise CustomException(message=f"limit must be between 1 and {SNAPSHOT_HISTORY_LIMIT}")
    return limit


def _node_id(params: dict[str, Any]) -> int | None:
    value = params.get("node_id")
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise CustomException(message="node_id must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="node_id must be an integer") from error


def read_redis_strategy_cost_snapshots(params: dict[str, Any]) -> dict[str, Any]:
    unknown_fields = set(params) - ALLOWED_FIELDS
    if unknown_fields:
        raise CustomException(message=f"unsupported params: {', '.join(sorted(unknown_fields))}")
    operation = str(params.get("operation") or OPERATION_LATEST).strip()
    if operation not in {OPERATION_LATEST, OPERATION_HISTORY}:
        raise CustomException(message=f"unsupported operation: {operation}")
    requested_node_id = _node_id(params)
    if operation == OPERATION_HISTORY and requested_node_id is None:
        raise CustomException(message="node_id is required for history")
    if operation == OPERATION_LATEST and "limit" in params:
        raise CustomException(message="limit is only supported for history")
    limit = _history_limit(params, operation)
    cluster_name = get_cluster().name
    nodes = list(CacheNode.objects.filter(cluster_name=cluster_name, is_enable=True).order_by("id"))
    if requested_node_id is not None:
        nodes = [node for node in nodes if node.id == requested_node_id]
        if not nodes:
            raise CustomException(message=f"enabled CacheNode not found in current cluster: {requested_node_id}")

    results = []
    for node in nodes:
        entry = {"node": serialize_cache_node(node), "snapshot_count": 0, "snapshots": []}
        try:
            snapshots = StrategyCostSnapshotStore(node).read(limit)
        except Exception:
            entry["error"] = "snapshot_read_failed"
        else:
            entry["snapshot_count"] = len(snapshots)
            entry["snapshots"] = snapshots
        results.append(entry)
    return {"operation": operation, "cluster_name": cluster_name, "limit": limit, "nodes": results}


_PARAMS_SCHEMA = {
    "operation": "latest | history, default latest",
    "node_id": "optional enabled CacheNode id in the current cluster",
    "limit": f"history only, 1..{SNAPSHOT_HISTORY_LIMIT}, default {SNAPSHOT_HISTORY_LIMIT}",
}

KernelRPCRegistry.register_function(
    func_name="bkm_cli.read_redis_strategy_cost_snapshots",
    summary="读取 Redis 节点策略成本快照",
    description="读取当前集群启用 Redis 节点最近或历史策略成本快照，不触发新的成本扫描。",
    handler=read_redis_strategy_cost_snapshots,
    params_schema=_PARAMS_SCHEMA,
    example_params={"operation": "latest"},
)

BkmCliOpRegistry.register(
    op_id="read-redis-strategy-cost-snapshots",
    func_name="bkm_cli.read_redis_strategy_cost_snapshots",
    summary="读取 Redis 节点策略成本快照",
    description="只读返回节点本地已生成的最新或最近六份策略成本快照，不执行线上扫描。",
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["cache", "redis", "readonly", "strategy-cost"],
    params_schema=_PARAMS_SCHEMA,
    example_params={"operation": "latest"},
)
