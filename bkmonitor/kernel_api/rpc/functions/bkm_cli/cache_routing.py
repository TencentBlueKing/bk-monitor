"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

bkm-cli CacheRouter 快照、变更预览与受控写入。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from django.db import router as db_router
from django.db import transaction
from django.db.models import Max

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli.cache import _node_identity

SNAPSHOT_SCHEMA = "cache-routing-snapshot/v1"
PLAN_SCHEMA = "replace-positive-routes/v1"
DRAIN_PLAN_SCHEMA = "drain-positive-routes/v1"
MAX_POSITIVE_ROUTES = 1000
DB_INT_MAX = 2_147_483_647
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
REVISION_KEY_PREFIX = "BKM_CLI_CACHE_ROUTING_REVISION"
HARD_CHANGE_PERCENT = 50
HARD_CHANGE_RATIO = HARD_CHANGE_PERCENT / 100
STRATEGY_ITERATOR_CHUNK_SIZE = 2000

LIST_ALLOWED_FIELDS = {"operation", "expected_snapshot_id", "desired_routes", "drain_node_id", "bk_tenant_id"}
MANAGE_ALLOWED_FIELDS = {
    "operation",
    "expected_snapshot_id",
    "expected_after_snapshot_id",
    "plan_id",
    "desired_routes",
    "drain_node_id",
    "confirmed",
    "operator",
    "exclusive_change_window",
    # 由服务桥注入，不参与 CacheRouter 路由选择。
    "bk_tenant_id",
}

logger = logging.getLogger(__name__)


def _get_value(value: Any, field: str) -> Any:
    if isinstance(value, dict):
        return value.get(field)
    return getattr(value, field)


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _safe_node(node: Any) -> dict[str, Any]:
    if isinstance(node, dict):
        return {
            "id": node["id"],
            "node_alias": node.get("node_alias") or "",
            "cluster_name": node["cluster_name"],
            "cache_type": node["cache_type"],
            "is_default": bool(node["is_default"]),
            "is_enable": bool(node["is_enable"]),
        }
    return _node_identity(node)


def _topology_errors(
    cluster_name: str,
    nodes: list[dict[str, Any]],
    raw_routes: list[dict[str, int]],
    max_strategy_id: int,
) -> list[str]:
    errors: list[str] = []
    node_by_id = {node["id"]: node for node in nodes}
    defaults = [node for node in nodes if node["is_default"]]
    if len(defaults) != 1:
        errors.append(f"default node count must be 1, got {len(defaults)}")
    elif not defaults[0]["is_enable"]:
        errors.append("default node must be enabled")

    aliases = [node["node_alias"] for node in nodes]
    if any(not alias for alias in aliases):
        errors.append("all cache nodes must have a non-empty node_alias")
    if len(aliases) != len(set(aliases)):
        errors.append("cache node_alias must be unique within the cluster")
    if any(node["cluster_name"] != cluster_name for node in nodes):
        errors.append("all cache nodes must belong to the current cluster")

    positive_routes = [route for route in raw_routes if route["strategy_score"] > 0]
    positive_scores = [route["strategy_score"] for route in positive_routes]
    if not positive_routes:
        errors.append("at least one positive route is required")
    elif positive_routes[-1]["strategy_score"] <= max_strategy_id:
        errors.append("terminal route must be greater than max_strategy_id")
    if len(positive_scores) != len(set(positive_scores)):
        errors.append("positive strategy_score values must be unique")

    for route in raw_routes:
        node = node_by_id.get(route["node_id"])
        if node is None:
            errors.append(f"route score={route['strategy_score']} references a node outside the current cluster")
        elif not node["is_enable"]:
            errors.append(f"route score={route['strategy_score']} references disabled node_id={route['node_id']}")
    return errors


def _build_snapshot(
    cluster_name: str,
    nodes: list[Any],
    routes: list[Any],
    *,
    max_strategy_id: int,
    revision: int = 0,
) -> dict[str, Any]:
    safe_nodes = sorted((_safe_node(node) for node in nodes), key=lambda node: node["id"])
    raw_routes = sorted(
        (
            {
                "strategy_score": int(_get_value(route, "strategy_score")),
                "node_id": int(_get_value(route, "node_id")),
            }
            for route in routes
        ),
        key=lambda route: (route["strategy_score"], route["node_id"]),
    )
    max_strategy_id = int(max_strategy_id or 0)
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise CustomException(message="cache routing revision must be a non-negative integer")
    default_nodes = [node for node in safe_nodes if node["is_default"]]
    default_node = default_nodes[0] if len(default_nodes) == 1 else None
    snapshot_payload = {
        "snapshot_schema": SNAPSHOT_SCHEMA,
        "cluster_name": cluster_name,
        "default_node": default_node,
        "nodes": safe_nodes,
        "raw_routes": raw_routes,
        "max_strategy_id": max_strategy_id,
        "max_strategy_id_scope": "all_strategy_rows",
        "revision": revision,
    }
    snapshot_id = _canonical_digest(snapshot_payload)
    positive_routes = [route for route in raw_routes if route["strategy_score"] > 0]
    reserved_routes = [route for route in raw_routes if route["strategy_score"] <= 0]
    node_by_id = {node["id"]: node for node in safe_nodes}

    router_items: list[dict[str, Any]] = []
    # strategy_id=0 由 get_node_by_strategy_id() 强制走 default_node，不属于正数路由段。
    floor = 1
    for route in positive_routes:
        router_items.append(
            {
                "strategy_score": route["strategy_score"],
                "score_range": {"floor": floor, "ceil": route["strategy_score"] - 1},
                "node": node_by_id.get(route["node_id"]),
            }
        )
        floor = route["strategy_score"]

    errors = _topology_errors(cluster_name, safe_nodes, raw_routes, max_strategy_id)
    return {
        "snapshot_schema": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "cluster_name": cluster_name,
        "router_count": len(router_items),
        "routers": router_items,
        "raw_routes": raw_routes,
        "reserved_routes": reserved_routes,
        "nodes": safe_nodes,
        "default_node": default_node,
        "max_strategy_id": max_strategy_id,
        "max_strategy_id_scope": "all_strategy_rows",
        "revision": revision,
        "suggested_cutoff_100": (max_strategy_id // 100 + 1) * 100,
        "suggested_cutoff_usage": "intermediate_boundary_only",
        "terminal_score": positive_routes[-1]["strategy_score"] if positive_routes else None,
        "topology_validation": {"valid": not errors, "errors": errors},
    }


def _normalize_desired_routes(value: Any) -> list[dict[str, int]]:
    if not isinstance(value, list):
        raise CustomException(message="desired_routes must be an array")
    if not value:
        raise CustomException(message="desired_routes must contain at least one positive route")
    if len(value) > MAX_POSITIVE_ROUTES:
        raise CustomException(message=f"desired_routes exceeds the limit of {MAX_POSITIVE_ROUTES}")

    normalized: list[dict[str, int]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"strategy_score", "node_id"}:
            raise CustomException(message=f"desired_routes[{index}] must contain only strategy_score and node_id")
        score = item["strategy_score"]
        node_id = item["node_id"]
        if isinstance(score, bool) or not isinstance(score, int) or not 0 < score <= DB_INT_MAX:
            raise CustomException(
                message=f"desired_routes[{index}].strategy_score must be a positive signed 32-bit integer"
            )
        if isinstance(node_id, bool) or not isinstance(node_id, int) or not 0 < node_id <= DB_INT_MAX:
            raise CustomException(message=f"desired_routes[{index}].node_id must be a positive signed 32-bit integer")
        normalized.append({"strategy_score": score, "node_id": node_id})

    scores = [route["strategy_score"] for route in normalized]
    if scores != sorted(scores):
        raise CustomException(message="desired_routes must be ordered by strategy_score")
    if len(scores) != len(set(scores)):
        raise CustomException(message="desired_routes strategy_score values must be unique")
    return normalized


def _validate_desired_routes(snapshot: dict[str, Any], desired_routes: list[dict[str, int]]) -> None:
    topology = snapshot["topology_validation"]
    if "positive strategy_score values must be unique" in topology["errors"]:
        raise CustomException(message="current cache routing has duplicate positive strategy_score values")

    enabled_node_ids = {node["id"] for node in snapshot["nodes"] if node["is_enable"]}
    invalid_node_ids = sorted({route["node_id"] for route in desired_routes} - enabled_node_ids)
    if invalid_node_ids:
        raise CustomException(message=f"desired_routes references unavailable node IDs: {invalid_node_ids}")

    terminal = desired_routes[-1]["strategy_score"]
    if terminal <= snapshot["max_strategy_id"]:
        raise CustomException(message="desired terminal score must be greater than max_strategy_id")
    current_terminal = snapshot["terminal_score"]
    if current_terminal is not None and terminal < current_terminal:
        raise CustomException(message="desired terminal score must not shrink the current terminal score")


def _after_snapshot(snapshot: dict[str, Any], desired_routes: list[dict[str, int]]) -> dict[str, Any]:
    routes = [*snapshot["reserved_routes"], *desired_routes]
    return _build_snapshot(
        snapshot["cluster_name"],
        snapshot["nodes"],
        routes,
        max_strategy_id=snapshot["max_strategy_id"],
        revision=snapshot["revision"] + 1,
    )


def _route_diff(
    before_routes: list[dict[str, int]], desired_routes: list[dict[str, int]]
) -> dict[str, list[dict[str, int]]]:
    before = {route["strategy_score"]: route["node_id"] for route in before_routes if route["strategy_score"] > 0}
    desired = {route["strategy_score"]: route["node_id"] for route in desired_routes}
    created = [{"strategy_score": score, "node_id": desired[score]} for score in sorted(desired.keys() - before.keys())]
    deleted = [{"strategy_score": score, "node_id": before[score]} for score in sorted(before.keys() - desired.keys())]
    updated = [
        {"strategy_score": score, "before_node_id": before[score], "after_node_id": desired[score]}
        for score in sorted(before.keys() & desired.keys())
        if before[score] != desired[score]
    ]
    return {"create": created, "update": updated, "delete": deleted}


def _build_impact_summary(
    snapshot: dict[str, Any],
    desired_routes: list[dict[str, int]],
    strategy_rows: Iterable[Any],
    *,
    permitted_drained_node_id: int | None = None,
) -> dict[str, Any]:
    before_routes = [route for route in snapshot["raw_routes"] if route["strategy_score"] > 0]
    before_scores = [route["strategy_score"] for route in before_routes]
    before_nodes = [route["node_id"] for route in before_routes]
    after_scores = [route["strategy_score"] for route in desired_routes]
    after_nodes = [route["node_id"] for route in desired_routes]

    total = 0
    enabled_total = 0
    affected = 0
    affected_enabled = 0
    before_ownership: dict[int, int] = defaultdict(int)
    after_ownership: dict[int, int] = defaultdict(int)
    movements: dict[tuple[int | None, int | None], list[int]] = defaultdict(lambda: [0, 0])

    for strategy in strategy_rows:
        strategy_id = int(_get_value(strategy, "id"))
        if strategy_id <= 0 or strategy_id > snapshot["max_strategy_id"]:
            continue
        is_enabled = bool(_get_value(strategy, "is_enabled"))
        total += 1
        enabled_total += int(is_enabled)

        before_index = bisect_right(before_scores, strategy_id)
        before_node_id = before_nodes[before_index] if before_index < len(before_nodes) else None
        after_index = bisect_right(after_scores, strategy_id)
        after_node_id = after_nodes[after_index] if after_index < len(after_nodes) else None
        if before_node_id is not None:
            before_ownership[before_node_id] += 1
        if after_node_id is not None:
            after_ownership[after_node_id] += 1
        if before_node_id == after_node_id:
            continue

        affected += 1
        affected_enabled += int(is_enabled)
        movement = movements[(before_node_id, after_node_id)]
        movement[0] += 1
        movement[1] += int(is_enabled)

    affected_ratio = round(affected / total, 6) if total else 0.0
    affected_enabled_ratio = round(affected_enabled / enabled_total, 6) if enabled_total else 0.0
    effective_ratio = max(affected_ratio, affected_enabled_ratio)
    drained_node_ids = sorted(node_id for node_id in before_ownership if after_ownership.get(node_id, 0) == 0)
    before_owned_nodes = sorted(node_id for node_id, count in before_ownership.items() if count)
    after_owned_nodes = sorted(node_id for node_id, count in after_ownership.items() if count)
    collapsed_to_single_node = len(before_owned_nodes) > 1 and len(after_owned_nodes) == 1

    block_reasons: list[str] = []
    if (total and affected * 100 >= total * HARD_CHANGE_PERCENT) or (
        enabled_total and affected_enabled * 100 >= enabled_total * HARD_CHANGE_PERCENT
    ):
        block_reasons.append(
            f"route change affects {affected}/{total} strategies ({affected_ratio:.2%}) and "
            f"{affected_enabled}/{enabled_total} enabled strategies ({affected_enabled_ratio:.2%}); "
            f"effective ratio {effective_ratio:.2%} reaches the hard limit {HARD_CHANGE_RATIO:.2%}"
        )
    blocked_drained_node_ids = [node_id for node_id in drained_node_ids if node_id != permitted_drained_node_id]
    if blocked_drained_node_ids:
        block_reasons.append(f"route change would drain strategy ownership from node IDs: {blocked_drained_node_ids}")
    if collapsed_to_single_node:
        block_reasons.append(
            f"route change would collapse strategy ownership from {len(before_owned_nodes)} nodes "
            f"to one node_id={after_owned_nodes[0]}"
        )

    node_movements = [
        {
            "before_node_id": before_node_id,
            "after_node_id": after_node_id,
            "strategy_count": counts[0],
            "enabled_strategy_count": counts[1],
        }
        for (before_node_id, after_node_id), counts in sorted(
            movements.items(),
            key=lambda item: (
                -1 if item[0][0] is None else item[0][0],
                -1 if item[0][1] is None else item[0][1],
            ),
        )
    ]
    return {
        "scope": "current_alarm_cluster_strategy_rows",
        "hard_limit_ratio": HARD_CHANGE_RATIO,
        "total_strategy_count": total,
        "affected_strategy_count": affected,
        "affected_ratio": affected_ratio,
        "enabled_strategy_count": enabled_total,
        "affected_enabled_strategy_count": affected_enabled,
        "affected_enabled_ratio": affected_enabled_ratio,
        "effective_affected_ratio": effective_ratio,
        "node_movements": node_movements,
        "drained_node_ids": drained_node_ids,
        "collapsed_to_single_node": collapsed_to_single_node,
        "apply_allowed": not block_reasons,
        "block_reasons": block_reasons,
    }


def _normalize_drain_node_id(snapshot: dict[str, Any], value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= DB_INT_MAX:
        raise CustomException(message="drain_node_id must be a positive signed 32-bit integer")
    if value not in {node["id"] for node in snapshot["nodes"]}:
        raise CustomException(message=f"drain_node_id={value} is unavailable in the current cluster")
    return value


def _build_drain_summary(
    snapshot: dict[str, Any],
    desired_routes: list[dict[str, int]],
    drain_node_id: int,
) -> dict[str, Any]:
    node_by_id = {node["id"]: node for node in snapshot["nodes"]}
    drain_node = node_by_id[drain_node_id]
    before_routes = [route for route in snapshot["raw_routes"] if route["strategy_score"] > 0]
    before_by_score = {route["strategy_score"]: route["node_id"] for route in before_routes}
    desired_by_score = {route["strategy_score"]: route["node_id"] for route in desired_routes}
    target_scores = sorted(score for score, node_id in before_by_score.items() if node_id == drain_node_id)
    remaining_target_scores = sorted(
        route["strategy_score"] for route in desired_routes if route["node_id"] == drain_node_id
    )
    reserved_references = sum(route["node_id"] == drain_node_id for route in snapshot["reserved_routes"])
    changed_scores = sorted(
        score
        for score in before_by_score.keys() & desired_by_score.keys()
        if before_by_score[score] != desired_by_score[score]
    )

    block_reasons: list[str] = []
    if drain_node["is_default"]:
        block_reasons.append("drain_node_id must not be the default node")
    if not drain_node["is_enable"]:
        block_reasons.append("drain_node_id must be enabled before a planned drain")
    if not snapshot["topology_validation"]["valid"]:
        block_reasons.append("current cache routing topology must be valid before a planned drain")
    if not target_scores:
        block_reasons.append(f"drain_node_id={drain_node_id} has no positive CacheRouter references")
    if reserved_references:
        block_reasons.append(f"reserved CacheRouter rows still reference drain_node_id={drain_node_id}")

    before_scores = [route["strategy_score"] for route in before_routes]
    desired_scores = [route["strategy_score"] for route in desired_routes]
    if before_scores != desired_scores:
        block_reasons.append("drain plan must preserve the exact positive strategy_score set and order")

    for score, before_node_id in before_by_score.items():
        after_node_id = desired_by_score.get(score)
        if before_node_id != drain_node_id and after_node_id is not None and after_node_id != before_node_id:
            block_reasons.append(f"drain plan changes non-target route score={score}")
    if remaining_target_scores:
        block_reasons.append(
            f"desired_routes still references drain_node_id={drain_node_id} at scores={remaining_target_scores}"
        )

    return {
        "drain_node": drain_node,
        "changed_strategy_scores": changed_scores,
        "positive_route_references_before": len(target_scores),
        "remaining_positive_route_references": len(remaining_target_scores),
        "reserved_route_references": reserved_references,
        "cache_node_mutated": False,
        "safe_to_disable_or_delete": False,
        "block_reasons": block_reasons,
    }


def _build_impact_contract(
    snapshot: dict[str, Any],
    desired_routes: list[dict[str, int]],
    strategy_rows: Iterable[Any],
    *,
    drain_node_id: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    impact_summary = _build_impact_summary(
        snapshot,
        desired_routes,
        strategy_rows,
        permitted_drained_node_id=drain_node_id,
    )
    if drain_node_id is None:
        return impact_summary, None

    drain_summary = _build_drain_summary(snapshot, desired_routes, drain_node_id)
    impact_summary["block_reasons"].extend(drain_summary["block_reasons"])
    impact_summary["apply_allowed"] = not impact_summary["block_reasons"]
    return impact_summary, drain_summary


def _impact_digest(impact_summary: dict[str, Any], drain_summary: dict[str, Any] | None) -> str:
    payload: dict[str, Any] = {"impact_summary": impact_summary}
    if drain_summary is not None:
        payload["drain_summary"] = drain_summary
    return _canonical_digest(payload)


def _build_plan(
    snapshot: dict[str, Any],
    desired_routes: Any,
    expected_snapshot_id: Any,
    *,
    check_current_snapshot: bool,
    strategy_rows: Iterable[Any],
    drain_node_id: int | None = None,
) -> dict[str, Any]:
    if not isinstance(expected_snapshot_id, str) or not expected_snapshot_id.strip():
        raise CustomException(message="expected_snapshot_id is required")
    expected_snapshot_id = expected_snapshot_id.strip()
    if not DIGEST_PATTERN.fullmatch(expected_snapshot_id):
        raise CustomException(message="expected_snapshot_id must use canonical sha256:<64 lowercase hex> form")
    if check_current_snapshot and snapshot["snapshot_id"] != expected_snapshot_id:
        raise CustomException(message="cache routing snapshot is stale; take a new snapshot and preview again")
    desired = _normalize_desired_routes(desired_routes)
    _validate_desired_routes(snapshot, desired)
    if drain_node_id is not None:
        drain_node_id = _normalize_drain_node_id(snapshot, drain_node_id)

    after = _after_snapshot(snapshot, desired)
    if not after["topology_validation"]["valid"]:
        raise CustomException(
            message=f"desired cache routing topology is invalid: {after['topology_validation']['errors']}"
        )
    diff = _route_diff(snapshot["raw_routes"], desired)
    impact_summary, drain_summary = _build_impact_contract(
        snapshot,
        desired,
        strategy_rows,
        drain_node_id=drain_node_id,
    )
    impact_digest = _impact_digest(impact_summary, drain_summary)
    plan_schema = DRAIN_PLAN_SCHEMA if drain_node_id is not None else PLAN_SCHEMA
    plan_payload = {
        "plan_schema": plan_schema,
        "cluster_name": snapshot["cluster_name"],
        "expected_snapshot_id": expected_snapshot_id,
        "desired_routes": desired,
        "impact_digest": impact_digest,
    }
    if drain_node_id is not None:
        plan_payload["drain_node_id"] = drain_node_id
    result = {
        "plan_schema": plan_schema,
        "plan_id": _canonical_digest(plan_payload),
        "expected_snapshot_id": expected_snapshot_id,
        "expected_after_snapshot_id": after["snapshot_id"],
        "desired_routes": desired,
        "changed": any(diff.values()),
        "diff": diff,
        "impact_summary": impact_summary,
        "impact_digest": impact_digest,
        "before": snapshot,
        "after": after,
    }
    if drain_summary is not None:
        result["drain_summary"] = drain_summary
    return result


def _build_preview(
    snapshot: dict[str, Any],
    desired_routes: Any,
    expected_snapshot_id: Any,
    *,
    strategy_rows: Iterable[Any],
) -> dict[str, Any]:
    plan = _build_plan(
        snapshot,
        desired_routes,
        expected_snapshot_id,
        check_current_snapshot=True,
        strategy_rows=strategy_rows,
    )
    result = {
        **plan,
        "operation": "preview",
        "states": {
            "configuration": "previewed",
            "worker_activation": "not_evaluated",
            "traffic_landing": "not_evaluated",
            "capacity": "not_evaluated",
        },
    }
    if not plan["impact_summary"]["apply_allowed"]:
        reasons = "; ".join(plan["impact_summary"]["block_reasons"])
        result["next_actions"] = [
            f"Do not call manage-cache-routing for this plan: {reasons}",
            "Split the route change into independently previewed and validated plans, or use the separately governed "
            "manual recovery path.",
        ]
    return result


def _build_drain_preview(
    snapshot: dict[str, Any],
    desired_routes: Any,
    expected_snapshot_id: Any,
    *,
    drain_node_id: Any,
    strategy_rows: Iterable[Any],
) -> dict[str, Any]:
    plan = _build_plan(
        snapshot,
        desired_routes,
        expected_snapshot_id,
        check_current_snapshot=True,
        strategy_rows=strategy_rows,
        drain_node_id=drain_node_id,
    )
    result = {
        **plan,
        "operation": "drain_preview",
        "states": {
            "configuration": "previewed",
            "worker_activation": "not_evaluated",
            "traffic_landing": "not_evaluated",
            "capacity": "not_evaluated",
        },
    }
    if not plan["impact_summary"]["apply_allowed"]:
        reasons = "; ".join(plan["impact_summary"]["block_reasons"])
        result["next_actions"] = [
            f"Do not call manage-cache-routing drain_apply for this plan: {reasons}",
            "Use independently previewed rebalance steps, or the separately governed recovery/default-node path.",
        ]
    return result


def _cluster_name() -> str:
    from alarm_backends.core.cluster import get_cluster

    return get_cluster().name


def _load_cluster_strategy_rows(*, using: str, max_strategy_id: int) -> Iterator[dict[str, Any]]:
    from alarm_backends.cluster import TargetType
    from alarm_backends.core.cluster import get_cluster
    from bkmonitor.models import StrategyModel

    cluster = get_cluster()
    queryset = (
        StrategyModel.objects.using(using)
        .filter(id__lte=max_strategy_id)
        .order_by("id")
        .values("id", "bk_biz_id", "is_enabled")
    )
    for row in queryset.iterator(chunk_size=STRATEGY_ITERATOR_CHUNK_SIZE):
        if cluster.match(TargetType.biz, row["bk_biz_id"]):
            yield {"id": row["id"], "is_enabled": row["is_enabled"]}


def _revision_key(cluster_name: str) -> str:
    return f"{REVISION_KEY_PREFIX}:{cluster_name}"


def _load_routing_revision(*, cluster_name: str, using: str, lock: bool) -> int:
    from bkmonitor.models import GlobalConfig

    queryset = GlobalConfig.objects.using(using)
    key = _revision_key(cluster_name)
    if lock:
        revision_config, _ = queryset.get_or_create(
            key=key,
            defaults={
                "value": 0,
                "description": "bkm-cli CacheRouter monotonic revision",
                "data_type": "Integer",
                "is_internal": True,
            },
        )
        revision_config = queryset.select_for_update().get(pk=revision_config.pk)
    else:
        revision_config = queryset.filter(key=key).only("value").first()

    revision = 0 if revision_config is None else revision_config.value
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise CustomException(message=f"invalid cache routing revision value for cluster={cluster_name}")
    return revision


def _advance_routing_revision(snapshot: dict[str, Any], *, using: str) -> None:
    from bkmonitor.models import GlobalConfig

    updated = (
        GlobalConfig.objects.using(using)
        .filter(
            key=_revision_key(snapshot["cluster_name"]),
            value=snapshot["revision"],
        )
        .update(value=snapshot["revision"] + 1)
    )
    if updated != 1:
        raise CustomException(message="cache routing revision changed unexpectedly; transaction rolled back")


def _load_routing_snapshot(*, using: str, lock: bool) -> dict[str, Any]:
    from bkmonitor.models import CacheNode, CacheRouter, StrategyModel

    cluster_name = _cluster_name()
    node_queryset = CacheNode.objects.using(using).filter(cluster_name=cluster_name).order_by("id")
    route_queryset = (
        CacheRouter.objects.using(using).filter(cluster_name=cluster_name).order_by("strategy_score", "node_id")
    )
    if lock:
        node_queryset = node_queryset.select_for_update()
        route_queryset = route_queryset.select_for_update()

    nodes = list(node_queryset)
    routes = list(route_queryset.values("strategy_score", "node_id"))
    revision = _load_routing_revision(cluster_name=cluster_name, using=using, lock=lock)
    strategy_queryset = StrategyModel.objects.using(using)
    if lock:
        # 路由变更窗口很短；锁住当前最大 ID 行以收紧并发窗口。
        # 这不代替 exclusive_change_window：不同数据库隔离级别对新增行的锁语义不同。
        max_strategy_id = (
            strategy_queryset.select_for_update().order_by("-id").values_list("id", flat=True).first() or 0
        )
    else:
        max_strategy_id = strategy_queryset.aggregate(max_id=Max("id"))["max_id"] or 0
    return _build_snapshot(
        cluster_name,
        nodes,
        routes,
        max_strategy_id=max_strategy_id,
        revision=revision,
    )


def _runtime_refresh_contract() -> dict[str, Any]:
    try:
        from alarm_backends.core.storage import redis_cluster

        has_ttl_refresh = hasattr(redis_cluster, "STRATEGY_ROUTER_CACHE_AT") and hasattr(
            redis_cluster, "_router_cache_ttl"
        )
    except (AttributeError, ImportError):
        # 本地最小测试配置可能没有加载 Redis 后端设置；保守回退为进程缓存契约。
        redis_cluster = None
        has_ttl_refresh = False
    ttl_seconds = None
    if has_ttl_refresh:
        try:
            ttl_seconds = int(redis_cluster._router_cache_ttl())
        except (AttributeError, TypeError, ValueError):
            ttl_seconds = None
    return {
        "mode": "ttl_refresh" if has_ttl_refresh else "process_lifetime_cache",
        # 这里只能识别当前 API 进程加载的源码能力，不能证明所有 alarm worker 已发布同一版本。
        "capability_source": "api_process_code",
        "worker_deployment_verified": False,
        "ttl_seconds": ttl_seconds,
        "stale_while_error": bool(has_ttl_refresh),
        "restart_required_if_no_ttl_refresh": not has_ttl_refresh,
        "db_readback_is_runtime_activation": False,
        "runtime_validation_required": True,
    }


def _validate_keys(params: Any, allowed_fields: set[str]) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise CustomException(message="params must be an object")
    unknown = sorted(set(params) - allowed_fields)
    if unknown:
        raise CustomException(message=f"unsupported params: {unknown}")
    return params


def list_cache_routing(params: dict[str, Any]) -> dict[str, Any]:
    params = _validate_keys(params or {}, LIST_ALLOWED_FIELDS)
    operation = params.get("operation") or "snapshot"
    if operation not in {"snapshot", "preview", "drain_preview"}:
        raise CustomException(message="operation only supports snapshot, preview, or drain_preview")
    from bkmonitor.models import CacheRouter

    using = db_router.db_for_read(CacheRouter) or "default"
    snapshot = _load_routing_snapshot(using=using, lock=False)
    contract = _runtime_refresh_contract()
    if operation == "snapshot":
        if "expected_snapshot_id" in params or "desired_routes" in params or "drain_node_id" in params:
            raise CustomException(message="snapshot operation does not accept preview fields")
        return {
            **snapshot,
            "operation": "snapshot",
            "runtime_refresh_contract": contract,
            "states": {
                "configuration": "observed",
                "worker_activation": "not_evaluated",
                "traffic_landing": "not_evaluated",
                "capacity": "not_evaluated",
            },
        }

    strategy_rows = _load_cluster_strategy_rows(using=using, max_strategy_id=snapshot["max_strategy_id"])
    if operation == "preview":
        if "drain_node_id" in params:
            raise CustomException(message="preview operation does not accept drain_node_id")
        preview = _build_preview(
            snapshot,
            params.get("desired_routes"),
            params.get("expected_snapshot_id"),
            strategy_rows=strategy_rows,
        )
    else:
        if "drain_node_id" not in params:
            raise CustomException(message="drain_node_id is required for drain_preview")
        preview = _build_drain_preview(
            snapshot,
            params.get("desired_routes"),
            params.get("expected_snapshot_id"),
            drain_node_id=params.get("drain_node_id"),
            strategy_rows=strategy_rows,
        )
    preview["runtime_refresh_contract"] = contract
    return preview


def _write_positive_routes(snapshot: dict[str, Any], desired_routes: list[dict[str, int]], *, using: str) -> None:
    from bkmonitor.models import CacheRouter

    cluster_name = snapshot["cluster_name"]
    before = {
        route["strategy_score"]: route["node_id"] for route in snapshot["raw_routes"] if route["strategy_score"] > 0
    }
    desired = {route["strategy_score"]: route["node_id"] for route in desired_routes}

    deleted_scores = sorted(before.keys() - desired.keys())
    if deleted_scores:
        CacheRouter.objects.using(using).filter(
            cluster_name=cluster_name,
            strategy_score__gt=0,
            strategy_score__in=deleted_scores,
        ).delete()

    for score in sorted(before.keys() & desired.keys()):
        if before[score] == desired[score]:
            continue
        updated = (
            CacheRouter.objects.using(using)
            .filter(
                cluster_name=cluster_name,
                strategy_score=score,
            )
            .update(node_id=desired[score])
        )
        if updated != 1:
            raise CustomException(message=f"expected one CacheRouter row for score={score}, updated={updated}")

    created_scores = sorted(desired.keys() - before.keys())
    if created_scores:
        CacheRouter.objects.using(using).bulk_create(
            [
                CacheRouter(cluster_name=cluster_name, strategy_score=score, node_id=desired[score])
                for score in created_scores
            ]
        )


def _required_text(params: dict[str, Any], field: str, *, max_length: int = 128) -> str:
    value = params.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CustomException(message=f"{field} is required")
    value = value.strip()
    if len(value) > max_length:
        raise CustomException(message=f"{field} exceeds max length {max_length}")
    return value


def _required_digest(params: dict[str, Any], field: str) -> str:
    value = _required_text(params, field)
    if not DIGEST_PATTERN.fullmatch(value):
        raise CustomException(message=f"{field} must use canonical sha256:<64 lowercase hex> form")
    return value


def manage_cache_routing(params: dict[str, Any]) -> dict[str, Any]:
    params = _validate_keys(params, MANAGE_ALLOWED_FIELDS)
    operation = params.get("operation")
    if operation not in {"apply", "drain_apply"}:
        raise CustomException(message="operation must be apply or drain_apply")
    if operation == "apply" and "drain_node_id" in params:
        raise CustomException(message="apply operation does not accept drain_node_id")
    if operation == "drain_apply" and "drain_node_id" not in params:
        raise CustomException(message="drain_node_id is required for drain_apply")
    if params.get("confirmed") is not True:
        raise CustomException(message="confirmed must be true")
    if params.get("exclusive_change_window") is not True:
        raise CustomException(message="exclusive_change_window must be true")
    operator = _required_text(params, "operator")
    expected_snapshot_id = _required_digest(params, "expected_snapshot_id")
    expected_after_snapshot_id = _required_digest(params, "expected_after_snapshot_id")
    expected_plan_id = _required_digest(params, "plan_id")

    runtime_contract = _runtime_refresh_contract()
    if runtime_contract["mode"] != "ttl_refresh":
        raise CustomException(
            message=(
                "manage-cache-routing apply is disabled because the current API process code does not expose "
                "ttl_refresh; this check does not verify alarm worker deployment"
            )
        )

    from bkmonitor.models import CacheRouter

    using = db_router.db_for_write(CacheRouter) or "default"
    with transaction.atomic(using=using):
        before = _load_routing_snapshot(using=using, lock=True)
        plan = _build_plan(
            before,
            params.get("desired_routes"),
            expected_snapshot_id,
            check_current_snapshot=False,
            strategy_rows=_load_cluster_strategy_rows(
                using=using,
                max_strategy_id=before["max_strategy_id"],
            ),
            drain_node_id=params.get("drain_node_id") if operation == "drain_apply" else None,
        )
        if plan["plan_id"] != expected_plan_id:
            raise CustomException(message="plan_id does not match the locked routing plan")
        if plan["expected_after_snapshot_id"] != expected_after_snapshot_id:
            raise CustomException(message="expected_after_snapshot_id does not match the locked routing plan")
        if before["snapshot_id"] != expected_snapshot_id:
            raise CustomException(message="cache routing snapshot is stale; take a new snapshot and preview again")
        if not plan["impact_summary"]["apply_allowed"]:
            reasons = "; ".join(plan["impact_summary"]["block_reasons"])
            raise CustomException(message=f"route change is blocked: {reasons}")

        _write_positive_routes(before, plan["desired_routes"], using=using)
        _advance_routing_revision(before, using=using)
        impact_after_write, drain_after_write = _build_impact_contract(
            before,
            plan["desired_routes"],
            _load_cluster_strategy_rows(
                using=using,
                max_strategy_id=before["max_strategy_id"],
            ),
            drain_node_id=params.get("drain_node_id") if operation == "drain_apply" else None,
        )
        if _impact_digest(impact_after_write, drain_after_write) != plan["impact_digest"]:
            raise CustomException(message="strategy impact changed during apply; transaction rolled back")
        after = _load_routing_snapshot(using=using, lock=False)
        if after["reserved_routes"] != before["reserved_routes"]:
            raise CustomException(message="reserved CacheRouter rows changed unexpectedly; transaction rolled back")
        if after["snapshot_id"] != expected_after_snapshot_id:
            raise CustomException(
                message="CacheRouter database readback does not match the preview; transaction rolled back"
            )

    logger.info(
        "CacheRouter apply completed operation=%s cluster=%s operator=%s plan_id=%s create=%d update=%d delete=%d "
        "affected=%d total=%d changed=%s",
        operation,
        before["cluster_name"],
        operator,
        expected_plan_id,
        len(plan["diff"]["create"]),
        len(plan["diff"]["update"]),
        len(plan["diff"]["delete"]),
        plan["impact_summary"]["affected_strategy_count"],
        plan["impact_summary"]["total_strategy_count"],
        plan["changed"],
    )
    result = {
        "operation": operation,
        "changed": plan["changed"],
        "plan_id": expected_plan_id,
        "previous_snapshot_id": expected_snapshot_id,
        "snapshot_id": after["snapshot_id"],
        "diff": plan["diff"],
        "impact_summary": plan["impact_summary"],
        "impact_digest": plan["impact_digest"],
        "routing": after,
        "runtime_refresh_contract": runtime_contract,
        "states": {
            "configuration": "readback_verified",
            "worker_activation": "pending",
            "traffic_landing": "not_evaluated",
            "capacity": "not_evaluated",
        },
    }
    if "drain_summary" in plan:
        result["drain_summary"] = plan["drain_summary"]
    return result


KernelRPCRegistry.register_function(
    func_name="bkm_cli.manage_cache_routing",
    summary="受控替换 alarm_backends Redis 正数路由表",
    description=(
        "使用预览产生的 snapshot_id、plan_id 和 expected_after_snapshot_id 在单一事务内替换 CacheRouter "
        "正数路由行；保留 score<=0 行，不管理 CacheNode 连接信息。必须 confirmed=true 且申明独占变更窗口；"
        "普通 apply 在当前集群至少半数策略改指、节点策略归属清空或多节点收缩为单节点时硬拒绝；"
        "drain_apply 只允许将一个已启用非默认节点的既有正路由原位改指，仍拒绝至少半数改指和收缩为单节点。"
    ),
    handler=manage_cache_routing,
    params_schema={
        "operation": "apply | drain_apply",
        "drain_node_id": "drain_apply 必填；当前集群已启用的非默认节点 ID",
        "expected_snapshot_id": "list-cache-routing preview/drain_preview 使用的前置快照",
        "expected_after_snapshot_id": "preview 计算的目标快照",
        "plan_id": "preview 计算的计划标识",
        "desired_routes": "完整、按 strategy_score 升序的正数路由表",
        "confirmed": "必须为 true",
        "operator": "操作人",
        "exclusive_change_window": "必须为 true",
    },
)

BkmCliOpRegistry.register(
    op_id="manage-cache-routing",
    func_name="bkm_cli.manage_cache_routing",
    summary="受控变更 alarm_backends Redis 路由",
    description=(
        "仅替换 CacheRouter 正数路由行；普通 apply 与计划缩容 drain_apply 使用独立 plan，均要求预览绑定、"
        "人工确认、独占变更窗口、策略影响硬门禁和事务内精确回读。drain 不修改 CacheNode。"
    ),
    capability_level="admin",
    risk_level="mutation",
    requires_confirmation=True,
    audit_tags=["cache", "redis", "routing", "mutation", "human-confirmation"],
    params_schema={
        "operation": "apply | drain_apply",
        "drain_node_id": "integer, drain_apply required",
        "expected_snapshot_id": "string",
        "expected_after_snapshot_id": "string",
        "plan_id": "string",
        "desired_routes": "array",
        "confirmed": "boolean, must be true",
        "operator": "string",
        "exclusive_change_window": "boolean, must be true",
    },
)
