from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core import serializers
from django.db.models import Model, QuerySet
from django.utils import timezone

from bkmonitor.data_migrate.biz_matadata import find_biz_table_and_data_id
from bkmonitor.data_migrate.fetcher.apm import get_apm_fetcher
from bkmonitor.data_migrate.fetcher.apm_ebpf import get_apm_ebpf_fetcher
from bkmonitor.data_migrate.fetcher.apm_web import get_apm_web_fetcher
from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from bkmonitor.data_migrate.fetcher.calendar import get_calendar_fetcher
from bkmonitor.data_migrate.fetcher.custom_report import get_custom_report_fetcher
from bkmonitor.data_migrate.fetcher.fta_web import get_fta_web_fetcher
from bkmonitor.data_migrate.fetcher.internal_config import get_global_meta_fetcher, get_internal_config_fetcher
from bkmonitor.data_migrate.fetcher.metadata.bcs import get_metadata_bcs_fetcher
from bkmonitor.data_migrate.fetcher.metadata.data_source import (
    get_metadata_data_source_fetcher,
    get_metadata_result_table_fetcher,
)
from bkmonitor.data_migrate.fetcher.metadata.space import get_metadata_space_fetcher
from bkmonitor.data_migrate.fetcher.metadata.storage import (
    get_metadata_cluster_info_fetcher,
    get_metadata_storage_by_table_ids_fetcher,
)
from bkmonitor.data_migrate.fetcher.plugin_collect import get_collect_config_fetcher, get_collector_plugin_fetcher
from bkmonitor.data_migrate.fetcher.query import get_query_template_fetcher
from bkmonitor.data_migrate.fetcher.report import get_report_fetcher
from bkmonitor.data_migrate.fetcher.strategy import get_strategy_fetcher
from bkmonitor.data_migrate.fetcher.uptimecheck import get_uptimecheck_fetcher
from bkmonitor.data_migrate.utils import (
    _get_reserved_auto_increment_start,
    _resolve_using,
    get_auto_increment_start,
    import_model_from_file,
    reset_auto_increment_start,
)
from metadata.models.storage import DorisStorage, ESStorage, KafkaStorage, StorageClusterRecord

DEFAULT_ENCODING = "utf-8"


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


def _build_queryset(
    model_cls: type[Model],
    filters: dict[str, Any] | None,
    exclude: dict[str, Any] | None,
) -> QuerySet:
    """根据 fetcher 返回值构建稳定的 ORM 查询。"""
    resolved_using = _resolve_using(model_cls, using=None, for_write=False)
    queryset = model_cls.objects.using(resolved_using).all()
    if filters:
        queryset = queryset.filter(**filters)
    if exclude:
        queryset = queryset.exclude(**exclude)
    return queryset.order_by("pk")


def _iter_fetcher_objects(fetchers: Sequence[FetcherResultType]):
    """按 fetcher 配置流式查询并去重返回模型实例。"""
    seen_object_keys: set[tuple[str, Any]] = set()
    for model_cls, filters, exclude in fetchers:
        queryset = _build_queryset(model_cls, filters, exclude)
        for instance in queryset.iterator(chunk_size=10000):
            object_key = (instance._meta.label_lower, instance.pk)
            if object_key in seen_object_keys:
                continue
            seen_object_keys.add(object_key)
            yield instance


def _get_biz_module_fetchers(bk_biz_id: int) -> OrderedDict[str, list[FetcherResultType]]:
    """获取单个业务目录下各模块对应的 fetcher。"""
    table_ids, data_ids = find_biz_table_and_data_id(bk_biz_id)
    cluster_ids = _collect_cluster_ids(table_ids)

    module_fetchers: OrderedDict[str, list[FetcherResultType]] = OrderedDict(
        [
            ("strategy", get_strategy_fetcher(bk_biz_id)),
            ("collect_config", get_collect_config_fetcher(bk_biz_id)),
            ("collector_plugin", get_collector_plugin_fetcher(bk_biz_id)),
            ("uptimecheck", get_uptimecheck_fetcher(bk_biz_id)),
            ("report", get_report_fetcher(bk_biz_id)),
            ("query", get_query_template_fetcher(bk_biz_id)),
            ("internal_config", get_internal_config_fetcher(bk_biz_id)),
            ("custom_report", get_custom_report_fetcher(bk_biz_id)),
            ("fta_web", get_fta_web_fetcher(bk_biz_id)),
            ("apm", get_apm_fetcher(bk_biz_id)),
            ("apm_web", get_apm_web_fetcher(bk_biz_id)),
            ("apm_ebpf", get_apm_ebpf_fetcher(bk_biz_id)),
            ("metadata_space", get_metadata_space_fetcher(bk_biz_id)),
            ("metadata_bcs", get_metadata_bcs_fetcher(bk_biz_id)),
        ]
    )

    if data_ids:
        module_fetchers["metadata_data_source"] = get_metadata_data_source_fetcher(data_ids)
    if table_ids:
        module_fetchers["metadata_result_table"] = get_metadata_result_table_fetcher(table_ids)
        module_fetchers["metadata_storage"] = get_metadata_storage_by_table_ids_fetcher(table_ids)
        # datalink 当前先不参与目录导出，避免把一批额外链路配置带进迁移包。
        # module_fetchers["metadata_datalink"] = get_metadata_datalink_fetcher(table_ids)
    if cluster_ids:
        module_fetchers["metadata_cluster"] = get_metadata_cluster_info_fetcher(cluster_ids)

    return module_fetchers


def _get_global_module_fetchers() -> OrderedDict[str, list[FetcherResultType]]:
    """获取全局目录下各模块对应的 fetcher。"""
    return OrderedDict(
        [
            ("global_meta", get_global_meta_fetcher()),
            ("calendar", get_calendar_fetcher()),
            ("report", get_report_fetcher(0)),
            ("apm", get_apm_fetcher(0)),
            ("collector_plugin", get_collector_plugin_fetcher(0)),
        ]
    )


def _collect_cluster_ids(table_ids: Sequence[str]) -> list[int]:
    """
    由 table_ids 回查实际引用到的存储集群 ID。

    ``ClusterInfo`` 和 ``ClusterConfig`` 已经合并在同一个 fetcher 中，
    这里先把用到的集群 ID 收敛出来，再单独补齐集群层数据。
    """
    normalized_table_ids = list(table_ids)
    if not normalized_table_ids:
        return []

    cluster_ids: set[int] = set()
    cluster_ids.update(
        ESStorage.objects.filter(table_id__in=normalized_table_ids).values_list("storage_cluster_id", flat=True)
    )
    cluster_ids.update(
        ESStorage.objects.filter(origin_table_id__in=normalized_table_ids).values_list("storage_cluster_id", flat=True)
    )
    cluster_ids.update(
        KafkaStorage.objects.filter(table_id__in=normalized_table_ids).values_list("storage_cluster_id", flat=True)
    )
    cluster_ids.update(
        DorisStorage.objects.filter(table_id__in=normalized_table_ids).values_list("storage_cluster_id", flat=True)
    )
    cluster_ids.update(
        StorageClusterRecord.objects.filter(table_id__in=normalized_table_ids).values_list("cluster_id", flat=True)
    )
    return sorted(cluster_id for cluster_id in cluster_ids if cluster_id is not None)


def _serialize_objects(export_objects, format: str, indent: int, stream=None) -> str | None:
    """固定按原始主键和外键值序列化对象。"""
    return serializers.serialize(
        format,
        export_objects,
        use_natural_foreign_keys=False,
        use_natural_primary_keys=False,
        indent=indent,
        stream=stream,
    )


def _write_fixture_file(
    file_path: Path,
    export_objects,
    format: str,
    indent: int,
) -> None:
    """将单个模块对象集合写入 fixture 文件。"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding=DEFAULT_ENCODING) as stream:
        _serialize_objects(export_objects, format=format, indent=indent, stream=stream)


def _write_json_file(file_path: Path, payload: dict[str, Any]) -> None:
    """将普通 JSON 元数据文件落盘。"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding=DEFAULT_ENCODING,
    )


def _update_sequences_state(model_state: dict[str, dict[str, Any]], export_object: Model) -> None:
    """
    增量更新顶层自增游标信息。

    导出时不再把所有对象累积到内存，而是在写出模块文件的同时更新模型状态。
    """
    model_cls = export_object.__class__
    model_label = model_cls._meta.label
    state = model_state.get(model_label)
    if state is None:
        current_start = get_auto_increment_start(model_cls)
        if current_start is None:
            return
        state = model_state.setdefault(
            model_label,
            {
                "has_auto_increment_pk": True,
                "current_start": current_start,
                "reserved_start": _get_reserved_auto_increment_start(current_start),
                "exported_max_pk": None,
            },
        )

    object_pk = export_object.pk
    if isinstance(object_pk, int):
        previous_max_pk = state["exported_max_pk"]
        state["exported_max_pk"] = object_pk if previous_max_pk is None else max(previous_max_pk, object_pk)


def _build_sequences_payload(model_state: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """将增量维护的模型状态包装为顶层游标文件结构。"""
    return {"models": model_state}


def _track_sequence_state(export_objects, model_state: dict[str, dict[str, Any]]):
    """在序列化写文件的同时更新自增游标状态。"""
    for export_object in export_objects:
        _update_sequences_state(model_state, export_object)
        yield export_object


def _peek_export_objects(export_objects):
    """探测流式对象是否为空，避免为空模块创建无意义文件。"""
    iterator = iter(export_objects)
    first_object = next(iterator, None)
    if first_object is None:
        return None
    return chain([first_object], iterator)


def _apply_sequences_payload(sequences_payload: dict[str, Any]) -> None:
    """根据导出时记录的游标信息恢复数据库自增游标。"""
    for model_label, state in (sequences_payload.get("models") or {}).items():
        app_label, model_name = model_label.split(".", 1)
        model_cls = apps.get_model(app_label, model_name)

        reserved_start = state.get("reserved_start")
        exported_max_pk = state.get("exported_max_pk")
        target_start = reserved_start
        if isinstance(exported_max_pk, int):
            target_start = max(target_start or 0, exported_max_pk + 1)

        if target_start:
            reset_auto_increment_start(model_cls, start=target_start)


def apply_auto_increment_from_directory(
    directory_path: str | Path,
) -> None:
    """
    从导出目录读取 ``sequences.json`` 并恢复自增游标。

    这个动作与数据导入解耦，调用方可以在确认数据导入完成后再单独执行。
    """
    target_directory = Path(directory_path)
    manifest = json.loads((target_directory / "manifest.json").read_text(encoding=DEFAULT_ENCODING))
    sequence_file = manifest.get("sequence_file", "sequences.json")
    sequence_path = target_directory / sequence_file
    if not sequence_path.exists():
        return
    _apply_sequences_payload(json.loads(sequence_path.read_text(encoding=DEFAULT_ENCODING)))


def export_biz_data_to_directory(
    directory_path: str | Path,
    bk_biz_ids: Sequence[int],
    format: str = "json",
    indent: int = 2,
) -> Path:
    """
    按目录结构导出业务迁移数据。

    目录约定：
    - 根目录下写 ``manifest.json`` 和 ``sequences.json``
    - 全局数据写到 ``global/*.json``
    - 业务数据写到 ``biz/<bk_biz_id>/*.json``
    """
    normalized_bk_biz_ids = _normalize_bk_biz_ids(bk_biz_ids)
    target_directory = Path(directory_path)
    target_directory.mkdir(parents=True, exist_ok=True)

    sequences_state: dict[str, dict[str, Any]] = {}
    manifest: dict[str, Any] = {
        "version": 1,
        "format": format,
        "exported_at": timezone.now().isoformat(),
        "bk_biz_ids": normalized_bk_biz_ids,
        "global_files": [],
        "biz_files": {},
        "sequence_file": "sequences.json",
    }

    if 0 in normalized_bk_biz_ids:
        for module_name, fetchers in _get_global_module_fetchers().items():
            module_objects = _peek_export_objects(_iter_fetcher_objects(fetchers))
            if module_objects is None:
                continue
            relative_file_path = Path("global") / f"{module_name}.{format}"
            _write_fixture_file(
                target_directory / relative_file_path,
                _track_sequence_state(module_objects, sequences_state),
                format=format,
                indent=indent,
            )
            manifest["global_files"].append(relative_file_path.as_posix())

    for bk_biz_id in normalized_bk_biz_ids:
        if bk_biz_id == 0:
            continue

        biz_relative_files: list[str] = []
        for module_name, fetchers in _get_biz_module_fetchers(bk_biz_id).items():
            module_objects = _peek_export_objects(_iter_fetcher_objects(fetchers))
            if module_objects is None:
                continue
            relative_file_path = Path("biz") / str(bk_biz_id) / f"{module_name}.{format}"
            _write_fixture_file(
                target_directory / relative_file_path,
                _track_sequence_state(module_objects, sequences_state),
                format=format,
                indent=indent,
            )
            biz_relative_files.append(relative_file_path.as_posix())
        manifest["biz_files"][str(bk_biz_id)] = biz_relative_files

    _write_json_file(target_directory / "sequences.json", _build_sequences_payload(sequences_state))
    _write_json_file(target_directory / "manifest.json", manifest)
    return target_directory


def import_biz_data_from_directory(
    directory_path: str | Path,
    atomic: bool = True,
) -> list[Model]:
    """
    按目录结构导入迁移数据。

    导入顺序由 ``manifest.json`` 控制：
    1. 先导全局目录
    2. 再按业务目录顺序导入
    """
    target_directory = Path(directory_path)
    manifest = json.loads((target_directory / "manifest.json").read_text(encoding=DEFAULT_ENCODING))
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
