"""Redis 策略成本快照的节点本地存储与采集逻辑。"""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import uuid4

from alarm_backends.core.cache.key import (
    LAST_CHECKPOINTS_CACHE_KEY,
    REDIS_STRATEGY_COST_SNAPSHOT_KEY,
    REDIS_STRATEGY_COST_SNAPSHOT_LOCK_KEY,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.item import detect_result_point_required
from alarm_backends.core.control.strategy import Strategy as ControlStrategy
from bkmonitor.models import CacheRouter

SNAPSHOT_HISTORY_LIMIT = 6
SNAPSHOT_INTERVAL_SECONDS = 3600
SNAPSHOT_TOTAL_BUDGET_SECONDS = 20
CHECK_RESULT_CLEAN_INTERVAL_SECONDS = 7200
GROUP_RESERVED_FIELDS = {"interval_list", "strategy_source", "bk_biz_id"}

logger = logging.getLogger("self_monitor")


class StrategyCostSnapshotStore:
    """在指定 CacheNode 的 service(DB10) 中读写最近快照。"""

    SNAPSHOT_TTL_SECONDS = REDIS_STRATEGY_COST_SNAPSHOT_KEY.ttl
    LOCK_TTL_SECONDS = REDIS_STRATEGY_COST_SNAPSHOT_LOCK_KEY.ttl

    def __init__(self, node, *, client=None):
        self.node = node
        self.client = client or REDIS_STRATEGY_COST_SNAPSHOT_KEY.client.get_client(node)
        self.snapshot_key = REDIS_STRATEGY_COST_SNAPSHOT_KEY.get_key(node_id=node.id)
        self.lock_key = REDIS_STRATEGY_COST_SNAPSHOT_LOCK_KEY.get_key(node_id=node.id)

    def try_lock(self, token: str) -> bool:
        return bool(self.client.set(self.lock_key, token, nx=True, ex=self.LOCK_TTL_SECONDS))

    def read(self, limit: int = 1) -> list[dict[str, Any]]:
        limit = min(max(int(limit), 1), SNAPSHOT_HISTORY_LIMIT)
        values = self.client.lrange(self.snapshot_key, 0, limit - 1)
        snapshots = []
        for history_index, value in enumerate(values):
            try:
                snapshots.append(json.loads(value))
            except (TypeError, ValueError):
                snapshots.append({"history_index": history_index, "error": "invalid snapshot JSON"})
        return snapshots

    def save(self, snapshot: dict[str, Any]) -> None:
        snapshot["snapshot_payload_bytes"] = 0
        while True:
            value = json.dumps(snapshot, separators=(",", ":"))
            payload_bytes = len(value.encode())
            if snapshot["snapshot_payload_bytes"] == payload_bytes:
                break
            snapshot["snapshot_payload_bytes"] = payload_bytes
        pipeline = self.client.pipeline()
        pipeline.lpush(self.snapshot_key, value)
        pipeline.ltrim(self.snapshot_key, 0, SNAPSHOT_HISTORY_LIMIT - 1)
        pipeline.expire(self.snapshot_key, self.SNAPSHOT_TTL_SECONDS)
        pipeline.execute()


def serialize_cache_node(node) -> dict[str, Any]:
    """返回足以对账且不含连接信息的 CacheNode 身份。"""

    return {
        "id": node.id,
        "node_alias": getattr(node, "node_alias", "") or "",
        "cluster_name": getattr(node, "cluster_name", "") or "",
        "cache_type": getattr(node, "cache_type", "") or "",
        "is_default": bool(getattr(node, "is_default", False)),
        "is_enable": bool(getattr(node, "is_enable", True)),
    }


def build_strategy_cost_profile(config: dict[str, Any]) -> dict[str, int]:
    """复用生产清理口径计算单条 series 的检测结果峰值成员数。"""

    strategy_id = int(config["id"])
    point_required = int(detect_result_point_required(config))
    interval = int(ControlStrategy(strategy_id, default_config=config).get_interval())
    if interval <= 0:
        raise ValueError(f"invalid strategy interval: {interval}")
    growth = -(-CHECK_RESULT_CLEAN_INTERVAL_SECONDS // interval)
    return {
        "point_required": point_required,
        "interval_seconds": interval,
        "clean_interval_seconds": CHECK_RESULT_CLEAN_INTERVAL_SECONDS,
        "growth_per_clean_cycle": growth,
        "peak_members_per_series": point_required + growth,
    }


def _int_value(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_group_index(raw_groups: Any) -> dict[int, dict[str, Any]]:
    if not isinstance(raw_groups, dict):
        raise ValueError("strategy group cache is not an object")

    index: dict[int, dict[str, Any]] = {}
    for raw_detail in raw_groups.values():
        try:
            detail = raw_detail if isinstance(raw_detail, dict) else json.loads(raw_detail)
        except (TypeError, ValueError):
            continue
        if not isinstance(detail, dict):
            continue
        for raw_strategy_id, raw_item_ids in detail.items():
            if raw_strategy_id in GROUP_RESERVED_FIELDS or not isinstance(raw_item_ids, list):
                continue
            strategy_id = _int_value(raw_strategy_id)
            if strategy_id is None:
                continue
            entry = index.setdefault(strategy_id, {"item_ids": set(), "bk_biz_id": detail.get("bk_biz_id")})
            entry["item_ids"].update(item_id for value in raw_item_ids if (item_id := _int_value(value)) is not None)
    return index


def _is_fresh(snapshots: list[dict[str, Any]], now: datetime) -> bool:
    if not snapshots or snapshots[0].get("error"):
        return False
    try:
        finished_at = datetime.fromisoformat(str(snapshots[0]["finished_at"]))
    except (KeyError, TypeError, ValueError):
        return False
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=UTC)
    return (now - finished_at).total_seconds() < SNAPSHOT_INTERVAL_SECONDS


def load_positive_routes() -> list[dict[str, int]]:
    """读取并规范化当前集群正数路由，供扫描与消费端对账。"""

    return list(
        CacheRouter.objects.filter(cluster_name=get_cluster().name, strategy_score__gt=0)
        .order_by("strategy_score", "node_id")
        .values("strategy_score", "node_id")
    )


def _routing_digest(positive_routes: list[dict[str, int]]) -> str:
    payload = json.dumps(positive_routes, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


class SnapshotBudgetExceeded(Exception):
    pass


class RedisStrategyCostSnapshotCollector:
    """一次 selfmonitor 收尾调用中，为到期节点生成成本快照。"""

    def __init__(
        self,
        *,
        client_factory=None,
        total_budget_seconds: int = SNAPSHOT_TOTAL_BUDGET_SECONDS,
        monotonic_fn=monotonic,
    ):
        self.client_factory = client_factory or REDIS_STRATEGY_COST_SNAPSHOT_KEY.client.get_client
        self.total_budget_seconds = total_budget_seconds
        self.monotonic = monotonic_fn

    def collect(self, nodes_info: list[tuple[Any, dict[str, Any]]]) -> dict[str, Any]:
        started = self.monotonic()
        deadline = started + self.total_budget_seconds
        now = datetime.now(UTC)
        result = {
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped_fresh": 0,
            "skipped_locked": 0,
            "budget_exhausted": False,
        }
        due: list[tuple[Any, dict[str, Any], StrategyCostSnapshotStore]] = []

        for node, node_info in nodes_info:
            try:
                store = StrategyCostSnapshotStore(node, client=self.client_factory(node))
                if _is_fresh(store.read(1), now):
                    result["skipped_fresh"] += 1
                    continue
                if not store.try_lock(uuid4().hex):
                    result["skipped_locked"] += 1
                    continue
                # 多个 selfmonitor 实例可能同时看到旧快照；锁后必须复查。
                if _is_fresh(store.read(1), now):
                    result["skipped_fresh"] += 1
                    continue
                due.append((node, node_info, store))
            except Exception:
                result["failed"] += 1
                self._record(node, "failed", 0)
                logger.exception("redis strategy cost snapshot precheck failed: node_id=%s", getattr(node, "id", ""))

        if not due:
            return result

        try:
            population, group_index, config_map = self._load_catalog()
            positive_routes = load_positive_routes()
            by_node = self._route_population(population, positive_routes, {node.id for node, _, _ in due})
        except Exception:
            logger.exception("load redis strategy cost snapshot catalog failed")
            for node, _, _ in due:
                result["failed"] += 1
                self._record(node, "failed", 0)
            return result

        for node, node_info, store in due:
            if self.monotonic() >= deadline:
                result["budget_exhausted"] = True
                self._record(node, "budget_exhausted", self.monotonic() - started)
                continue
            result["attempted"] += 1
            node_started = self.monotonic()
            target_strategy_ids = by_node.get(node.id, [])
            target_items = sum(
                len(group_index[strategy_id]["item_ids"])
                for strategy_id in target_strategy_ids
                if strategy_id in group_index
            )
            logger.info(
                "redis strategy cost snapshot started: node_id=%s target_strategies=%s target_items=%s "
                "budget_remaining=%.3fs",
                node.id,
                len(target_strategy_ids),
                target_items,
                max(deadline - node_started, 0),
            )
            try:
                snapshot = self._build_node_snapshot(
                    node,
                    node_info,
                    target_strategy_ids,
                    len(population),
                    group_index,
                    config_map,
                    positive_routes,
                    node_started,
                    deadline,
                )
                self._check_budget(deadline)
                store.save(snapshot)
            except SnapshotBudgetExceeded:
                result["budget_exhausted"] = True
                self._record(node, "budget_exhausted", self.monotonic() - node_started)
                logger.warning("redis strategy cost snapshot ended: node_id=%s status=budget_exhausted", node.id)
                continue
            except Exception:
                result["failed"] += 1
                self._record(node, "failed", self.monotonic() - node_started)
                logger.exception("redis strategy cost snapshot ended: node_id=%s status=failed", node.id)
                continue
            result["succeeded"] += 1
            self._record(node, "success", self.monotonic() - node_started)
            logger.info(
                "redis strategy cost snapshot ended: node_id=%s status=success strategies=%s payload_bytes=%s "
                "db8_config_batches=%s db10_hlen_requested=%s db10_hlen_measured=%s "
                "db10_hlen_failed=%s duration=%.3fs",
                node.id,
                len(snapshot["strategies"]),
                snapshot["snapshot_payload_bytes"],
                snapshot["commands"]["db8"]["config_mget_batches"],
                snapshot["commands"]["db10"]["hlen_requested"],
                snapshot["commands"]["db10"]["hlen_measured"],
                snapshot["commands"]["db10"]["hlen_failed"],
                self.monotonic() - node_started,
            )
        return result

    @staticmethod
    def _load_catalog():
        population = sorted(
            {strategy_id for value in StrategyCacheManager.get_strategy_ids() if (strategy_id := _int_value(value))}
        )
        group_index = _build_group_index(StrategyCacheManager.get_all_groups())
        configs = StrategyCacheManager.get_strategy_by_ids(population) or []
        config_map = {
            strategy_id: config
            for config in configs
            if isinstance(config, dict) and (strategy_id := _int_value(config.get("id"))) is not None
        }
        return population, group_index, config_map

    @staticmethod
    def _route_population(population: list[int], positive_routes: list[dict[str, int]], due_node_ids: set[int]):
        by_node: dict[int, list[int]] = {node_id: [] for node_id in due_node_ids}
        for strategy_id in population:
            node_id = next(
                (route["node_id"] for route in positive_routes if route["strategy_score"] > strategy_id), None
            )
            if node_id in by_node:
                by_node[node_id].append(strategy_id)
        return by_node

    def _build_node_snapshot(
        self,
        node,
        node_info,
        strategy_ids,
        population_total,
        group_index,
        config_map,
        positive_routes,
        started,
        deadline,
    ):
        started_at = datetime.now(UTC)
        client = self.client_factory(node)
        strategies = []
        for strategy_id in strategy_ids:
            self._check_budget(deadline)
            strategies.append(
                self._measure_strategy(
                    node,
                    client,
                    strategy_id,
                    group_index.get(strategy_id),
                    config_map.get(strategy_id),
                    deadline,
                )
            )
        coverage = {
            "population_total": population_total,
            "route_matched": len(strategy_ids),
            "config_resolved": sum(strategy_id in config_map for strategy_id in strategy_ids),
            "group_mapped": sum(strategy_id in group_index for strategy_id in strategy_ids),
            "item_requested": sum(strategy["item_count"] for strategy in strategies),
            "item_measured": sum(strategy["item_measured"] for strategy in strategies),
            "item_failed": sum(strategy["item_failed"] for strategy in strategies),
            "measured": 0,
            "no_group": 0,
            "config_missing": 0,
            "failed": 0,
        }
        for strategy in strategies:
            coverage[strategy["status"]] += 1
        measured = [strategy for strategy in strategies if strategy["status"] == "measured"]
        finished = datetime.now(UTC)
        return {
            "schema_version": 1,
            "snapshot_id": uuid4().hex,
            "started_at": started_at.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": round(self.monotonic() - started, 3),
            "cluster_name": get_cluster().name,
            "node": serialize_cache_node(node),
            "routing": {"positive_routes": positive_routes, "digest": _routing_digest(positive_routes)},
            "node_memory": {
                "used_memory_bytes": node_info.get("used_memory"),
                "maxmemory_bytes": node_info.get("config_maxmemory"),
            },
            "coverage": coverage,
            "commands": {
                "db8": {
                    "scope": "shared_once_per_selfmonitor_call",
                    "population_reads": 1,
                    "group_reads": 1,
                    "config_mget_batches": -(-population_total // 1000),
                },
                "db10": {
                    "snapshot_precheck_reads": 2,
                    "lock_writes": 1,
                    "hlen_requested": coverage["item_requested"],
                    "hlen_measured": coverage["item_measured"],
                    "hlen_failed": coverage["item_failed"],
                    "store_commands": 3,
                },
            },
            "totals": {
                "series_upper_bound": sum(strategy["series_upper_bound"] for strategy in measured),
                "estimated_peak_members": sum(strategy["estimated_peak_members"] for strategy in measured),
            },
            "series_semantics": {
                "checkpoint_fields": "HLEN of detect.last.checkpoint.{strategy_id}.{item_id}",
                "series_upper_bound": "checkpoint fields may include stale series and are an upper bound",
            },
            "strategies": strategies,
        }

    def _measure_strategy(self, node, client, strategy_id, group, config, deadline):
        row: dict[str, Any] = {
            "strategy_id": strategy_id,
            "target_node_id": node.id,
            "bk_biz_id": group.get("bk_biz_id") if group else None,
            "item_count": len(group["item_ids"]) if group else 0,
            "item_measured": 0,
            "item_failed": 0,
            "series_upper_bound": None,
            "estimated_peak_members": None,
        }
        if group is None:
            row["status"] = "no_group"
            return row

        failed = False
        checkpoint_fields = 0
        for item_id in sorted(group["item_ids"]):
            self._check_budget(deadline)
            try:
                checkpoint_fields += int(
                    client.hlen(LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id))
                )
                row["item_measured"] += 1
            except Exception:
                failed = True
                row["item_failed"] += 1
            self._check_budget(deadline)

        if failed:
            row["status"] = "failed"
            row["error_code"] = "redis_read_failed"
            return row

        row["series_upper_bound"] = checkpoint_fields
        if config is None:
            row["status"] = "config_missing"
            return row
        try:
            profile = build_strategy_cost_profile(config)
        except Exception:
            row["status"] = "failed"
            row["error_code"] = "profile_invalid"
            return row
        row["status"] = "measured"
        row["cost_profile"] = profile
        row["estimated_peak_members"] = checkpoint_fields * profile["peak_members_per_series"]
        return row

    def _check_budget(self, deadline: float) -> None:
        if self.monotonic() >= deadline:
            raise SnapshotBudgetExceeded

    @staticmethod
    def _record(node, status: str, duration: float) -> None:
        try:
            from core.prometheus import metrics

            labels = {"cluster_name": get_cluster().name, "node_id": str(getattr(node, "id", "")), "status": status}
            metrics.REDIS_STRATEGY_COST_SNAPSHOT_EXECUTE_COUNT.labels(**labels).inc()
            metrics.REDIS_STRATEGY_COST_SNAPSHOT_DURATION_SECONDS.labels(**labels).observe(duration)
        except Exception:
            logger.debug("record redis strategy cost snapshot metric failed", exc_info=True)
