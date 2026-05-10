from __future__ import annotations

import logging
import shutil
import tarfile
import tempfile
from collections import OrderedDict
from collections.abc import Sequence
from itertools import chain
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from django.core import serializers
from django.core.files.storage import default_storage
from django.db.models import Model, QuerySet
from django.utils import timezone

from metadata.models import DataSource, ResultTable

logger = logging.getLogger(__name__)
from metadata.models.storage import ClusterInfo, DorisStorage, ESStorage, KafkaStorage
from monitor_web.data_migrate.biz_matadata import find_biz_table_and_data_id
from monitor_web.data_migrate.constants import DEFAULT_ENCODING, EXPORT_QUERYSET_CHUNK_SIZE
from monitor_web.data_migrate.fetcher.apm import get_apm_fetcher
from monitor_web.data_migrate.fetcher.dashboard import get_bk_dataview_fetcher
from monitor_web.data_migrate.fetcher.apm_ebpf import get_apm_ebpf_fetcher
from monitor_web.data_migrate.fetcher.apm_web import get_apm_web_fetcher
from monitor_web.data_migrate.fetcher.base import FetcherResultType
from monitor_web.data_migrate.fetcher.calendar import get_calendar_fetcher
from monitor_web.data_migrate.fetcher.custom_report import get_custom_report_fetcher
from monitor_web.data_migrate.fetcher.fta_web import get_fta_web_fetcher
from monitor_web.data_migrate.fetcher.internal_config import get_global_meta_fetcher, get_internal_config_fetcher
from monitor_web.data_migrate.fetcher.metadata.bcs import get_metadata_bcs_fetcher
from monitor_web.data_migrate.fetcher.metadata.data_source import (
    get_metadata_data_source_fetcher,
    get_metadata_result_table_fetcher,
)
from monitor_web.data_migrate.fetcher.metadata.space import get_metadata_space_fetcher
from monitor_web.data_migrate.fetcher.metadata.storage import (
    get_metadata_cluster_info_fetcher,
    get_metadata_storage_by_table_ids_fetcher,
)
from monitor_web.data_migrate.fetcher.plugin_collect import get_collect_config_fetcher, get_collector_plugin_fetcher
from monitor_web.data_migrate.fetcher.query import get_query_template_fetcher
from monitor_web.data_migrate.fetcher.report import get_report_fetcher
from monitor_web.data_migrate.fetcher.strategy import get_strategy_fetcher
from monitor_web.data_migrate.fetcher.uptimecheck import get_uptimecheck_fetcher
from monitor_web.data_migrate.utils import _resolve_using, write_json_file


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


def _iter_fetcher_objects(fetchers: Sequence[FetcherResultType], context: str | None = None):
    """按 fetcher 配置流式查询并去重返回模型实例。"""
    seen_object_keys: set[tuple[str, Any]] = set()
    for model_cls, filters, exclude in fetchers:
        queryset = _build_queryset(model_cls, filters, exclude)
        try:
            for instance in queryset.iterator(chunk_size=EXPORT_QUERYSET_CHUNK_SIZE):
                object_key = (instance._meta.label_lower, instance.pk)
                if object_key in seen_object_keys:
                    continue
                seen_object_keys.add(object_key)
                yield instance
        except Exception:
            logger.exception(
                "data_migrate export failed while iterating queryset, context=%s, model=%s, db_table=%s, "
                "filters=%s, exclude=%s",
                context,
                model_cls._meta.label,
                model_cls._meta.db_table,
                filters,
                exclude,
            )
            raise


def _build_biz_export_context(
    bk_biz_id: int,
) -> tuple[OrderedDict[str, list[FetcherResultType]], list[str], list[int]]:
    """构建单个业务的导出上下文，包括 fetcher 和 metadata 关联 ID。"""
    table_ids, data_ids = find_biz_table_and_data_id(bk_biz_id)
    normalized_table_ids = sorted(set(table_ids))
    normalized_data_ids = sorted(set(data_ids))

    module_fetchers: OrderedDict[str, list[FetcherResultType]] = OrderedDict(
        [
            ("strategy", get_strategy_fetcher(bk_biz_id)),
            ("collector_plugin", get_collector_plugin_fetcher(bk_biz_id)),
            ("collect_config", get_collect_config_fetcher(bk_biz_id)),
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
            ("bk_dataview", get_bk_dataview_fetcher(bk_biz_id)),
        ]
    )

    if normalized_data_ids:
        module_fetchers["metadata_data_source"] = get_metadata_data_source_fetcher(normalized_data_ids)
    if normalized_table_ids:
        module_fetchers["metadata_result_table"] = get_metadata_result_table_fetcher(normalized_table_ids)
        module_fetchers["metadata_storage"] = get_metadata_storage_by_table_ids_fetcher(normalized_table_ids)
        # datalink 当前先不参与目录导出，避免把一批额外链路配置带进迁移包。
        # module_fetchers["metadata_datalink"] = get_metadata_datalink_fetcher(normalized_table_ids)

    return module_fetchers, normalized_table_ids, normalized_data_ids


def _get_global_module_fetchers() -> OrderedDict[str, list[FetcherResultType]]:
    """获取全局目录下各模块对应的 fetcher。"""
    return OrderedDict(
        [
            ("global_meta", get_global_meta_fetcher()),
            ("calendar", get_calendar_fetcher()),
            ("report", get_report_fetcher(0)),
            ("apm", get_apm_fetcher(0)),
            ("collector_plugin", get_collector_plugin_fetcher(0)),
            ("metadata_cluster", get_metadata_cluster_info_fetcher(None)),
        ]
    )


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


def _write_fixture_file(file_path: Path, export_objects, format: str, indent: int) -> None:
    """将单个模块对象集合写入 fixture 文件。"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding=DEFAULT_ENCODING) as stream:
        _serialize_objects(export_objects, format=format, indent=indent, stream=stream)


def _build_scope_export_stats(
    scope_type: str,
    tables: Sequence[dict[str, Any]] | None = None,
    datasources: Sequence[dict[str, Any]] | None = None,
    clusters: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """初始化单个统计范围的导出元数据。"""
    return {
        "scope": scope_type,
        "model_counts": {},
        "tables": list(tables or []),
        "datasources": list(datasources or []),
        "clusters": list(clusters or []),
    }


def _track_scope_model_counts(export_objects, model_counts: dict[str, int]):
    """在写出 fixture 时同步累计各模型导出数量。"""
    for export_object in export_objects:
        model_label = export_object._meta.label
        model_counts[model_label] = model_counts.get(model_label, 0) + 1
        yield export_object


def _build_table_export_refs(table_ids: Sequence[str]) -> list[dict[str, Any]]:
    """将 table_ids 展开为包含中文名的结果表引用信息。"""
    normalized_table_ids = list(table_ids)
    if not normalized_table_ids:
        return []

    table_name_map = {
        row["table_id"]: row["table_name_zh"]
        for row in ResultTable.objects.filter(table_id__in=normalized_table_ids).values("table_id", "table_name_zh")
    }
    return [
        {
            "table_id": table_id,
            "table_name_zh": table_name_map.get(table_id),
        }
        for table_id in normalized_table_ids
    ]


def _build_data_source_export_refs(data_ids: Sequence[int]) -> list[dict[str, Any]]:
    """将 data_ids 展开为包含名称的数据源引用信息。"""
    normalized_data_ids = list(data_ids)
    if not normalized_data_ids:
        return []

    data_name_map = {
        row["bk_data_id"]: row["data_name"]
        for row in DataSource.objects.filter(bk_data_id__in=normalized_data_ids).values("bk_data_id", "data_name")
    }
    return [
        {
            "bk_data_id": data_id,
            "data_name": data_name_map.get(data_id),
        }
        for data_id in normalized_data_ids
    ]


def _build_cluster_export_refs(table_ids: Sequence[str], data_ids: Sequence[int]) -> list[dict[str, Any]]:
    """统计本次导出中被 DataSource/Storage 实际引用到的集群摘要。"""
    normalized_table_ids = list(table_ids)
    normalized_data_ids = list(data_ids)
    cluster_ids: set[int] = set()

    if normalized_data_ids:
        cluster_ids.update(
            cluster_id
            for cluster_id in DataSource.objects.filter(bk_data_id__in=normalized_data_ids).values_list(
                "mq_cluster_id", flat=True
            )
            if cluster_id is not None
        )

    if normalized_table_ids:
        for storage_model in (KafkaStorage, ESStorage, DorisStorage):
            cluster_ids.update(
                cluster_id
                for cluster_id in storage_model.objects.filter(table_id__in=normalized_table_ids).values_list(
                    "storage_cluster_id", flat=True
                )
                if cluster_id is not None
            )

    if not cluster_ids:
        return []

    cluster_rows = ClusterInfo.objects.filter(cluster_id__in=sorted(cluster_ids)).values(
        "cluster_id", "cluster_name", "display_name", "cluster_type"
    )
    cluster_map = {row["cluster_id"]: row for row in cluster_rows}
    return [
        {
            "cluster_id": cluster_id,
            "cluster_name": cluster_map.get(cluster_id, {}).get("cluster_name"),
            "display_name": cluster_map.get(cluster_id, {}).get("display_name"),
            "cluster_type": cluster_map.get(cluster_id, {}).get("cluster_type"),
        }
        for cluster_id in sorted(cluster_ids)
    ]


def _peek_export_objects(export_objects):
    """探测流式对象是否为空，避免为空模块创建无意义文件。"""
    iterator = iter(export_objects)
    first_object = next(iterator, None)
    if first_object is None:
        return None
    return chain([first_object], iterator)


def export_biz_data_to_directory(
    directory_path: str | Path,
    bk_biz_ids: Sequence[int],
    format: str = "json",
    indent: int = 2,
) -> Path:
    """
    按目录结构导出业务迁移数据。

    目录约定：
    - 根目录下写 ``manifest.json``
    - 全局数据写到 ``global/*.json``
    - 业务数据写到 ``biz/<bk_biz_id>/*.json``
    """
    normalized_bk_biz_ids = _normalize_bk_biz_ids(bk_biz_ids)
    target_directory = Path(directory_path)
    target_directory.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "version": 1,
        "format": format,
        "exported_at": timezone.now().isoformat(),
        "bk_biz_ids": normalized_bk_biz_ids,
        "global_files": [],
        "biz_files": {},
        "export_stats": {},
    }

    if 0 in normalized_bk_biz_ids:
        global_stats = _build_scope_export_stats("global")
        for module_name, fetchers in _get_global_module_fetchers().items():
            module_objects = _peek_export_objects(_iter_fetcher_objects(fetchers, context=f"global:{module_name}"))
            if module_objects is None:
                continue
            relative_file_path = Path("global") / f"{module_name}.{format}"
            _write_fixture_file(
                target_directory / relative_file_path,
                _track_scope_model_counts(module_objects, global_stats["model_counts"]),
                format=format,
                indent=indent,
            )
            manifest["global_files"].append(relative_file_path.as_posix())
        manifest["export_stats"]["0"] = global_stats

    for bk_biz_id in normalized_bk_biz_ids:
        if bk_biz_id == 0:
            continue

        module_fetchers, table_ids, data_ids = _build_biz_export_context(bk_biz_id)
        biz_stats = _build_scope_export_stats(
            "biz",
            tables=_build_table_export_refs(table_ids),
            datasources=_build_data_source_export_refs(data_ids),
            clusters=_build_cluster_export_refs(table_ids, data_ids),
        )
        biz_relative_files: list[str] = []
        for module_name, fetchers in module_fetchers.items():
            module_objects = _peek_export_objects(
                _iter_fetcher_objects(fetchers, context=f"biz:{bk_biz_id}:{module_name}")
            )
            if module_objects is None:
                continue
            relative_file_path = Path("biz") / str(bk_biz_id) / f"{module_name}.{format}"
            _write_fixture_file(
                target_directory / relative_file_path,
                _track_scope_model_counts(module_objects, biz_stats["model_counts"]),
                format=format,
                indent=indent,
            )
            biz_relative_files.append(relative_file_path.as_posix())
        manifest["biz_files"][str(bk_biz_id)] = biz_relative_files
        manifest["export_stats"][str(bk_biz_id)] = biz_stats

    write_json_file(target_directory / "manifest.json", manifest, encoding=DEFAULT_ENCODING)
    return target_directory


def upload_export_directory_to_storage(directory_path: str | Path) -> str:
    """将导出目录打包为 tar.gz 并上传到 default_storage，返回下载链接。

    流程：
    1. 将导出目录打成 tar.gz 压缩包
    2. 通过 ``default_storage.save`` 上传到 bkrepo
    3. 生成并返回下载 URL

    Args:
        directory_path: ``export_biz_data_to_directory`` 返回的导出目录路径

    Returns:
        可直接访问的下载 URL
    """
    target_directory = Path(directory_path)
    archive_name = target_directory.name
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")

    tmp_dir = tempfile.mkdtemp()
    try:
        tarfile_path = Path(tmp_dir) / f"{archive_name}.tar.gz"
        with tarfile.open(tarfile_path, "w:gz") as tar:
            tar.add(str(target_directory), arcname=archive_name)

        storage_path = f"data_migrate/export/{archive_name}-{timestamp}.tar.gz"
        with tarfile_path.open("rb") as f:
            default_storage.save(storage_path, f)

        download_url = default_storage.url(storage_path)

        if hasattr(settings, "BK_MONITOR_HOST") and settings.BK_MONITOR_HOST.startswith("https://"):
            download_url = download_url.replace("http://", "https://")

        if not download_url.startswith("http"):
            download_url = urljoin(settings.BK_MONITOR_HOST, download_url)

        logger.info("upload_export_directory_to_storage: 上传完成, download_url=%s", download_url)
        return download_url
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
