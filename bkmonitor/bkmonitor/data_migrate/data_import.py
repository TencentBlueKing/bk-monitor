from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from django.db.models import Model

from bkmonitor.data_migrate.constants import DEFAULT_ENCODING
from bkmonitor.data_migrate.utils import import_model_from_file, read_json_file


def _normalize_bk_biz_ids(bk_biz_ids: Sequence[int] | None) -> list[int]:
    """将业务 ID 列表规整为去重后的有序列表。"""
    normalized_bk_biz_ids = []
    seen: set[int] = set()
    for bk_biz_id in bk_biz_ids or []:
        normalized_bk_biz_id = int(bk_biz_id)
        if normalized_bk_biz_id in seen:
            continue
        seen.add(normalized_bk_biz_id)
        normalized_bk_biz_ids.append(normalized_bk_biz_id)
    return normalized_bk_biz_ids


def import_biz_data_from_directory(
    directory_path: str | Path,
    bk_biz_ids: Sequence[int] | None = None,
    atomic: bool = True,
) -> list[Model]:
    """
    按目录结构导入迁移数据。

    导入顺序由 ``manifest.json`` 控制：
    1. 如业务列表包含 ``0``，则先导全局目录
    2. 再按业务目录顺序导入

    默认行为是不传 ``bk_biz_ids``，则按导出目录中的 ``manifest.json`` 全量导入。
    如果显式传入业务列表，则只导入对应业务；``0`` 代表同时导入全局目录。
    """
    target_directory = Path(directory_path)
    manifest = read_json_file(target_directory / "manifest.json", encoding=DEFAULT_ENCODING)
    format = manifest.get("format", "json")
    exported_bk_biz_ids = _normalize_bk_biz_ids(manifest.get("bk_biz_ids", []))
    target_bk_biz_ids = exported_bk_biz_ids if bk_biz_ids is None else _normalize_bk_biz_ids(bk_biz_ids)

    missing_bk_biz_ids = [bk_biz_id for bk_biz_id in target_bk_biz_ids if bk_biz_id not in exported_bk_biz_ids]
    if missing_bk_biz_ids:
        raise ValueError(f"导入目录中不存在这些业务 ID: {missing_bk_biz_ids}")

    imported_objects: list[Model] = []
    if 0 in target_bk_biz_ids:
        for relative_file_path in manifest.get("global_files", []):
            imported_objects.extend(
                import_model_from_file(
                    file_path=target_directory / relative_file_path,
                    format=format,
                    using=None,
                    ignorenonexistent=False,
                    handle_forward_references=True,
                    save=True,
                    atomic=atomic,
                    encoding=DEFAULT_ENCODING,
                )
            )

    for bk_biz_id in map(str, target_bk_biz_ids):
        if bk_biz_id == "0":
            continue
        for relative_file_path in manifest.get("biz_files", {}).get(bk_biz_id, []):
            imported_objects.extend(
                import_model_from_file(
                    file_path=target_directory / relative_file_path,
                    format=format,
                    using=None,
                    ignorenonexistent=False,
                    handle_forward_references=True,
                    save=True,
                    atomic=atomic,
                    encoding=DEFAULT_ENCODING,
                )
            )

    return imported_objects
