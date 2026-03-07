from __future__ import annotations

from pathlib import Path

from django.db.models import Model

from bkmonitor.data_migrate.constants import DEFAULT_ENCODING
from bkmonitor.data_migrate.utils import import_model_from_file, read_json_file


def import_biz_data_from_directory(directory_path: str | Path, atomic: bool = True) -> list[Model]:
    """
    按目录结构导入迁移数据。

    导入顺序由 ``manifest.json`` 控制：
    1. 先导全局目录
    2. 再按业务目录顺序导入
    """
    target_directory = Path(directory_path)
    manifest = read_json_file(target_directory / "manifest.json", encoding=DEFAULT_ENCODING)
    format = manifest.get("format", "json")

    imported_objects: list[Model] = []
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

    for bk_biz_id in map(str, manifest.get("bk_biz_ids", [])):
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
