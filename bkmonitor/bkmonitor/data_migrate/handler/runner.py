from __future__ import annotations

from pathlib import Path
from typing import Any

from django.utils import timezone

from bkmonitor.data_migrate.handler.base import BaseDirectoryHandler, HandlerExecutionError
from bkmonitor.data_migrate.handler.cluster import SanitizeClusterInfoHandler
from bkmonitor.data_migrate.handler.tenant import ReplaceTenantIdHandler
from bkmonitor.data_migrate.utils import read_json_file, write_json_file


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
