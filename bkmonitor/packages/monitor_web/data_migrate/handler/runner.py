from __future__ import annotations

from pathlib import Path
from typing import Any

from django.utils import timezone

from monitor_web.data_migrate.constants import RECOVERY_RECORDS_DIRECTORY_NAME
from monitor_web.data_migrate.handler.base import BaseDirectoryHandler, HandlerExecutionError
from monitor_web.data_migrate.handler.cluster import SanitizeClusterInfoHandler
from monitor_web.data_migrate.handler.cluster_id import ReplaceClusterIdHandler
from monitor_web.data_migrate.handler.model_disable import DisableModelsHandler
from monitor_web.data_migrate.handler.tenant import ReplaceTenantIdHandler
from monitor_web.data_migrate.utils import read_json_file, write_json_file


def _iter_manifest_files(manifest: dict[str, Any]) -> list[tuple[int, str]]:
    """
    按 manifest 顺序返回需要处理的文件列表。

    返回值中的第一个元素是业务 ID：
    - 全局目录统一视为 ``0``
    - 业务目录取对应业务 ID
    """
    ordered_files: list[tuple[int, str]] = []
    for relative_file_path in manifest.get("global_files", []):
        ordered_files.append((0, relative_file_path))

    for bk_biz_id in manifest.get("bk_biz_ids", []):
        if int(bk_biz_id) == 0:
            continue
        for relative_file_path in manifest.get("biz_files", {}).get(str(bk_biz_id), []):
            ordered_files.append((int(bk_biz_id), relative_file_path))

    return ordered_files


def apply_handler_to_directory(
    directory_path: str | Path,
    handler: BaseDirectoryHandler,
) -> Path:
    """
    对导出目录执行一个 handler。

    handler 直接原地修改 fixture 文件，并在 manifest 中记录执行历史。
    """
    target_directory = Path(directory_path)
    manifest_path = target_directory / "manifest.json"
    manifest = read_json_file(manifest_path)

    for biz_id, relative_file_path in _iter_manifest_files(manifest):
        file_path = target_directory / relative_file_path
        records = read_json_file(file_path)
        if not isinstance(records, list):
            raise HandlerExecutionError(handler.name, file_path, "fixture payload is not a list")
        changed = handler.handle_records(records=records, biz_id=biz_id, relative_file_path=relative_file_path)
        if changed:
            write_json_file(file_path, records)

    manifest.setdefault("handlers", []).append(
        {
            **handler.get_manifest_payload(),
            "applied_at": timezone.now().isoformat(),
        }
    )
    write_json_file(manifest_path, manifest)
    return target_directory


def _normalize_handler_applied_at(applied_at: str) -> str:
    """将 handler 执行时间转成适合文件名的片段。"""
    return applied_at.replace("-", "").replace(":", "").replace("+", "_").replace(".", "_")


def _build_recovery_record_model_file_path(
    target_directory: Path,
    biz_id: int,
    applied_at: str,
    model_label: str,
) -> Path:
    """为 disable-models 的恢复记录生成按批次/业务/模型拆分的文件路径。"""
    normalized_applied_at = _normalize_handler_applied_at(applied_at)
    normalized_model_label = model_label.strip().lower()
    file_name = f"{normalized_model_label}.json"
    if biz_id == 0:
        return target_directory / RECOVERY_RECORDS_DIRECTORY_NAME / normalized_applied_at / "global" / file_name
    return target_directory / RECOVERY_RECORDS_DIRECTORY_NAME / normalized_applied_at / "biz" / str(biz_id) / file_name


def _load_disable_model_recovery_records(
    target_directory: Path,
    source_handler: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    读取 disable-models 的恢复记录。

    恢复记录统一从独立的 recovery_records 目录读取。
    """
    recovery_files = source_handler.get("recovery_files")
    if not isinstance(recovery_files, dict) or not recovery_files:
        raise ValueError("disable-models 未找到 recovery_files")

    recovery_records: list[dict[str, Any]] = []
    for biz_recovery_files in recovery_files.values():
        if not isinstance(biz_recovery_files, dict) or not biz_recovery_files:
            raise ValueError("disable-models 的 recovery_files 结构非法")
        for relative_file_path in biz_recovery_files.values():
            file_payload = read_json_file(target_directory / relative_file_path)
            if not isinstance(file_payload, list):
                raise ValueError(f"恢复记录文件结构非法: {relative_file_path}")
            recovery_records.extend(file_payload)
    return recovery_records


def restore_disabled_models_in_directory(
    directory_path: str | Path,
) -> Path:
    """
    恢复最近一次未恢复的 ``disable-models`` 处理结果。

    恢复依据来自 ``manifest.json -> handlers -> recovery_records``，
    会将记录中的原始字段值回写到对应 fixture 文件。
    """
    target_directory = Path(directory_path)
    manifest_path = target_directory / "manifest.json"
    manifest = read_json_file(manifest_path)
    handler_history = manifest.get("handlers", [])

    source_handler = next(
        (
            handler_payload
            for handler_payload in reversed(handler_history)
            if handler_payload.get("name") == "disable_models" and not handler_payload.get("restored_at")
        ),
        None,
    )
    if source_handler is None:
        raise ValueError("没有找到可恢复的 disable-models 执行记录")

    recovery_records = _load_disable_model_recovery_records(target_directory, source_handler)

    changed_files: dict[Path, list[dict[str, Any]]] = {}
    restored_records = 0
    for recovery_record in recovery_records:
        relative_file_path = recovery_record.get("relative_file_path")
        model = recovery_record.get("model")
        pk = recovery_record.get("pk")
        original_fields = recovery_record.get("original_fields")
        if not relative_file_path or not isinstance(original_fields, dict):
            raise ValueError(f"recovery_records 内容非法: {recovery_record}")

        file_path = target_directory / relative_file_path
        records = changed_files.get(file_path)
        if records is None:
            records = read_json_file(file_path)
            if not isinstance(records, list):
                raise HandlerExecutionError("restore_disable_models", file_path, "fixture payload is not a list")
            changed_files[file_path] = records

        target_record = next(
            (
                record
                for record in records
                if record.get("model") == model and record.get("pk") == pk and isinstance(record.get("fields"), dict)
            ),
            None,
        )
        if target_record is None:
            raise HandlerExecutionError("restore_disable_models", file_path, f"record not found: {model}#{pk}")

        target_record["fields"].update(original_fields)
        restored_records += 1

    for file_path, records in changed_files.items():
        write_json_file(file_path, records)

    restored_at = timezone.now().isoformat()
    source_handler["restored_at"] = restored_at
    source_handler.pop("recovery_records", None)
    handler_history.append(
        {
            "name": "restore_disable_models",
            "applied_at": restored_at,
            "source_applied_at": source_handler.get("applied_at"),
            "restored_records": restored_records,
        }
    )
    write_json_file(manifest_path, manifest)
    return target_directory


def replace_tenant_id_in_directory(
    directory_path: str | Path,
    biz_tenant_id_map: dict[int | str, str],
) -> Path:
    """按业务替换导出目录中的 ``bk_tenant_id`` 字段。"""
    return apply_handler_to_directory(
        directory_path=directory_path,
        handler=ReplaceTenantIdHandler(biz_tenant_id_map=biz_tenant_id_map),
    )


def sanitize_cluster_info_in_directory(
    directory_path: str | Path,
) -> Path:
    """将导出目录中的 ``metadata.ClusterInfo`` 连接信息替换为假数据。"""
    return apply_handler_to_directory(
        directory_path=directory_path,
        handler=SanitizeClusterInfoHandler(),
    )


def replace_cluster_id_in_directory(
    directory_path: str | Path,
    cluster_id_map: dict[int | str, int | str],
) -> Path:
    """按映射替换导出目录中的 cluster_id 引用。"""
    handler = ReplaceClusterIdHandler(cluster_id_map=cluster_id_map)
    target_directory = apply_handler_to_directory(
        directory_path=directory_path,
        handler=handler,
    )

    manifest_path = target_directory / "manifest.json"
    manifest = read_json_file(manifest_path)
    for scope_stats in manifest.get("export_stats", {}).values():
        if not isinstance(scope_stats, dict):
            continue
        clusters = scope_stats.get("clusters")
        if not isinstance(clusters, list):
            continue
        for cluster in clusters:
            if not isinstance(cluster, dict) or "cluster_id" not in cluster:
                continue
            try:
                source_cluster_id = int(cluster["cluster_id"])
            except (TypeError, ValueError):
                continue
            if source_cluster_id not in handler.cluster_id_map:
                continue
            cluster["cluster_id"] = handler.cluster_id_map[source_cluster_id]

    write_json_file(manifest_path, manifest)
    return target_directory


def disable_models_in_directory(
    directory_path: str | Path,
    model_labels: list[str],
) -> Path:
    """按模型关闭导出目录中的数据。"""
    handler = DisableModelsHandler(model_labels=model_labels)
    target_directory = apply_handler_to_directory(
        directory_path=directory_path,
        handler=handler,
    )

    manifest_path = target_directory / "manifest.json"
    manifest = read_json_file(manifest_path)
    handler_history = manifest.get("handlers", [])
    if not handler_history:
        raise ValueError("disable-models 执行后未找到 handler 历史记录")

    current_handler = handler_history[-1]
    applied_at = current_handler.get("applied_at")
    if current_handler.get("name") != "disable_models" or not applied_at:
        raise ValueError("disable-models 执行历史记录非法")

    recovery_records_by_biz_and_model: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for recovery_record in handler.recovery_records:
        biz_id = int(recovery_record["biz_id"])
        model_label = str(recovery_record["model"]).strip().lower()
        recovery_records_by_biz_and_model.setdefault(biz_id, {}).setdefault(model_label, []).append(recovery_record)

    recovery_files: dict[str, dict[str, str]] = {}
    for biz_id, model_record_map in recovery_records_by_biz_and_model.items():
        recovery_files[str(biz_id)] = {}
        for model_label, recovery_records in model_record_map.items():
            recovery_file_path = _build_recovery_record_model_file_path(
                target_directory=target_directory,
                biz_id=biz_id,
                applied_at=applied_at,
                model_label=model_label,
            )
            write_json_file(recovery_file_path, recovery_records)
            recovery_files[str(biz_id)][model_label] = str(recovery_file_path.relative_to(target_directory))

    current_handler["recovery_files"] = recovery_files
    current_handler.pop("recovery_records", None)
    write_json_file(manifest_path, manifest)
    return target_directory
