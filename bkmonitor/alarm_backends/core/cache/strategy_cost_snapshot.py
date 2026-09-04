"""Redis 策略成本快照的节点本地存储与采集逻辑。"""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from datetime import UTC, datetime
from time import monotonic, time
from typing import Any
from uuid import uuid4

import redis
from django.conf import settings
from redis.sentinel import Sentinel, SentinelConnectionPool

from alarm_backends.core.cache.key import (
    LAST_CHECKPOINTS_CACHE_KEY,
    REDIS_STRATEGY_COST_SNAPSHOT_KEY,
    REDIS_STRATEGY_COST_SNAPSHOT_LOCK_KEY,
)
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.item import detect_result_point_required
from alarm_backends.core.control.strategy import Strategy as ControlStrategy
from bkmonitor.models import CacheNode, CacheRouter

SNAPSHOT_HISTORY_LIMIT = 6
SNAPSHOT_INTERVAL_SECONDS = 3600
SNAPSHOT_TOTAL_BUDGET_SECONDS = 20
SNAPSHOT_TOTAL_BUDGET_SECONDS_MIN = 5
SNAPSHOT_TOTAL_BUDGET_SECONDS_MAX = 30
# 与 celery_report_cron 的 collector_interval 对齐：每 30 秒一次采集即一轮。
SNAPSHOT_COLLECT_ROUND_SECONDS = 30
SNAPSHOT_REDIS_SOCKET_TIMEOUT_SECONDS = 1.0
# 大规模分片串行 HLEN 约 1.5ms/条；隔离客户端 socket_timeout=1s，100 条一批留出余量。
SNAPSHOT_HLEN_PIPELINE_SIZE = 100
SNAPSHOT_CONFIG_MGET_SIZE = 1000
CHECK_RESULT_CLEAN_INTERVAL_SECONDS = 7200
GROUP_RESERVED_FIELDS = {"interval_list", "strategy_source", "bk_biz_id"}

logger = logging.getLogger("self_monitor")


class SnapshotBudgetExceeded(Exception):
    pass


class IsolatedSnapshotRedisClient:
    """复制连接参数并限制单次 IO 超时，专供 HLEN 测量；预检与写回不得使用。"""

    def __init__(self, source_client, remaining_seconds: float):
        raw_client = getattr(source_client, "_instance", source_client)
        source_pool = raw_client.connection_pool
        self._sentinel = None

        if isinstance(source_pool, SentinelConnectionPool):
            manager = source_pool.sentinel_manager
            phases = 2 * (len(manager.sentinels) + 1)
            socket_timeout = self._socket_timeout(remaining_seconds, phases)
            sentinel_kwargs = self._bounded_kwargs(manager.sentinel_kwargs, socket_timeout)
            endpoints = [
                (
                    sentinel.connection_pool.connection_kwargs["host"],
                    sentinel.connection_pool.connection_kwargs["port"],
                )
                for sentinel in manager.sentinels
            ]
            data_kwargs = self._bounded_kwargs(source_pool.connection_kwargs, socket_timeout)
            self._sentinel = Sentinel(
                endpoints,
                min_other_sentinels=manager.min_other_sentinels,
                sentinel_kwargs=sentinel_kwargs,
                **data_kwargs,
            )
            self._client = self._sentinel.master_for(source_pool.service_name)
        else:
            phases = 2  # 最坏包含一次 connect 和一次 response read。
            socket_timeout = self._socket_timeout(remaining_seconds, phases)
            kwargs = self._bounded_kwargs(source_pool.connection_kwargs, socket_timeout)
            self._client = redis.Redis(**kwargs)

        self.snapshot_max_io_seconds = phases * socket_timeout

    @staticmethod
    def _socket_timeout(remaining_seconds: float, phases: int) -> float:
        if remaining_seconds <= 0:
            raise SnapshotBudgetExceeded
        return min(SNAPSHOT_REDIS_SOCKET_TIMEOUT_SECONDS, remaining_seconds / phases)

    @staticmethod
    def _bounded_kwargs(source: dict[str, Any], socket_timeout: float) -> dict[str, Any]:
        kwargs = dict(source)
        kwargs.pop("connection_pool", None)
        kwargs.pop("retry", None)
        kwargs.update(
            {
                "socket_timeout": socket_timeout,
                "socket_connect_timeout": socket_timeout,
                "retry_on_timeout": False,
                "retry_on_error": [],
            }
        )
        return kwargs

    @property
    def connection_pool(self):
        return self._client.connection_pool

    def __getattr__(self, name):
        return getattr(self._client, name)

    def close(self) -> None:
        self._client.connection_pool.disconnect()
        if self._sentinel is not None:
            for sentinel in self._sentinel.sentinels:
                sentinel.connection_pool.disconnect()


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

    def release_lock(self, token: str) -> None:
        if not token:
            return
        current = self.client.get(self.lock_key)
        expected = token.encode() if isinstance(current, (bytes, bytearray)) else token
        if current == expected:
            self.client.delete(self.lock_key)

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

    def save(self, snapshot: dict[str, Any], *, before_execute=None) -> None:
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
        if before_execute is not None:
            before_execute()
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


def resolve_snapshot_total_budget_seconds() -> int:
    """命令之间检查的软预算（秒）。

    不能中断正在执行的 Redis 命令；配置值夹在 5–30，不随节点数放大。
    """

    raw = getattr(
        settings, "REDIS_STRATEGY_COST_SNAPSHOT_TOTAL_BUDGET_SECONDS", SNAPSHOT_TOTAL_BUDGET_SECONDS
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = SNAPSHOT_TOTAL_BUDGET_SECONDS
    return min(SNAPSHOT_TOTAL_BUDGET_SECONDS_MAX, max(SNAPSHOT_TOTAL_BUDGET_SECONDS_MIN, value))


def load_positive_routes() -> list[dict[str, int]]:
    """读取并规范化当前集群正数路由，供扫描与消费端对账。"""

    return list(
        CacheRouter.objects.filter(cluster_name=get_cluster().name, strategy_score__gt=0)
        .order_by("strategy_score", "node_id")
        .values("strategy_score", "node_id")
    )


def load_routed_snapshot_node_ids() -> set[int]:
    """只扫描当前集群路由引用节点，并始终包含默认节点。"""

    cluster_name = get_cluster().name
    node_ids = set(
        CacheRouter.objects.filter(cluster_name=cluster_name).values_list("node_id", flat=True)
    )
    node_ids.update(
        CacheNode.objects.filter(cluster_name=cluster_name, is_default=True, is_enable=True).values_list(
            "id", flat=True
        )
    )
    return node_ids


def _routing_digest(positive_routes: list[dict[str, int]]) -> str:
    payload = json.dumps(positive_routes, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{sha256(payload).hexdigest()}"


def snapshot_collect_round_index(now: float | None = None) -> int:
    return int((time() if now is None else now) // SNAPSHOT_COLLECT_ROUND_SECONDS)


def select_round_target(
    nodes_info: list[tuple[Any, dict[str, Any]]],
    routed_ids: set[int],
    round_index: int,
) -> tuple[tuple[Any, dict[str, Any]] | None, int]:
    """按 node_id 排序后取本轮唯一目标。公平性由轮次保证，失败也立刻释放锁。"""

    skipped_unrouted = 0
    candidates: list[tuple[Any, dict[str, Any]]] = []
    for node, node_info in nodes_info:
        if getattr(node, "id", None) not in routed_ids:
            skipped_unrouted += 1
            continue
        candidates.append((node, node_info))
    if not candidates:
        return None, skipped_unrouted
    candidates.sort(key=lambda item: item[0].id)
    return candidates[round_index % len(candidates)], skipped_unrouted


class RedisStrategyCostSnapshotCollector:
    """一次 selfmonitor 收尾调用中，按轮次只尝试一个路由节点生成成本快照。"""

    def __init__(
        self,
        *,
        client_factory=None,
        catalog_client_factory=None,
        total_budget_seconds: int | None = None,
        routed_node_ids: set[int] | None = None,
        round_index: int | None = None,
        monotonic_fn=monotonic,
    ):
        self.client_factory = client_factory
        self.catalog_client_factory = catalog_client_factory
        self.total_budget_seconds = (
            resolve_snapshot_total_budget_seconds() if total_budget_seconds is None else total_budget_seconds
        )
        self.routed_node_ids = routed_node_ids
        self.round_index = round_index
        self.monotonic = monotonic_fn

    def _resolve_round_index(self) -> int:
        if self.round_index is not None:
            return self.round_index
        return snapshot_collect_round_index()

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
            "skipped_unrouted": 0,
            "budget_exhausted": False,
        }
        due: list[tuple[Any, dict[str, Any], StrategyCostSnapshotStore, str]] = []
        try:
            routed_ids = (
                self.routed_node_ids if self.routed_node_ids is not None else load_routed_snapshot_node_ids()
            )
        except Exception:
            logger.exception("load routed snapshot node ids failed")
            result["failed"] += 1
            return result

        target, result["skipped_unrouted"] = select_round_target(
            nodes_info, routed_ids, self._resolve_round_index()
        )
        if target is None:
            return result

        node, node_info = target
        store = None
        token = ""
        try:
            shared_client = self._shared_node_client(node, deadline)
            store = StrategyCostSnapshotStore(node, client=shared_client)
            self._check_io_budget(shared_client, deadline)
            snapshots = store.read(1)
            self._check_budget(deadline)
            if _is_fresh(snapshots, now):
                result["skipped_fresh"] += 1
                return result
            self._check_io_budget(shared_client, deadline)
            token = uuid4().hex
            if not store.try_lock(token):
                result["skipped_locked"] += 1
                return result
            self._check_budget(deadline)
            # 多个 selfmonitor 实例可能同时看到旧快照；锁后必须复查。
            self._check_io_budget(shared_client, deadline)
            snapshots = store.read(1)
            self._check_budget(deadline)
            if _is_fresh(snapshots, now):
                result["skipped_fresh"] += 1
                self._release_lock(store, token)
                return result
            due.append((node, node_info, store, token))
            token = ""
        except SnapshotBudgetExceeded:
            result["budget_exhausted"] = True
            self._record(node, "budget_exhausted", self.monotonic() - started)
            self._release_lock(store, token)
            return result
        except Exception:
            result["failed"] += 1
            self._record(node, "failed", 0)
            self._release_lock(store, token)
            logger.exception("redis strategy cost snapshot precheck failed: node_id=%s", getattr(node, "id", ""))
            return result

        catalog_client = None
        try:
            try:
                catalog_client = self._catalog_client(deadline)
                population, group_index = self._load_catalog(catalog_client, deadline)
                self._check_budget(deadline)
                positive_routes = load_positive_routes()
                self._check_budget(deadline)
                by_node = self._route_population(population, positive_routes, {node.id for node, _, _, _ in due})
            except SnapshotBudgetExceeded:
                result["budget_exhausted"] = True
                for node, _, store, token in due:
                    self._record(node, "budget_exhausted", self.monotonic() - started)
                    self._release_lock(store, token)
                return result
            except Exception:
                logger.exception("load redis strategy cost snapshot catalog failed")
                for node, _, store, token in due:
                    result["failed"] += 1
                    self._record(node, "failed", 0)
                    self._release_lock(store, token)
                return result

            for node, node_info, store, token in due:
                if self.monotonic() >= deadline:
                    result["budget_exhausted"] = True
                    self._record(node, "budget_exhausted", self.monotonic() - started)
                    self._release_lock(store, token)
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
                measure_client = None
                try:
                    measure_client = self._measure_node_client(node, store.client, deadline)
                    snapshot = self._build_node_snapshot(
                        node,
                        node_info,
                        measure_client,
                        catalog_client,
                        target_strategy_ids,
                        len(population),
                        group_index,
                        positive_routes,
                        node_started,
                        deadline,
                    )
                    store.save(snapshot, before_execute=lambda: self._check_io_budget(store.client, deadline))
                    self._check_budget(deadline)
                except SnapshotBudgetExceeded:
                    result["budget_exhausted"] = True
                    self._record(node, "budget_exhausted", self.monotonic() - node_started)
                    logger.warning("redis strategy cost snapshot ended: node_id=%s status=budget_exhausted", node.id)
                except Exception:
                    result["failed"] += 1
                    self._record(node, "failed", self.monotonic() - node_started)
                    logger.exception("redis strategy cost snapshot ended: node_id=%s status=failed", node.id)
                else:
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
                finally:
                    self._close_client(measure_client)
                    self._release_lock(store, token)
        finally:
            self._close_client(catalog_client)
        return result

    def _release_lock(self, store, token: str) -> None:
        if store is None or not token:
            return
        try:
            store.release_lock(token)
        except Exception:
            logger.debug("release redis strategy cost snapshot lock failed", exc_info=True)

    def _load_catalog(self, client, deadline):
        if client is None:
            self._check_budget(deadline)
            raw_population = StrategyCacheManager.get_strategy_ids()
            self._check_budget(deadline)
            raw_groups = StrategyCacheManager.get_all_groups()
            self._check_budget(deadline)
        else:
            raw_population = json.loads(
                self._redis_call(client, deadline, client.get, StrategyCacheManager.IDS_CACHE_KEY) or "[]"
            )
            raw_groups = self._redis_call(
                client, deadline, client.hgetall, StrategyCacheManager.STRATEGY_GROUP_CACHE_KEY
            )

        population = sorted({strategy_id for value in raw_population if (strategy_id := _int_value(value)) is not None})
        return population, _build_group_index(raw_groups)

    def _load_configs(self, client, strategy_ids, deadline):
        if not strategy_ids:
            return {}
        if client is None:
            configs = []
            for offset in range(0, len(strategy_ids), SNAPSHOT_CONFIG_MGET_SIZE):
                self._check_budget(deadline)
                configs.extend(
                    StrategyCacheManager.get_strategy_by_ids(
                        strategy_ids[offset : offset + SNAPSHOT_CONFIG_MGET_SIZE]
                    )
                    or []
                )
                self._check_budget(deadline)
        else:
            keys = [
                StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)
                for strategy_id in strategy_ids
            ]
            raw_configs = []
            for offset in range(0, len(keys), SNAPSHOT_CONFIG_MGET_SIZE):
                raw_configs.extend(
                    self._redis_call(client, deadline, client.mget, keys[offset : offset + SNAPSHOT_CONFIG_MGET_SIZE])
                )
            configs = [json.loads(config) for config in raw_configs if config]
        return {
            strategy_id: config
            for config in configs
            if isinstance(config, dict) and (strategy_id := _int_value(config.get("id"))) is not None
        }

    def _shared_node_client(self, node, deadline):
        if self.client_factory is not None:
            return self.client_factory(node)
        self._check_budget(deadline)
        return REDIS_STRATEGY_COST_SNAPSHOT_KEY.client.get_client(node)

    def _measure_node_client(self, node, shared_client, deadline):
        if self.client_factory is not None:
            return shared_client
        self._check_budget(deadline)
        return IsolatedSnapshotRedisClient(shared_client, deadline - self.monotonic())

    def _catalog_client(self, _deadline):
        # 共享 DB8：软预算不能打断在途命令。目录超时后续单独做，勿复用 HLEN 的 1 秒上限。
        if self.catalog_client_factory is not None:
            return self.catalog_client_factory()
        return None

    def _redis_call(self, client, deadline, command, *args):
        self._check_io_budget(client, deadline)
        value = command(*args)
        self._check_budget(deadline)
        return value

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
        client,
        catalog_client,
        strategy_ids,
        population_total,
        group_index,
        positive_routes,
        started,
        deadline,
    ):
        started_at = datetime.now(UTC)
        pairs = []
        for strategy_id in strategy_ids:
            group = group_index.get(strategy_id)
            if group is None:
                continue
            pairs.extend((strategy_id, item_id) for item_id in sorted(group["item_ids"]))
        hlen_map = dict(zip(pairs, self._pipeline_hlens(client, pairs, deadline))) if pairs else {}

        strategies = []
        config_batches = 0
        resolved_ids: set[int] = set()
        for offset in range(0, len(strategy_ids), SNAPSHOT_CONFIG_MGET_SIZE):
            chunk_ids = strategy_ids[offset : offset + SNAPSHOT_CONFIG_MGET_SIZE]
            config_map = self._load_configs(catalog_client, chunk_ids, deadline)
            config_batches += 1
            resolved_ids.update(config_map)
            for strategy_id in chunk_ids:
                strategies.append(
                    self._measure_strategy(
                        node,
                        strategy_id,
                        group_index.get(strategy_id),
                        config_map.get(strategy_id),
                        hlen_map,
                        deadline,
                    )
                )

        coverage = {
            "population_total": population_total,
            "route_matched": len(strategy_ids),
            "config_resolved": sum(strategy_id in resolved_ids for strategy_id in strategy_ids),
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
                    "scope": "ids_groups_once_configs_due_node",
                    "population_reads": 1,
                    "group_reads": 1,
                    "config_mget_batches": config_batches,
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

    def _pipeline_hlens(self, client, pairs, deadline):
        results = []
        for offset in range(0, len(pairs), SNAPSHOT_HLEN_PIPELINE_SIZE):
            self._check_io_budget(client, deadline)
            batch = pairs[offset : offset + SNAPSHOT_HLEN_PIPELINE_SIZE]
            pipe = client.pipeline(transaction=False)
            for strategy_id, item_id in batch:
                pipe.hlen(LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id))
            try:
                values = pipe.execute(raise_on_error=False)
            except Exception as exc:
                values = [exc] * len(batch)
            if not isinstance(values, list) or len(values) != len(batch):
                values = [RuntimeError("hlen pipeline size mismatch")] * len(batch)
            results.extend(values)
            self._check_budget(deadline)
        return results

    def _measure_strategy(self, node, strategy_id, group, config, hlen_map, deadline):
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
            value = hlen_map.get((strategy_id, item_id), RuntimeError("hlen missing"))
            try:
                if isinstance(value, BaseException):
                    raise value
                checkpoint_fields += int(value)
                row["item_measured"] += 1
            except Exception:
                failed = True
                row["item_failed"] += 1

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
        self._check_budget(deadline)
        row["status"] = "measured"
        row["cost_profile"] = profile
        row["estimated_peak_members"] = checkpoint_fields * profile["peak_members_per_series"]
        return row

    def _check_budget(self, deadline: float) -> None:
        # 软预算：只能拦下一跳命令，不能掐断正在执行的 Redis 调用。
        if self.monotonic() >= deadline:
            raise SnapshotBudgetExceeded

    def _check_io_budget(self, client, deadline: float) -> None:
        self._check_budget(deadline)
        bound = getattr(client, "snapshot_max_io_seconds", 0)
        if not isinstance(bound, (int, float)):
            bound = 0
        if deadline - self.monotonic() <= bound:
            raise SnapshotBudgetExceeded

    @staticmethod
    def _close_client(client) -> None:
        if isinstance(client, IsolatedSnapshotRedisClient):
            try:
                client.close()
            except Exception:
                logger.debug("close isolated redis strategy cost snapshot client failed", exc_info=True)

    @staticmethod
    def _record(node, status: str, duration: float) -> None:
        try:
            from core.prometheus import metrics

            labels = {"cluster_name": get_cluster().name, "node_id": str(getattr(node, "id", "")), "status": status}
            metrics.REDIS_STRATEGY_COST_SNAPSHOT_EXECUTE_COUNT.labels(**labels).inc()
            metrics.REDIS_STRATEGY_COST_SNAPSHOT_DURATION_SECONDS.labels(**labels).observe(duration)
        except Exception:
            logger.debug("record redis strategy cost snapshot metric failed", exc_info=True)
