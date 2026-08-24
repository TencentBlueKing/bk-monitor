"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# Redis 节点管理页面的只读数据聚合。

from __future__ import annotations

import json
import logging
from hashlib import sha256
from math import isfinite
from time import monotonic, time
from typing import Any

from django.conf import settings
from django.db import router as db_router
from django.db.models import Max

from alarm_backends.core.cache.key import REDIS_STRATEGY_COST_SNAPSHOT_KEY
from alarm_backends.core.cache.strategy_cost_snapshot import (
    IsolatedSnapshotRedisClient,
    StrategyCostSnapshotStore,
    serialize_cache_node,
)
from alarm_backends.core.cluster import get_cluster
from bkmonitor.models import CacheNode, CacheRouter, StrategyModel
from core.drf_resource import Resource, resource

MEMBER_COST_LOWER_BYTES = 100
MEMBER_COST_UPPER_BYTES = 150
HOT_STRATEGY_LIMIT = 100
THREE_HOURS_SECONDS = 3 * 60 * 60
CURRENT_POINT_MAX_AGE_SECONDS = 5 * 60
SNAPSHOT_READ_TOTAL_BUDGET_SECONDS = 3.0
SNAPSHOT_READ_NODE_BUDGET_SECONDS = 1.0

logger = logging.getLogger("monitor_web")


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return f"sha256:{sha256(encoded).hexdigest()}"


def _topology_errors(nodes: list[dict[str, Any]], routes: list[dict[str, int]], max_strategy_id: int) -> list[str]:
    errors = []
    node_by_id = {node["id"]: node for node in nodes}
    positive_routes = [route for route in routes if route["strategy_score"] > 0]
    if not positive_routes:
        errors.append("missing_positive_route")
    elif positive_routes[-1]["strategy_score"] <= max_strategy_id:
        errors.append("terminal_route_does_not_cover_current_strategies")
    if len({route["strategy_score"] for route in positive_routes}) != len(positive_routes):
        errors.append("duplicate_positive_route_boundary")
    for route in routes:
        node = node_by_id.get(route["node_id"])
        if node is None:
            errors.append("route_references_unknown_node")
        elif not node["is_enable"]:
            errors.append("route_references_disabled_node")
    return sorted(set(errors))


def build_routing_observation(
    cluster_name: str,
    node_models: list[Any],
    routes: list[dict[str, int]],
    *,
    max_strategy_id: int,
) -> dict[str, Any]:
    nodes = sorted((serialize_cache_node(node) for node in node_models), key=lambda item: item["id"])
    routes = sorted(
        (
            {"strategy_score": int(route["strategy_score"]), "node_id": int(route["node_id"])}
            for route in routes
        ),
        key=lambda item: (item["strategy_score"], item["node_id"]),
    )
    node_by_id = {node["id"]: node for node in nodes}
    positive_routes = [route for route in routes if route["strategy_score"] > 0]
    routers = []
    floor = 1
    for route in positive_routes:
        routers.append(
            {
                "strategy_score": route["strategy_score"],
                "score_range": {"floor": floor, "ceil": route["strategy_score"] - 1},
                "node": node_by_id.get(route["node_id"]),
            }
        )
        floor = route["strategy_score"]
    payload = {
        "cluster_name": cluster_name,
        "nodes": nodes,
        "routes": routes,
        "max_strategy_id": int(max_strategy_id or 0),
    }
    errors = _topology_errors(nodes, routes, payload["max_strategy_id"])
    return {
        "snapshot_id": _canonical_digest(payload),
        "cluster_name": cluster_name,
        "nodes": nodes,
        "routers": routers,
        "max_strategy_id": payload["max_strategy_id"],
        "terminal_score": positive_routes[-1]["strategy_score"] if positive_routes else None,
        "topology_validation": {"valid": not errors, "errors": errors},
    }


def load_routing_observation() -> tuple[dict[str, Any], list[Any]]:
    cluster_name = get_cluster().name
    using = db_router.db_for_read(CacheRouter) or "default"
    node_models = list(CacheNode.objects.using(using).filter(cluster_name=cluster_name).order_by("id"))
    routes = list(
        CacheRouter.objects.using(using)
        .filter(cluster_name=cluster_name)
        .order_by("strategy_score", "node_id")
        .values("strategy_score", "node_id")
    )
    max_strategy_id = StrategyModel.objects.using(using).aggregate(max_id=Max("id"))["max_id"] or 0
    return build_routing_observation(cluster_name, node_models, routes, max_strategy_id=max_strategy_id), node_models


def _last_number(datapoints: list[list[Any]]) -> float | None:
    for value, _timestamp in reversed(datapoints):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
            return float(value)
    return None


def _series_identity(series: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    dimensions = series.get("dimensions") or {}
    return tuple(
        sorted((str(key), str(value)) for key, value in dimensions.items() if key not in {"node", "cluster_name"})
    )


def _timestamp_seconds(value: Any) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
        return None
    timestamp = float(value)
    if timestamp > 100_000_000_000:
        timestamp /= 1000
    return int(timestamp) if timestamp.is_integer() else timestamp


def _merge_datapoints(series_list: list[dict[str, Any]]) -> list[list[Any]]:
    values_by_timestamp: dict[Any, list[float]] = {}
    for series in series_list:
        for value, timestamp in series.get("datapoints") or []:
            timestamp = _timestamp_seconds(timestamp)
            if timestamp is None:
                continue
            values = values_by_timestamp.setdefault(timestamp, [])
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
                values.append(float(value))
    return [
        [max(values) if values else None, timestamp]
        for timestamp, values in sorted(values_by_timestamp.items(), key=lambda item: item[0])
    ]


def _capacity_at(datapoints: list[list[Any]], timestamp: Any) -> float | None:
    result = None
    for value, point_timestamp in datapoints:
        if point_timestamp > timestamp:
            break
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value > 0:
            result = float(value)
    return result


def build_memory_view(
    node_label: str,
    used_series: list[dict],
    capacity_series: list[dict],
    *,
    reference_time: int | None = None,
) -> dict[str, Any]:
    node_used_series = [item for item in used_series if item.get("dimensions", {}).get("node") == node_label]
    node_capacity_series = [item for item in capacity_series if item.get("dimensions", {}).get("node") == node_label]
    trend = _merge_datapoints(node_used_series)
    values = [
        float(value)
        for value, _timestamp in trend
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
    ]
    current = _last_number(trend)
    maximum = max(values) if values else None
    capacity_by_identity: dict[tuple[tuple[str, str], ...], list[list[Any]]] = {}
    for identity in {_series_identity(item) for item in node_capacity_series}:
        capacity_by_identity[identity] = _merge_datapoints(
            [item for item in node_capacity_series if _series_identity(item) == identity]
        )

    usage_values = []
    current_candidates = []
    for series in node_used_series:
        identity = _series_identity(series)
        capacity_points = capacity_by_identity.get(identity, [])
        for value, timestamp in series.get("datapoints") or []:
            timestamp = _timestamp_seconds(timestamp)
            if timestamp is None:
                continue
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not isfinite(value):
                continue
            capacity = _capacity_at(capacity_points, timestamp)
            current_candidates.append((timestamp, float(value), capacity))
            if capacity:
                usage_values.append(float(value) / capacity)

    observed_at = next(
        (
            timestamp
            for value, timestamp in reversed(trend)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
        ),
        None,
    )
    if reference_time is not None and (observed_at is None or observed_at < reference_time - CURRENT_POINT_MAX_AGE_SECONDS):
        current = None
    current_capacity_candidates = [
        capacity
        for timestamp, value, capacity in current_candidates
        if timestamp == observed_at and value == current and capacity
    ]
    current_capacity = min(current_capacity_candidates) if current_capacity_candidates else None
    capacity_value = current_capacity
    if capacity_value is None:
        capacity_points = _merge_datapoints(node_capacity_series)
        capacity_value = _last_number(capacity_points)
    current_ratio = current / current_capacity if current is not None and current_capacity else None
    maximum_ratio = max(usage_values) if usage_values else None
    return {
        "trend": trend,
        "current_bytes": current,
        "max_3h_bytes": maximum,
        "capacity_bytes": capacity_value,
        "current_usage_ratio": current_ratio,
        "max_3h_usage_ratio": maximum_ratio,
        "observed_at": observed_at,
        "missing_points": sum(value is None for value, _timestamp in trend),
    }


def _current_positive_routes(routing_snapshot: dict[str, Any]) -> list[dict[str, int]]:
    return [
        {"strategy_score": int(router["strategy_score"]), "node_id": int(router["node"]["id"])}
        for router in routing_snapshot.get("routers") or []
        if router.get("node")
    ]


def _routing_digest(routing_snapshot: dict[str, Any]) -> str:
    payload = json.dumps(_current_positive_routes(routing_snapshot), sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def _current_owner(routing_snapshot: dict[str, Any], strategy_id: int) -> int | None:
    for router in routing_snapshot.get("routers") or []:
        score_range = router.get("score_range") or {}
        if score_range.get("floor", 1) <= strategy_id <= score_range.get("ceil", -1):
            node = router.get("node") or {}
            return node.get("id")
    return None


def _strategy_cost(row: dict[str, Any]) -> dict[str, Any] | None:
    members = row.get("estimated_peak_members")
    if isinstance(members, bool) or not isinstance(members, (int, float)) or members < 0:
        return None
    lower_bytes = round(members * MEMBER_COST_LOWER_BYTES)
    upper_bytes = round(members * MEMBER_COST_UPPER_BYTES)
    return {
        "strategy_id": int(row["strategy_id"]),
        "bk_biz_id": row.get("bk_biz_id"),
        "series_upper_bound": row.get("series_upper_bound"),
        "estimated_peak_members": members,
        "lower_bytes": lower_bytes,
        "upper_bytes": upper_bytes,
    }


def build_cost_evidence(
    routing_snapshot: dict[str, Any], node_snapshots: dict[int, dict[str, Any] | None]
) -> dict[str, Any]:
    current_digest = _routing_digest(routing_snapshot)
    valid_by_strategy: dict[int, dict[str, Any]] = {}
    coverage_by_strategy: dict[int, str] = {}
    stale_strategy_count = 0
    node_evidence = []
    missing_snapshot_count = 0

    for node in routing_snapshot.get("nodes") or []:
        node_id = int(node["id"])
        snapshot = node_snapshots.get(node_id)
        if not snapshot:
            missing_snapshot_count += 1
            node_evidence.append(
                {
                    "node_id": node_id,
                    "snapshot_time": None,
                    "coverage": None,
                    "routing_matches_current": None,
                }
            )
            continue

        snapshot_time = snapshot.get("finished_at")
        route_matches = snapshot.get("routing", {}).get("digest") == current_digest
        node_evidence.append(
            {
                "node_id": node_id,
                "snapshot_time": snapshot_time,
                "coverage": snapshot.get("coverage"),
                "routing_matches_current": route_matches,
            }
        )
        for row in snapshot.get("strategies") or []:
            try:
                strategy_id = int(row["strategy_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if strategy_id > routing_snapshot.get("max_strategy_id", 0):
                continue
            if _current_owner(routing_snapshot, strategy_id) != node_id:
                stale_strategy_count += 1
                continue
            cost = _strategy_cost(row) if row.get("status") == "measured" else None
            if cost is None:
                coverage_by_strategy[strategy_id] = "unmeasured"
                valid_by_strategy.pop(strategy_id, None)
                continue
            if coverage_by_strategy.get(strategy_id) == "unmeasured":
                continue
            coverage_by_strategy[strategy_id] = "measured"
            cost.update({"snapshot_node_id": node_id, "snapshot_time": snapshot_time})
            previous = valid_by_strategy.get(cost["strategy_id"])
            if previous is None or str(snapshot_time or "") > str(previous.get("snapshot_time") or ""):
                valid_by_strategy[cost["strategy_id"]] = cost

    cumulative_lower = 0
    cumulative_upper = 0
    cumulative_members = 0
    cumulative_measured = 0
    cumulative_unmeasured = 0
    cost_prefix = []
    for strategy_id, status in sorted(coverage_by_strategy.items()):
        cost = valid_by_strategy.get(strategy_id)
        if status == "measured" and cost:
            cumulative_lower += cost["lower_bytes"]
            cumulative_upper += cost["upper_bytes"]
            cumulative_members += cost["estimated_peak_members"]
            cumulative_measured += 1
        else:
            cumulative_unmeasured += 1
        cost_prefix.append(
            {
                "strategy_id": strategy_id,
                "lower_bytes": cumulative_lower,
                "upper_bytes": cumulative_upper,
                "peak_members": cumulative_members,
                "measured_count": cumulative_measured,
                "unmeasured_count": cumulative_unmeasured,
            }
        )

    hot_strategies = sorted(valid_by_strategy.values(), key=lambda item: (-item["upper_bytes"], item["strategy_id"]))[
        :HOT_STRATEGY_LIMIT
    ]
    has_mismatch = any(item["routing_matches_current"] is False for item in node_evidence)
    unmeasured_strategy_count = cumulative_unmeasured
    if not valid_by_strategy:
        status = "unavailable"
    elif missing_snapshot_count or stale_strategy_count or unmeasured_strategy_count or has_mismatch:
        status = "partial"
    else:
        status = "complete"
    return {
        "status": status,
        "valid_strategy_count": len(valid_by_strategy),
        "stale_strategy_count": stale_strategy_count,
        "unmeasured_strategy_count": unmeasured_strategy_count,
        "missing_snapshot_count": missing_snapshot_count,
        "cost_prefix": cost_prefix,
        "hot_strategies": hot_strategies,
        "nodes": node_evidence,
    }


def _query_metric(metric: str, cluster_name: str, start_time: int, end_time: int) -> list[dict[str, Any]]:
    promql = f"custom:custom_report_aggate:{metric}{{job={json.dumps(cluster_name)}}}"
    try:
        result = resource.grafana.graph_promql_query(
            bk_biz_id=settings.DEFAULT_BK_BIZ_ID,
            promql=promql,
            start_time=start_time,
            end_time=end_time,
            step="1m",
        )
    except Exception:
        logger.exception("query Redis management metric failed: metric=%s cluster=%s", metric, cluster_name)
        return []
    return result.get("series") or []


def _read_latest_snapshot(node, remaining_seconds: float) -> dict[str, Any] | None:
    source_client = REDIS_STRATEGY_COST_SNAPSHOT_KEY.client.get_client(node)
    client = IsolatedSnapshotRedisClient(source_client, min(remaining_seconds, SNAPSHOT_READ_NODE_BUDGET_SECONDS))
    try:
        history = StrategyCostSnapshotStore(node, client=client).read(limit=1)
        return history[0] if history else None
    finally:
        client.close()


class GetRedisManagementOverviewResource(Resource):
    """返回本环境 Redis 节点、路由、内存趋势与策略成本证据。"""

    def perform_request(self, params):
        generated_at = int(time())
        routing, node_models = load_routing_observation()
        start_time = generated_at - THREE_HOURS_SECONDS
        used_series = _query_metric("redis_memory_used_bytes", routing["cluster_name"], start_time, generated_at)
        capacity_series = _query_metric("redis_memory_max_bytes", routing["cluster_name"], start_time, generated_at)

        node_snapshots = {}
        node_model_by_id = {node.id: node for node in node_models}
        snapshot_deadline = monotonic() + SNAPSHOT_READ_TOTAL_BUDGET_SECONDS
        for node in routing["nodes"]:
            node_model = node_model_by_id.get(node["id"])
            if node_model is None or not node["is_enable"]:
                node_snapshots[node["id"]] = None
                continue
            remaining_seconds = snapshot_deadline - monotonic()
            if remaining_seconds <= 0:
                node_snapshots[node["id"]] = None
                continue
            try:
                snapshot = _read_latest_snapshot(node_model, remaining_seconds)
            except Exception:
                logger.exception("read Redis strategy cost snapshot failed: node_id=%s", node["id"])
                snapshot = None
            node_snapshots[node["id"]] = snapshot

        cost_evidence = build_cost_evidence(routing, node_snapshots)
        snapshot_evidence_by_node = {item["node_id"]: item for item in cost_evidence["nodes"]}
        nodes = []
        for node in routing["nodes"]:
            node_model = node_model_by_id.get(node["id"])
            nodes.append(
                {
                    **node,
                    "memory": build_memory_view(
                        str(node_model) if node_model else "",
                        used_series,
                        capacity_series,
                        reference_time=generated_at,
                    ),
                    "snapshot": snapshot_evidence_by_node.get(node["id"]),
                }
            )

        return {
            "generated_at": generated_at,
            "routing": {
                key: routing[key]
                for key in (
                    "snapshot_id",
                    "cluster_name",
                    "routers",
                    "max_strategy_id",
                    "terminal_score",
                    "topology_validation",
                )
            },
            "nodes": nodes,
            "cost_evidence": cost_evidence,
        }
