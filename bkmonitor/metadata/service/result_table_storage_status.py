"""结果表 ES/Doris 存储配置、历史分段和运行时状态查询"""

import json
import logging
from collections import deque
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from threading import BoundedSemaphore, Condition, Lock
from time import monotonic
from typing import Any

from django.db import close_old_connections

from metadata import models
from metadata.service.es_storage import query_es_storage_runtime, serialize_es_runtime_value


# =============================================================================
# 常量与内部类型
# =============================================================================

SUPPORTED_STORAGE_TYPES = {models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS}
MAX_PROBE_WORKERS = 20
MAX_PROBE_WORKERS_PER_CLUSTER = 5
MAX_PROBE_QUEUED_TASKS = 100
MAX_TABLE_QUERY_WORKERS = 20
MAX_TABLE_QUERY_QUEUED_TASKS = 40
MAX_BATCH_TABLE_COUNT = 50
DEFAULT_BATCH_TOTAL_TIMEOUT = 60
MIN_BATCH_TOTAL_TIMEOUT = 1
MAX_BATCH_TOTAL_TIMEOUT = 300
StorageConfig = models.ESStorage | models.DorisStorage

logger = logging.getLogger(__name__)


class SchedulerQueueFullError(Exception):
    """共享调度器在 deadline 前无法接受更多任务。"""


class ClusterProbeScheduler:
    """进程内共享的两级集群探测调度器。"""

    def __init__(self, *, max_workers: int, max_workers_per_cluster: int, max_queued_tasks: int):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="storage-cluster-probe")
        self._max_workers = max_workers
        self._max_workers_per_cluster = max_workers_per_cluster
        self._max_queued_tasks = max_queued_tasks
        self._condition = Condition(Lock())
        self._queues: dict[tuple[str, int], deque[tuple[Future, Any, tuple[Any, ...], dict[str, Any]]]] = {}
        self._ready_keys: deque[tuple[str, int]] = deque()
        self._ready_key_set: set[tuple[str, int]] = set()
        self._active_by_cluster: dict[tuple[str, int], int] = {}
        self._active_total = 0
        self._queued_total = 0

    def submit(
        self,
        cluster_key: tuple[str, int],
        function,
        *args: Any,
        enqueue_timeout: float | None = None,
        **kwargs: Any,
    ) -> Future:
        deadline = monotonic() + enqueue_timeout if enqueue_timeout is not None else None
        with self._condition:
            while self._queued_total >= self._max_queued_tasks:
                remaining = None if deadline is None else deadline - monotonic()
                if remaining is not None and remaining <= 0:
                    raise SchedulerQueueFullError("集群探测队列已满")
                self._condition.wait(timeout=remaining)

            future = Future()
            queue = self._queues.setdefault(cluster_key, deque())
            queue.append((future, function, args, kwargs))
            self._queued_total += 1
            self._mark_ready_locked(cluster_key)
            self._dispatch_locked()
        future.add_done_callback(lambda completed: self._discard_cancelled(cluster_key, completed))
        return future

    def _mark_ready_locked(self, cluster_key: tuple[str, int]) -> None:
        if not self._queues.get(cluster_key):
            return
        if self._active_by_cluster.get(cluster_key, 0) >= self._max_workers_per_cluster:
            return
        if cluster_key not in self._ready_key_set:
            self._ready_keys.append(cluster_key)
            self._ready_key_set.add(cluster_key)

    def _dispatch_locked(self) -> None:
        while self._active_total < self._max_workers and self._ready_keys:
            cluster_key = self._ready_keys.popleft()
            self._ready_key_set.remove(cluster_key)
            queue = self._queues.get(cluster_key)
            if not queue:
                continue

            future, function, args, kwargs = queue.popleft()
            self._queued_total -= 1
            if not queue:
                del self._queues[cluster_key]

            if future.cancelled():
                self._condition.notify_all()
                self._mark_ready_locked(cluster_key)
                continue

            self._active_total += 1
            self._active_by_cluster[cluster_key] = self._active_by_cluster.get(cluster_key, 0) + 1
            self._mark_ready_locked(cluster_key)
            self._condition.notify_all()
            self._executor.submit(self._run_task, cluster_key, future, function, args, kwargs)

    def _run_task(
        self,
        cluster_key: tuple[str, int],
        future: Future,
        function,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        try:
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(function(*args, **kwargs))
                except BaseException as error:  # 与 concurrent.futures.Executor 的异常传递语义保持一致
                    future.set_exception(error)
        finally:
            with self._condition:
                self._active_total -= 1
                active = self._active_by_cluster[cluster_key] - 1
                if active:
                    self._active_by_cluster[cluster_key] = active
                else:
                    del self._active_by_cluster[cluster_key]
                self._mark_ready_locked(cluster_key)
                self._dispatch_locked()
                self._condition.notify_all()

    def _discard_cancelled(self, cluster_key: tuple[str, int], future: Future) -> None:
        if not future.cancelled():
            return
        with self._condition:
            queue = self._queues.get(cluster_key)
            if not queue:
                return
            for task in queue:
                if task[0] is future:
                    queue.remove(task)
                    self._queued_total -= 1
                    if not queue:
                        del self._queues[cluster_key]
                        if cluster_key in self._ready_key_set:
                            self._ready_key_set.remove(cluster_key)
                            self._ready_keys.remove(cluster_key)
                    self._condition.notify_all()
                    return

    def shutdown(self, wait_for_tasks: bool = True) -> None:
        """仅供独立调度器测试或进程退出时显式清理。"""

        self._executor.shutdown(wait=wait_for_tasks)


class BoundedExecutor:
    """进程内共享且有界的线程池。"""

    def __init__(self, *, max_workers: int, max_queued_tasks: int, thread_name_prefix: str):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)
        self._capacity = BoundedSemaphore(max_workers + max_queued_tasks)

    def submit(self, function, *args: Any, enqueue_timeout: float | None = None, **kwargs: Any) -> Future:
        if not self._capacity.acquire(timeout=enqueue_timeout):
            raise SchedulerQueueFullError("结果表查询队列已满")
        try:
            future = self._executor.submit(function, *args, **kwargs)
        except BaseException:
            self._capacity.release()
            raise
        future.add_done_callback(lambda _: self._capacity.release())
        return future

    def shutdown(self, wait_for_tasks: bool = True) -> None:
        self._executor.shutdown(wait=wait_for_tasks)


shared_cluster_probe_scheduler = ClusterProbeScheduler(
    max_workers=MAX_PROBE_WORKERS,
    max_workers_per_cluster=MAX_PROBE_WORKERS_PER_CLUSTER,
    max_queued_tasks=MAX_PROBE_QUEUED_TASKS,
)
shared_table_query_executor = BoundedExecutor(
    max_workers=MAX_TABLE_QUERY_WORKERS,
    max_queued_tasks=MAX_TABLE_QUERY_QUEUED_TASKS,
    thread_name_prefix="storage-table-query",
)


@dataclass(frozen=True)
class StorageProbeTarget:
    """单个唯一存储集群的探测上下文"""

    cluster_id: int
    cluster: models.ClusterInfo | None
    has_current_segment: bool
    is_configured_current: bool
    has_historical_segment: bool


@dataclass
class StorageSegmentState:
    """单个集群在历史分段中的聚合状态"""

    has_current: bool = False
    has_historical: bool = False


@dataclass
class StorageConfigs:
    """结果表按存储类型区分的配置，保留键与具体模型类型的对应关系"""

    es: models.ESStorage | None
    doris: models.DorisStorage | None

    def values(self) -> tuple[StorageConfig | None, StorageConfig | None]:
        return self.es, self.doris


@dataclass(frozen=True)
class StorageProbeBatch:
    """一次查询需要返回的历史分段和待探测集群"""

    segments: list[dict[str, Any]]
    targets: list[StorageProbeTarget]


# =============================================================================
# 通用响应与序列化
# =============================================================================


def _serialize_datetime(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _error(code: str, message: str, **details: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "message": message}
    if details:
        item["details"] = details
    return item


def _warning(code: str, message: str, **details: Any) -> dict[str, Any]:
    return _error(code, message, **details)


def _load_json_config(value: Any, field_name: str, table_id: str, warnings: list[dict[str, Any]]) -> Any:
    if value in (None, "") or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as error:
        warnings.append(
            _warning(
                "STORAGE_JSON_PARSE_FAILED",
                f"{field_name} 不是合法 JSON，已返回原始值",
                table_id=table_id,
                field=field_name,
                error=str(error),
            )
        )
        return value


def _serialize_result_table(result_table: models.ResultTable) -> dict[str, Any]:
    return {
        "table_id": result_table.table_id,
        "bk_tenant_id": result_table.bk_tenant_id,
        "table_name_zh": result_table.table_name_zh,
        "bk_biz_id": result_table.bk_biz_id,
        "data_label": result_table.data_label,
        "default_storage": result_table.default_storage,
        "is_enable": result_table.is_enable,
        "is_deleted": result_table.is_deleted,
    }


def _serialize_cluster(cluster: models.ClusterInfo | None) -> dict[str, Any] | None:
    if cluster is None:
        return None
    return {
        "cluster_id": cluster.cluster_id,
        "cluster_name": cluster.cluster_name,
        "display_name": cluster.display_name,
        "cluster_type": cluster.cluster_type,
        "domain_name": cluster.domain_name,
        "port": cluster.port,
        "version": cluster.version,
        "schema": cluster.schema,
    }


def _serialize_es_storage(storage: models.ESStorage, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    json_fields = {"index_settings", "mapping_settings", "warm_phase_settings", "long_term_storage_settings"}
    fields = (
        "table_id",
        "origin_table_id",
        "bk_tenant_id",
        "storage_cluster_id",
        "date_format",
        "slice_size",
        "slice_gap",
        "retention",
        "warm_phase_days",
        "time_zone",
        "source_type",
        "index_set",
        "need_create_index",
        "archive_index_days",
        "index_settings",
        "mapping_settings",
        "warm_phase_settings",
        "long_term_storage_settings",
    )
    result = {field: getattr(storage, field, None) for field in fields}
    for field in json_fields:
        result[field] = _load_json_config(result.get(field), field, storage.table_id, warnings)
    result["effective_table_id"] = storage.origin_table_id or storage.table_id
    return result


def _serialize_doris_storage(storage: models.DorisStorage, warnings: list[dict[str, Any]]) -> dict[str, Any]:
    result = {
        "table_id": storage.table_id,
        "origin_table_id": storage.origin_table_id,
        "bk_tenant_id": storage.bk_tenant_id,
        "bkbase_table_id": storage.bkbase_table_id,
        "source_type": storage.source_type,
        "index_set": storage.index_set,
        "table_type": storage.table_type,
        "field_config_mapping": _load_json_config(
            storage.field_config_mapping, "field_config_mapping", storage.table_id, warnings
        ),
        "expire_days": storage.expire_days,
        "storage_cluster_id": storage.storage_cluster_id,
        "effective_table_id": storage.origin_table_id or storage.table_id,
    }
    return result


def _serialize_segment(record: models.StorageClusterRecord, cluster: models.ClusterInfo | None) -> dict[str, Any]:
    return {
        "id": record.pk,
        "table_id": record.table_id,
        "cluster_id": record.cluster_id,
        "storage_type": cluster.cluster_type if cluster is not None else "unknown",
        "is_current": record.is_current,
        "is_deleted": record.is_deleted,
        "creator": record.creator,
        "create_time": _serialize_datetime(record.create_time),
        "enable_time": _serialize_datetime(record.enable_time),
        "disable_time": _serialize_datetime(record.disable_time),
        "delete_time": _serialize_datetime(record.delete_time),
    }


# =============================================================================
# 元数据加载
# =============================================================================


def _resolve_history_table_id(
    table_id: str,
    storages: StorageConfigs,
    errors: list[dict[str, Any]],
) -> str | None:
    origin_table_ids = {storage.origin_table_id for storage in storages.values() if storage and storage.origin_table_id}
    if len(origin_table_ids) > 1:
        errors.append(
            _error(
                "STORAGE_ORIGIN_TABLE_CONFLICT",
                "ESStorage 与 DorisStorage 指向不同实体表，无法确定唯一历史表",
                table_id=table_id,
                origin_table_ids=sorted(origin_table_ids),
            )
        )
        return None
    return next(iter(origin_table_ids), table_id)


# =============================================================================
# Doris 运行时投影
# =============================================================================


def _mapping_value(row: Any, *keys: str) -> Any:
    if not isinstance(row, Mapping):
        return None
    normalized = {str(key).lower(): value for key, value in row.items()}
    return next((normalized[key.lower()] for key in keys if key.lower() in normalized), None)


def _compact_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: serialize_es_runtime_value(value) for key, value in mapping.items() if value is not None}


def _as_mapping(value: Any) -> Mapping[Any, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _serialize_doris_table(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    return _compact_mapping(
        {
            "schema": _mapping_value(row, "TABLE_SCHEMA", "table_schema"),
            "name": _mapping_value(row, "TABLE_NAME", "table_name"),
            "type": _mapping_value(row, "TABLE_TYPE", "table_type"),
            "engine": _mapping_value(row, "ENGINE", "engine"),
            "rows": _mapping_value(row, "TABLE_ROWS", "table_rows"),
            "data_length_bytes": _mapping_value(row, "DATA_LENGTH", "data_length"),
            "index_length_bytes": _mapping_value(row, "INDEX_LENGTH", "index_length"),
            "create_time": _mapping_value(row, "CREATE_TIME", "create_time"),
            "update_time": _mapping_value(row, "UPDATE_TIME", "update_time"),
            "collation": _mapping_value(row, "TABLE_COLLATION", "table_collation"),
            "comment": _mapping_value(row, "TABLE_COMMENT", "table_comment"),
        }
    )


def _serialize_doris_column(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    nullable = _mapping_value(row, "IS_NULLABLE", "is_nullable")
    return _compact_mapping(
        {
            "name": _mapping_value(row, "COLUMN_NAME", "column_name"),
            "position": _mapping_value(row, "ORDINAL_POSITION", "ordinal_position"),
            "is_nullable": str(nullable).upper() == "YES" if nullable is not None else None,
            "data_type": _mapping_value(row, "DATA_TYPE", "data_type"),
            "column_type": _mapping_value(row, "COLUMN_TYPE", "column_type"),
            "key": _mapping_value(row, "COLUMN_KEY", "column_key"),
            "default": _mapping_value(row, "COLUMN_DEFAULT", "column_default"),
            "extra": _mapping_value(row, "EXTRA", "extra"),
            "character_set": _mapping_value(row, "CHARACTER_SET_NAME", "character_set_name"),
            "collation": _mapping_value(row, "COLLATION_NAME", "collation_name"),
            "comment": _mapping_value(row, "COLUMN_COMMENT", "column_comment"),
        }
    )


def _serialize_doris_partition(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        return None
    return _compact_mapping(
        {
            "name": _mapping_value(row, "PARTITION_NAME", "partition_name"),
            "position": _mapping_value(row, "PARTITION_ORDINAL_POSITION", "partition_ordinal_position"),
            "method": _mapping_value(row, "PARTITION_METHOD", "partition_method"),
            "expression": _mapping_value(row, "PARTITION_EXPRESSION", "partition_expression"),
            "description": _mapping_value(row, "PARTITION_DESCRIPTION", "partition_description"),
            "rows": _mapping_value(row, "TABLE_ROWS", "table_rows"),
            "data_length_bytes": _mapping_value(row, "DATA_LENGTH", "data_length"),
            "index_length_bytes": _mapping_value(row, "INDEX_LENGTH", "index_length"),
            "create_time": _mapping_value(row, "CREATE_TIME", "create_time"),
            "update_time": _mapping_value(row, "UPDATE_TIME", "update_time"),
        }
    )


def build_doris_storage_runtime(
    raw_runtime: Any,
    *,
    connection_cluster_id: int | None = None,
    is_historical_cluster: bool = False,
) -> dict[str, Any]:
    """将 DorisBinding/information_schema 原始结果投影为稳定的关键字段"""

    raw_runtime = _as_mapping(raw_runtime)
    binding = _as_mapping(raw_runtime.get("doris_binding"))
    binding_status = _as_mapping(binding.get("status"))
    physical_metadata = _as_mapping(raw_runtime.get("physical_metadata"))
    table_rows = _as_list(physical_metadata.get("tables"))
    column_rows = _as_list(physical_metadata.get("columns"))
    partition_rows = _as_list(physical_metadata.get("partitions"))

    return {
        "request_table_id": raw_runtime.get("request_table_id"),
        "metadata_context": {
            "connection_cluster_id": connection_cluster_id,
            "is_historical_cluster": is_historical_cluster,
            "binding_source": "current_doris_binding",
            "historical_binding_snapshot_available": False,
        },
        "binding": _compact_mapping(
            {
                "name": binding.get("name"),
                "namespace": binding.get("namespace"),
                "phase": _mapping_value(binding_status, "phase"),
                "message": _mapping_value(binding_status, "message"),
                "physical_table_name": binding.get("physical_table_name"),
                "physical_table_name_source": binding.get("physical_table_name_source"),
            }
        ),
        "table": _serialize_doris_table(table_rows[0]) if table_rows else None,
        "columns": [item for row in column_rows if (item := _serialize_doris_column(row)) is not None],
        "partitions": [item for row in partition_rows if (item := _serialize_doris_partition(row)) is not None],
    }


# =============================================================================
# 查询与集群探测
# =============================================================================


class ResultTableStorageStatusService:
    """查询结果表关联 ES/Doris 存储的配置、历史分段与运行时状态"""

    def __init__(
        self,
        *,
        bk_tenant_id: str,
        table_id: str,
        timeout: int = 15,
        deadline_at: float | None = None,
    ):
        self.bk_tenant_id = bk_tenant_id
        self.table_id = table_id
        self.timeout = timeout
        self.deadline_at = deadline_at

    # -------------------------------------------------------------------------
    # 查询编排与元数据准备
    # -------------------------------------------------------------------------

    def query(self) -> dict[str, Any]:
        """加载元数据、准备探测目标并组装部分成功响应"""

        try:
            result_table = models.ResultTable.objects.get(bk_tenant_id=self.bk_tenant_id, table_id=self.table_id)
        except models.ResultTable.DoesNotExist as error:
            raise ValueError(f"结果表不存在: table_id={self.table_id}") from error

        warnings: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        storages, history_table_id = self._load_storage_configs(warnings, errors)
        probe_batch = self._prepare_probe_batch(history_table_id, storages, warnings)
        cluster_results = self._probe_targets(probe_batch.targets, storages)
        return self._build_response(
            result_table=result_table,
            history_table_id=history_table_id,
            storages=storages,
            probe_batch=probe_batch,
            cluster_results=cluster_results,
            warnings=warnings,
            errors=errors,
        )

    def _load_storage_configs(
        self,
        warnings: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> tuple[StorageConfigs, str | None]:
        """加载请求 RT 配置，并在虚拟 RT 缺少配置时补充实体表配置"""

        storages = StorageConfigs(
            es=models.ESStorage.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id=self.table_id,
            ).first(),
            doris=models.DorisStorage.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id=self.table_id,
            ).first(),
        )
        history_table_id = _resolve_history_table_id(self.table_id, storages, errors)
        if history_table_id is not None and history_table_id != self.table_id:
            if storages.es is None:
                storages.es = models.ESStorage.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    table_id=history_table_id,
                ).first()
                self._append_effective_storage_warning(
                    storages.es,
                    history_table_id=history_table_id,
                    storage_type=models.ClusterInfo.TYPE_ES,
                    warnings=warnings,
                )
            if storages.doris is None:
                storages.doris = models.DorisStorage.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    table_id=history_table_id,
                ).first()
                self._append_effective_storage_warning(
                    storages.doris,
                    history_table_id=history_table_id,
                    storage_type=models.ClusterInfo.TYPE_DORIS,
                    warnings=warnings,
                )
        if not any(storages.values()):
            errors.append(
                _error(
                    "SUPPORTED_STORAGE_CONFIG_NOT_FOUND",
                    "结果表没有可用的 ESStorage 或 DorisStorage 配置",
                    table_id=self.table_id,
                )
            )
        return storages, history_table_id

    def _append_effective_storage_warning(
        self,
        storage: StorageConfig | None,
        *,
        history_table_id: str,
        storage_type: str,
        warnings: list[dict[str, Any]],
    ) -> None:
        if storage is None:
            return
        warnings.append(
            _warning(
                "EFFECTIVE_STORAGE_CONFIG_USED",
                "虚拟结果表缺少对应类型配置，历史探测使用实体表 Storage 配置",
                table_id=self.table_id,
                effective_table_id=history_table_id,
                storage_type=storage_type,
            )
        )

    def _prepare_probe_batch(
        self,
        history_table_id: str | None,
        storages: StorageConfigs,
        warnings: list[dict[str, Any]],
    ) -> StorageProbeBatch:
        """按历史首次出现顺序构造 segments 和唯一集群探测目标"""

        records = (
            list(
                models.StorageClusterRecord.objects.filter(
                    bk_tenant_id=self.bk_tenant_id,
                    table_id=history_table_id,
                ).order_by("enable_time", "create_time", "id")
            )
            if history_table_id is not None
            else []
        )
        ordered_cluster_ids, segment_states = self._aggregate_segment_states(records)
        configured_cluster_id_list = [
            storage.storage_cluster_id for storage in storages.values() if storage is not None
        ]
        configured_cluster_ids = set(configured_cluster_id_list)
        if history_table_id is not None:
            seen_cluster_ids = set(ordered_cluster_ids)
            for cluster_id in configured_cluster_id_list:
                if cluster_id in seen_cluster_ids:
                    continue
                seen_cluster_ids.add(cluster_id)
                ordered_cluster_ids.append(cluster_id)

        cluster_map = {
            cluster.cluster_id: cluster
            for cluster in models.ClusterInfo.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                cluster_id__in=ordered_cluster_ids,
            )
        }
        self._append_missing_segment_warnings(history_table_id, storages, segment_states, warnings)
        return StorageProbeBatch(
            segments=[_serialize_segment(record, cluster_map.get(record.cluster_id)) for record in records],
            targets=[
                self._build_target(cluster_id, segment_states, cluster_map, configured_cluster_ids)
                for cluster_id in ordered_cluster_ids
            ],
        )

    @staticmethod
    def _aggregate_segment_states(
        records: list[models.StorageClusterRecord],
    ) -> tuple[list[int], dict[int, StorageSegmentState]]:
        ordered_cluster_ids: list[int] = []
        segment_states: dict[int, StorageSegmentState] = {}
        for record in records:
            state = segment_states.get(record.cluster_id)
            if state is None:
                state = StorageSegmentState()
                segment_states[record.cluster_id] = state
                ordered_cluster_ids.append(record.cluster_id)
            if record.is_current:
                state.has_current = True
            else:
                state.has_historical = True
        return ordered_cluster_ids, segment_states

    def _append_missing_segment_warnings(
        self,
        history_table_id: str | None,
        storages: StorageConfigs,
        segment_states: Mapping[int, StorageSegmentState],
        warnings: list[dict[str, Any]],
    ) -> None:
        if history_table_id is None:
            return
        for storage_type, storage in (
            (models.ClusterInfo.TYPE_ES, storages.es),
            (models.ClusterInfo.TYPE_DORIS, storages.doris),
        ):
            if storage is None or storage.storage_cluster_id in segment_states:
                continue
            warnings.append(
                _warning(
                    "STORAGE_CLUSTER_RECORD_MISSING",
                    "存储配置指向的集群没有对应历史分段，仍会执行一次探测",
                    table_id=self.table_id,
                    storage_type=storage_type,
                    cluster_id=storage.storage_cluster_id,
                )
            )

    @staticmethod
    def _build_response(
        *,
        result_table: models.ResultTable,
        history_table_id: str | None,
        storages: StorageConfigs,
        probe_batch: StorageProbeBatch,
        cluster_results: dict[str, dict[str, Any]],
        warnings: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "result_table": _serialize_result_table(result_table),
            "history_table_id": history_table_id,
            "storage_configs": {
                models.ClusterInfo.TYPE_ES: (
                    _serialize_es_storage(storages.es, warnings) if storages.es is not None else None
                ),
                models.ClusterInfo.TYPE_DORIS: (
                    _serialize_doris_storage(storages.doris, warnings) if storages.doris is not None else None
                ),
            },
            "segments": probe_batch.segments,
            "cluster_results": cluster_results,
            "warnings": warnings,
            "errors": errors,
        }

    @staticmethod
    def _build_target(
        cluster_id: int,
        segment_states: Mapping[int, StorageSegmentState],
        cluster_map: dict[int, models.ClusterInfo],
        configured_cluster_ids: set[int],
    ) -> StorageProbeTarget:
        segment_state = segment_states.get(cluster_id)
        return StorageProbeTarget(
            cluster_id=cluster_id,
            cluster=cluster_map.get(cluster_id),
            has_current_segment=segment_state.has_current if segment_state else False,
            is_configured_current=cluster_id in configured_cluster_ids,
            has_historical_segment=segment_state.has_historical if segment_state else False,
        )

    # -------------------------------------------------------------------------
    # 并发探测与后端查询
    # -------------------------------------------------------------------------

    def _probe_targets(
        self,
        targets: list[StorageProbeTarget],
        storages: StorageConfigs,
    ) -> dict[str, dict[str, Any]]:
        if not targets:
            return {}
        results: dict[int, dict[str, Any]] = {}
        future_map: dict[Future, StorageProbeTarget] = {}
        for target in targets:
            remaining = self._remaining_deadline()
            if remaining is not None and remaining <= 0:
                results[target.cluster_id] = self._build_probe_error_result(
                    target,
                    "BATCH_DEADLINE_EXCEEDED",
                    "批量查询已超过总时间限制，未启动集群探测",
                )
                continue
            try:
                future = shared_cluster_probe_scheduler.submit(
                    (self.bk_tenant_id, target.cluster_id),
                    self._probe_target,
                    target,
                    storages,
                    enqueue_timeout=remaining,
                )
            except SchedulerQueueFullError:
                results[target.cluster_id] = self._build_probe_error_result(
                    target,
                    "STORAGE_PROBE_QUEUE_TIMEOUT",
                    "集群探测队列繁忙，未能在批次总时间内提交任务",
                )
                continue
            future_map[future] = target

        pending = set(future_map)
        while pending:
            remaining = self._remaining_deadline()
            if remaining is not None and remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                target = future_map[future]
                try:
                    results[target.cluster_id] = future.result()
                except Exception as error:  # pylint: disable=broad-except
                    results[target.cluster_id] = self._build_probe_error_result(
                        target,
                        "STORAGE_PROBE_UNEXPECTED_ERROR",
                        "存储集群探测发生未预期异常",
                        error=str(error),
                    )

        for future in pending:
            future.cancel()
            target = future_map[future]
            results[target.cluster_id] = self._build_probe_error_result(
                target,
                "BATCH_DEADLINE_EXCEEDED",
                "批量查询已超过总时间限制，集群探测已取消或停止等待",
            )
        return {str(target.cluster_id): results[target.cluster_id] for target in targets}

    def _remaining_deadline(self) -> float | None:
        if self.deadline_at is None:
            return None
        return self.deadline_at - monotonic()

    def _deadline_exceeded(self) -> bool:
        remaining = self._remaining_deadline()
        return remaining is not None and remaining <= 0

    def _build_probe_error_result(
        self,
        target: StorageProbeTarget,
        code: str,
        message: str,
        **details: Any,
    ) -> dict[str, Any]:
        result = self._build_probe_result(target, [], [])
        result["runtime_skipped"] = True
        result["errors"].append(_error(code, message, cluster_id=target.cluster_id, **details))
        return result

    def _probe_target(
        self,
        target: StorageProbeTarget,
        storages: StorageConfigs,
    ) -> dict[str, Any]:
        close_old_connections()
        try:
            return self._do_probe_target(target, storages)
        finally:
            close_old_connections()

    def _do_probe_target(
        self,
        target: StorageProbeTarget,
        storages: StorageConfigs,
    ) -> dict[str, Any]:
        warnings: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        result = self._build_probe_result(target, warnings, errors)
        if self._deadline_exceeded():
            self._skip_runtime(
                result,
                errors,
                _error(
                    "BATCH_DEADLINE_EXCEEDED",
                    "批量查询已超过总时间限制，未启动集群探测",
                    cluster_id=target.cluster_id,
                ),
            )
            return result
        if target.has_historical_segment:
            warnings.append(
                _warning(
                    "HISTORICAL_CONFIG_NOT_SNAPSHOTTED",
                    "历史分段未保存当时的存储配置，运行时查询使用当前 Storage 配置",
                    cluster_id=target.cluster_id,
                )
            )

        cluster = self._validate_probe_target(target, result, errors)
        if cluster is None:
            return result
        if self._deadline_exceeded():
            self._skip_runtime(
                result,
                errors,
                _error(
                    "BATCH_DEADLINE_EXCEEDED",
                    "集群连通性检查完成时批量查询已超时，跳过运行时查询",
                    cluster_id=target.cluster_id,
                ),
            )
            return result
        if cluster.cluster_type == models.ClusterInfo.TYPE_ES:
            self._probe_es_runtime(target, cluster, storages.es, result, warnings, errors)
        else:
            self._probe_doris_runtime(target, cluster, storages.doris, result, warnings, errors)
        return result

    @staticmethod
    def _build_probe_result(
        target: StorageProbeTarget,
        warnings: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cluster = target.cluster
        return {
            "storage_type": cluster.cluster_type if cluster is not None else "unknown",
            "is_current": target.has_current_segment or target.is_configured_current,
            "is_current_segment": target.has_current_segment,
            "is_configured_current": target.is_configured_current,
            "cluster": _serialize_cluster(cluster),
            "connectivity": None,
            "runtime": None,
            "runtime_skipped": False,
            "config_source": "current_storage_config",
            "warnings": warnings,
            "errors": errors,
        }

    def _validate_probe_target(
        self,
        target: StorageProbeTarget,
        result: dict[str, Any],
        errors: list[dict[str, Any]],
    ) -> models.ClusterInfo | None:
        """校验集群并执行轻量连通性检查；不可探测时统一标记 runtime_skipped"""

        cluster = target.cluster
        if cluster is None:
            self._skip_runtime(
                result,
                errors,
                _error(
                    "STORAGE_CLUSTER_NOT_FOUND",
                    "历史分段或存储配置关联的 ClusterInfo 不存在",
                    cluster_id=target.cluster_id,
                ),
            )
            return None
        if cluster.cluster_type not in SUPPORTED_STORAGE_TYPES:
            self._skip_runtime(
                result,
                errors,
                _error(
                    "STORAGE_TYPE_UNSUPPORTED",
                    "仅支持探测 ES 和 Doris 历史集群",
                    cluster_id=target.cluster_id,
                    storage_type=cluster.cluster_type,
                ),
            )
            return None

        connectivity = cluster.check_connectivity(timeout=self.timeout)
        result["connectivity"] = serialize_es_runtime_value(connectivity)
        if not connectivity.get("is_connected", False):
            self._skip_runtime(
                result,
                errors,
                _error(
                    "STORAGE_CONNECTIVITY_CHECK_FAILED",
                    "存储集群连接失败，已跳过运行时查询",
                    cluster_id=target.cluster_id,
                    connection_error=connectivity.get("error"),
                ),
            )
            return None
        return cluster

    def _probe_es_runtime(
        self,
        target: StorageProbeTarget,
        cluster: models.ClusterInfo,
        storage: models.ESStorage | None,
        result: dict[str, Any],
        warnings: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> None:
        if storage is None:
            self._skip_runtime(
                result,
                errors,
                _error(
                    "STORAGE_CONFIG_NOT_FOUND",
                    "历史集群存在但结果表缺少对应类型的 Storage 配置",
                    cluster_id=target.cluster_id,
                    storage_type=models.ClusterInfo.TYPE_ES,
                ),
            )
            return

        runtime, runtime_warnings = query_es_storage_runtime(
            es_storage=storage,
            bk_tenant_id=self.bk_tenant_id,
            runtime_cluster=cluster,
            includes={"indices", "aliases"},
            timeout=self.timeout,
        )
        result["runtime"] = runtime
        for item in runtime_warnings:
            if item.get("code") == "RUNTIME_QUERY_FAILED":
                errors.append(item)
            else:
                warnings.append(item)

    def _probe_doris_runtime(
        self,
        target: StorageProbeTarget,
        cluster: models.ClusterInfo,
        storage: models.DorisStorage | None,
        result: dict[str, Any],
        warnings: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> None:
        if storage is None:
            self._skip_runtime(
                result,
                errors,
                _error(
                    "STORAGE_CONFIG_NOT_FOUND",
                    "历史集群存在但结果表缺少对应类型的 Storage 配置",
                    cluster_id=target.cluster_id,
                    storage_type=models.ClusterInfo.TYPE_DORIS,
                ),
            )
            return

        is_historical_cluster = not target.is_configured_current
        if is_historical_cluster:
            warnings.append(
                _warning(
                    "HISTORICAL_DORIS_BINDING_NOT_SNAPSHOTTED",
                    "仅连接信息切换到历史 Doris 集群；DorisBinding 和物理库表名仍来自当前配置，"
                    "查询结果可能为空或指向不同物理表",
                    cluster_id=target.cluster_id,
                )
            )

        raw_runtime = storage.query_physical_storage_metadata(
            storage_cluster_id=cluster.cluster_id,
            timeout=self.timeout,
            include_create_table=False,
        )
        raw_runtime = serialize_es_runtime_value(raw_runtime)
        warnings.extend(raw_runtime.get("warnings", []))
        errors.extend(raw_runtime.get("errors", []))
        result["runtime"] = build_doris_storage_runtime(
            raw_runtime,
            connection_cluster_id=cluster.cluster_id,
            is_historical_cluster=is_historical_cluster,
        )

    @staticmethod
    def _skip_runtime(
        result: dict[str, Any],
        errors: list[dict[str, Any]],
        error: dict[str, Any],
    ) -> None:
        errors.append(error)
        result["runtime_skipped"] = True


class ResultTableStorageStatusBatchService:
    """批量查询结果表存储状态，保持输入顺序并隔离单表失败。"""

    def __init__(
        self,
        *,
        bk_tenant_id: str,
        table_ids: list[str],
        timeout: int = 15,
        total_timeout: int = DEFAULT_BATCH_TOTAL_TIMEOUT,
    ):
        if not table_ids or len(table_ids) > MAX_BATCH_TABLE_COUNT:
            raise ValueError(f"table_ids 数量必须在 1 到 {MAX_BATCH_TABLE_COUNT} 之间")
        if len(table_ids) != len(set(table_ids)):
            raise ValueError("table_ids 不能包含重复项")
        if not MIN_BATCH_TOTAL_TIMEOUT <= total_timeout <= MAX_BATCH_TOTAL_TIMEOUT:
            raise ValueError(f"total_timeout 必须在 {MIN_BATCH_TOTAL_TIMEOUT} 到 {MAX_BATCH_TOTAL_TIMEOUT} 秒之间")
        self.bk_tenant_id = bk_tenant_id
        self.table_ids = table_ids
        self.timeout = timeout
        self.total_timeout = total_timeout

    def query(self) -> dict[str, Any]:
        results: dict[str, dict[str, Any]] = {}
        deadline_at = monotonic() + self.total_timeout
        future_map: dict[Future, str] = {}
        submitted_count = 0

        for table_id in self.table_ids:
            remaining = deadline_at - monotonic()
            if remaining <= 0:
                break
            try:
                future = shared_table_query_executor.submit(
                    self._query_table,
                    table_id,
                    deadline_at,
                    enqueue_timeout=remaining,
                )
            except SchedulerQueueFullError:
                break
            future_map[future] = table_id
            submitted_count += 1

        remaining = max(0.0, deadline_at - monotonic())
        done, pending = wait(future_map, timeout=remaining)
        for future in done:
            table_id = future_map[future]
            try:
                results[table_id] = future.result()
            except Exception as error:  # pylint: disable=broad-except
                logger.exception("query result table storage status future failed, table_id->[%s]", table_id)
                results[table_id] = self._build_query_error(table_id, error)

        for future in pending:
            future.cancel()
            table_id = future_map[future]
            results[table_id] = self._build_deadline_error(table_id)

        for table_id in self.table_ids[submitted_count:]:
            results[table_id] = self._build_deadline_error(table_id)
        return {"items": [results[table_id] for table_id in self.table_ids]}

    def _query_table(self, table_id: str, deadline_at: float) -> dict[str, Any]:
        close_old_connections()
        try:
            if monotonic() >= deadline_at:
                return self._build_deadline_error(table_id)
            data = ResultTableStorageStatusService(
                bk_tenant_id=self.bk_tenant_id,
                table_id=table_id,
                timeout=self.timeout,
                deadline_at=deadline_at,
            ).query()
            return {"table_id": table_id, "data": data, "error": None}
        except ValueError as error:
            return {
                "table_id": table_id,
                "data": None,
                "error": _error("RESULT_TABLE_NOT_FOUND", str(error), table_id=table_id),
            }
        except Exception as error:  # pylint: disable=broad-except
            logger.exception("query result table storage status failed, table_id->[%s]", table_id)
            return self._build_query_error(table_id, error)
        finally:
            close_old_connections()

    @staticmethod
    def _build_query_error(table_id: str, error: Exception) -> dict[str, Any]:
        return {
            "table_id": table_id,
            "data": None,
            "error": _error(
                "RESULT_TABLE_STORAGE_STATUS_QUERY_FAILED",
                "结果表存储状态查询失败",
                table_id=table_id,
                error=str(error),
            ),
        }

    @staticmethod
    def _build_deadline_error(table_id: str) -> dict[str, Any]:
        return {
            "table_id": table_id,
            "data": None,
            "error": _error(
                "BATCH_DEADLINE_EXCEEDED",
                "批量结果表存储状态查询超过总时间限制",
                table_id=table_id,
            ),
        }
