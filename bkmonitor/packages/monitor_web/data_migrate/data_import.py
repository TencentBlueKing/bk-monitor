from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from bk_dataview.models import Org
from bkmonitor.models import DefaultStrategyBizAccessModel
from django.db.models import Model
from monitor.models import ApplicationConfig
from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel

from monitor_web.data_migrate.constants import DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY, DEFAULT_ENCODING
from monitor_web.data_migrate.handler.runner import get_close_records_by_biz_from_directory
from monitor_web.data_migrate.utils import import_model_from_file, read_json_file


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


def _has_close_records(close_records: dict[str, list[int]]) -> bool:
    """判断业务下是否存在需要重新开启的关闭记录。"""
    return any(record_ids for record_ids in close_records.values())


def _build_org_backup_name(org: Org) -> str:
    """为导入前备份的 Grafana Org 生成不冲突的名称。"""
    base_backup_name = f"{org.name}_bak"
    backup_name = base_backup_name
    suffix = 1
    while Org.objects.filter(name=backup_name).exclude(pk=org.pk).exists():
        suffix += 1
        backup_name = f"{base_backup_name}_{suffix}"
    return backup_name


def _cleanup_biz_related_configs(bk_biz_ids: Sequence[int]) -> None:
    """
    在导入前清理业务维度的历史配置，避免残留脏数据影响导入结果。

    Args:
        bk_biz_ids: 本次需要导入的业务 ID 列表。
    """
    for bk_biz_id in _normalize_bk_biz_ids(bk_biz_ids):
        if bk_biz_id == 0:
            continue

        org = Org.objects.filter(name=str(bk_biz_id)).first()
        if org:
            org.name = _build_org_backup_name(org)
            org.save()

        SceneViewModel.objects.filter(bk_biz_id=bk_biz_id).delete()
        SceneViewOrderModel.objects.filter(bk_biz_id=bk_biz_id).delete()
        DefaultStrategyBizAccessModel.objects.filter(bk_biz_id=bk_biz_id).delete()
        ApplicationConfig.objects.filter(cc_biz_id=bk_biz_id).delete()
        DefaultStrategyBizAccessModel.objects.filter(bk_biz_id=bk_biz_id).delete()


def _sync_close_records_to_application_config(
    directory_path: Path,
    bk_biz_ids: Sequence[int],
) -> None:
    """
    将导入包中的关闭记录同步到 ``ApplicationConfig``。

    Args:
        directory_path: 已解压的数据迁移目录。
        bk_biz_ids: 本次实际导入的业务 ID 列表。
    """
    imported_bk_biz_ids = [bk_biz_id for bk_biz_id in _normalize_bk_biz_ids(bk_biz_ids) if bk_biz_id != 0]
    if not imported_bk_biz_ids:
        return

    try:
        close_records_by_biz = get_close_records_by_biz_from_directory(directory_path)
    except ValueError:
        close_records_by_biz = {}

    for bk_biz_id in imported_bk_biz_ids:
        close_records = close_records_by_biz.get(bk_biz_id, {})
        config_queryset = ApplicationConfig.objects.filter(
            cc_biz_id=bk_biz_id,
            key=DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY,
        )
        if not _has_close_records(close_records):
            config_queryset.delete()
            continue

        ApplicationConfig.objects.update_or_create(
            cc_biz_id=bk_biz_id,
            key=DATA_MIGRATE_CLOSED_RECORDS_APPLICATION_CONFIG_KEY,
            defaults={"value": close_records},
        )


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

    _cleanup_biz_related_configs(target_bk_biz_ids)

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

    _sync_close_records_to_application_config(
        directory_path=target_directory,
        bk_biz_ids=target_bk_biz_ids,
    )
    return imported_objects
