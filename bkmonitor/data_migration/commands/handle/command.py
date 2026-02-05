"""处理命令"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click

from data_migration.config import BIZ_TENANT_ID_MAPPING, DEFAULT_TARGET_TENANT_ID
from data_migration.utils.types import RowDict

from ..export import writer
from ..import_ import reader
from .biz_filter import CACHE_SOURCE_TABLES, EXTRA_PRELOAD_MODELS, get_row_biz_id, preload_relation_cache
from .biz_splitter import (
    BizInfo,
    get_biz_list_from_spaces,
    get_biz_output_dir,
    get_global_output_dir,
    split_rows_by_biz,
)
from .builtins import configure_enable_field_recording, flush_enable_field_records
from .handle import (
    get_global_required_models,
    get_table_pipeline,
    run_global_pipelines,
)
from .metadata_relations import get_global_metadata, get_metadata_by_biz


@dataclass(frozen=True)
class HandleRecord:
    """处理记录"""

    scope: str
    app_label: str
    model_name: str
    input_rows: int
    output_rows: int
    filtered_rows: int
    duration_sec: float
    size_bytes: int


METADATA_RELATION_EXTRA_MODELS: set[str] = {
    "monitor_web.CustomTSTable",
    "monitor_web.CustomEventGroup",
    "monitor_web.CollectorPluginMeta",
    "apm.MetricDataSource",
    "apm.LogDataSource",
    "apm.TraceDataSource",
    "apm.ProfileDataSource",
}


def _parse_biz_id_set(raw_value: str | None) -> set[int]:
    """解析业务ID集合。

    Args:
        raw_value: 逗号分隔的业务ID字符串。

    Returns:
        业务ID集合。
    """
    if not raw_value:
        return set()
    biz_ids: set[int] = set()
    for item in raw_value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        try:
            biz_ids.add(int(stripped))
        except ValueError as exc:
            raise click.ClickException(f"非法业务ID: {stripped}") from exc
    return biz_ids


def create_command() -> click.Command:
    """创建处理命令"""

    handle_help_text = "处理导出的 JSON 数据（支持变更、过滤、跨表处理）"
    handle_epilog_text = """\
\b
输入说明:
  - input: 目录或 .zip
    - 目录会递归读取 *.json（支持按 app_label 分目录）
    - .zip 会先解压到临时目录再读取

\b
输出说明:
  - out: 目录或 .zip
    - 若为 .zip，会先处理到临时目录后再打包输出
  - 输出结构与导出一致，可直接用于 import

\b
处理流程:
  1. 按需读取导出文件（惰性读取）
  2. 对每张表执行 TablePipeline（行级变更/过滤）
  3. 对全局处理依赖的表，收集后执行 GlobalPipeline（跨表处理）
  4. 写出处理后的数据

\b
示例:
  - uv run python -m data_migration.cli handle --input /tmp/export_dir --out /tmp/handled_dir
  - uv run python -m data_migration.cli handle --input /tmp/export.zip --out /tmp/handled.zip
"""

    @click.command("handle", help=handle_help_text, epilog=handle_epilog_text)  # type: ignore[attr-defined]
    @click.option(
        "--input",
        "input_path",
        required=True,
        type=click.Path(path_type=Path, exists=True),
        help="输入路径（目录或 .zip）",
    )
    @click.option(
        "--out",
        "output_path",
        required=True,
        type=click.Path(path_type=Path),
        help="输出路径（目录或 .zip）",
    )
    @click.option(
        "--write-empty-file/--skip-empty-file",
        "write_empty_file",
        default=False,
        show_default=True,
        help="当数据量为 0 时是否仍生成 JSON 文件（默认跳过）",
    )
    @click.option("--dry-run", is_flag=True, default=False, help="仅统计不写入")
    @click.option("--split-by-biz", is_flag=True, default=False, help="按业务拆分数据到独立目录")
    @click.option(
        "--exclude-biz-ids",
        default="",
        help="按业务ID排除（逗号分隔，支持正负业务ID）",
    )
    def handle_data(
        input_path: Path,
        output_path: Path,
        write_empty_file: bool,
        dry_run: bool,
        split_by_biz: bool,
        exclude_biz_ids: str,
    ) -> None:
        """处理数据"""
        excluded_biz_ids = _parse_biz_id_set(exclude_biz_ids)
        global_required_models = get_global_required_models()
        handled_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        with reader.prepare_input_dir(input_path) as input_dir:
            file_paths = reader.iter_export_file_paths(input_dir)
            if not file_paths:
                raise click.ClickException(f"输入路径中未找到 JSON 文件: {input_path}")

            # 构建 model_label -> file_path 映射
            model_file_map: dict[str, Path] = {}
            for file_path in file_paths:
                model_label = reader.infer_model_label_from_path(input_dir, file_path)
                if model_label:
                    model_file_map[model_label] = file_path

            # 预加载缓存源表（在 pipeline 执行前构建关联缓存）
            rows_by_model: dict[str, list[RowDict]] = {}
            preload_models = set(CACHE_SOURCE_TABLES) | EXTRA_PRELOAD_MODELS
            for model_label in preload_models:
                file_path = model_file_map.get(model_label)
                if not file_path:
                    continue
                payload = reader.read_export_file(file_path)
                rows = payload.get("data", [])
                if rows:
                    rows_by_model[model_label] = rows
            preload_relation_cache(rows_by_model)

            with writer.prepare_output_dir(output_path) as (output_dir, output_zip):
                configure_enable_field_recording(
                    output_dir=output_dir,
                    handled_at=handled_at,
                    enabled=not dry_run,
                )
                records: list[HandleRecord] = []
                if split_by_biz:
                    _handle_split_by_biz(
                        file_paths=file_paths,
                        input_dir=input_dir,
                        model_file_map=model_file_map,
                        output_dir=output_dir,
                        handled_at=handled_at,
                        write_empty_file=write_empty_file,
                        dry_run=dry_run,
                        records=records,
                        excluded_biz_ids=excluded_biz_ids,
                    )
                else:
                    _handle_default_mode(
                        file_paths=file_paths,
                        input_dir=input_dir,
                        output_dir=output_dir,
                        handled_at=handled_at,
                        write_empty_file=write_empty_file,
                        dry_run=dry_run,
                        records=records,
                        global_required_models=global_required_models,
                        excluded_biz_ids=excluded_biz_ids,
                    )

                # 写出报告
                if not dry_run:
                    flush_enable_field_records()
                    report_path = _write_handle_report(handled_at=handled_at, output_dir=output_dir, records=records)
                    click.echo(f"已生成处理报告: {report_path.relative_to(output_dir).as_posix()}")
                    if output_zip:
                        zip_path = writer.write_export_archive(output_dir, output_zip)
                        click.echo(f"已生成压缩包: {zip_path}")
                else:
                    _print_dry_run_summary(records)

    return handle_data


def _handle_default_mode(
    file_paths: list[Path],
    input_dir: Path,
    output_dir: Path,
    handled_at: str,
    write_empty_file: bool,
    dry_run: bool,
    records: list[HandleRecord],
    global_required_models: set[str],
    excluded_biz_ids: set[int],
) -> None:
    """默认处理模式（不按业务拆分）。"""
    in_memory_rows: dict[str, list[RowDict]] = {}
    in_memory_meta: dict[str, tuple[str, str, int]] = {}  # model_label -> (app_label, model_name, input_rows)
    in_memory_started_at: dict[str, float] = {}
    metadata_rows_by_model: dict[str, list[RowDict]] = {}
    metadata_input_rows_by_model: dict[str, list[RowDict]] = {}
    relation_rows_by_model: dict[str, list[RowDict]] = {}
    filtered_metadata_by_model: dict[str, list[RowDict]] | None = None

    if excluded_biz_ids:
        model_file_map: dict[str, Path] = {}
        for file_path in file_paths:
            model_label = reader.infer_model_label_from_path(input_dir, file_path)
            if model_label:
                model_file_map[model_label] = file_path
        for file_path in file_paths:
            model_label = reader.infer_model_label_from_path(input_dir, file_path)
            if not model_label or not model_label.startswith("metadata."):
                continue
            input_rows, processed_rows, _dropped = _load_model_rows(file_path, model_label)
            metadata_rows_by_model[model_label] = processed_rows
            metadata_input_rows_by_model[model_label] = input_rows
        relation_rows_by_model = dict(metadata_rows_by_model)
        for model_label in METADATA_RELATION_EXTRA_MODELS:
            file_path = model_file_map.get(model_label)
            if not file_path:
                continue
            _input_rows, processed_rows, _dropped = _load_model_rows(file_path, model_label)
            relation_rows_by_model[model_label] = processed_rows
        filtered_metadata_by_model = get_global_metadata(
            metadata_rows_by_model,
            excluded_biz_ids,
            biz_tenant_mapping=BIZ_TENANT_ID_MAPPING,
            default_tenant_id=DEFAULT_TARGET_TENANT_ID,
            relation_rows_by_model=relation_rows_by_model,
        )

    for file_path in file_paths:
        model_label = reader.infer_model_label_from_path(input_dir, file_path)
        if not model_label:
            click.echo(f"跳过无法识别的文件: {file_path}")
            continue

        app_label, model_name = model_label.split(".", 1)
        started_at = time.perf_counter()

        if excluded_biz_ids and model_label.startswith("metadata.") and filtered_metadata_by_model is not None:
            input_rows = metadata_input_rows_by_model.get(model_label, [])
            processed_rows = filtered_metadata_by_model.get(model_label, [])
            dropped = len(input_rows) - len(processed_rows)
        else:
            input_rows, processed_rows, dropped = _load_model_rows(file_path, model_label)
            if excluded_biz_ids:
                processed_rows = _exclude_rows_by_biz(processed_rows, model_label, excluded_biz_ids)
                dropped = len(input_rows) - len(processed_rows)
        input_count = len(input_rows)

        # 全局处理依赖的表：先收集到内存
        if model_label in global_required_models:
            in_memory_rows[model_label] = processed_rows
            in_memory_meta[model_label] = (app_label, model_name, input_count)
            in_memory_started_at[model_label] = started_at
            continue

        # 非全局依赖表：直接写出
        if dry_run:
            duration_sec = time.perf_counter() - started_at
            records.append(
                HandleRecord(
                    scope="global",
                    app_label=app_label,
                    model_name=model_name,
                    input_rows=input_count,
                    output_rows=len(processed_rows),
                    filtered_rows=dropped,
                    duration_sec=duration_sec,
                    size_bytes=0,
                )
            )
            click.echo(
                f"[dry-run] 处理完成: {model_label} "
                f"(input={input_count}, output={len(processed_rows)}, filtered={dropped})"
            )
            continue

        file_out, total, size_bytes = writer.write_export_batches(
            model_label=model_label,
            batches=_iter_batches(processed_rows),
            output_dir=output_dir,
            app_label=app_label,
            exported_at=handled_at,
            write_empty_file=write_empty_file,
        )
        duration_sec = time.perf_counter() - started_at
        records.append(
            HandleRecord(
                scope="global",
                app_label=app_label,
                model_name=model_name,
                input_rows=input_count,
                output_rows=total,
                filtered_rows=dropped,
                duration_sec=duration_sec,
                size_bytes=size_bytes,
            )
        )

        if file_out is None:
            click.echo(f"处理完成: {model_label} (output=0) 已跳过生成文件")
        else:
            relative_path = file_out.relative_to(output_dir).as_posix()
            click.echo(f"处理完成: {relative_path} (input={input_count}, output={total})")

    # 执行全局处理
    if in_memory_rows:
        try:
            run_global_pipelines(in_memory_rows)
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc

        # 全局处理执行后，将依赖表的数据最终写出
        for model_label, (app_label, model_name, input_count) in in_memory_meta.items():
            started_at = in_memory_started_at[model_label]
            rows = in_memory_rows.get(model_label, [])
            if dry_run:
                duration_sec = time.perf_counter() - started_at
                records.append(
                    HandleRecord(
                        scope="global",
                        app_label=app_label,
                        model_name=model_name,
                        input_rows=input_count,
                        output_rows=len(rows),
                        filtered_rows=input_count - len(rows),
                        duration_sec=duration_sec,
                        size_bytes=0,
                    )
                )
                click.echo(
                    f"[dry-run] 处理完成: {model_label} "
                    f"(input={input_count}, output={len(rows)}, filtered={input_count - len(rows)})"
                )
                continue

            file_out, total, size_bytes = writer.write_export_batches(
                model_label=model_label,
                batches=_iter_batches(rows),
                output_dir=output_dir,
                app_label=app_label,
                exported_at=handled_at,
                write_empty_file=write_empty_file,
            )
            duration_sec = time.perf_counter() - started_at
            records.append(
                HandleRecord(
                    scope="global",
                    app_label=app_label,
                    model_name=model_name,
                    input_rows=input_count,
                    output_rows=total,
                    filtered_rows=input_count - total,
                    duration_sec=duration_sec,
                    size_bytes=size_bytes,
                )
            )

            if file_out is None:
                click.echo(f"处理完成: {model_label} (output=0) 已跳过生成文件")
            else:
                relative_path = file_out.relative_to(output_dir).as_posix()
                click.echo(f"处理完成: {relative_path} (input={input_count}, output={total})")


def _handle_split_by_biz(
    file_paths: list[Path],
    input_dir: Path,
    model_file_map: dict[str, Path],
    output_dir: Path,
    handled_at: str,
    write_empty_file: bool,
    dry_run: bool,
    records: list[HandleRecord],
    excluded_biz_ids: set[int],
) -> None:
    """按业务拆分数据并写出。"""
    metadata_rows_by_model: dict[str, list[RowDict]] = {}
    for model_label, file_path in model_file_map.items():
        if not model_label.startswith("metadata."):
            continue
        input_rows, processed_rows, _dropped = _load_model_rows(file_path, model_label)
        metadata_rows_by_model[model_label] = processed_rows

    relation_rows_by_model = dict(metadata_rows_by_model)
    extra_rows_by_model: dict[str, list[RowDict]] = {}
    extra_input_rows_by_model: dict[str, list[RowDict]] = {}
    for model_label in METADATA_RELATION_EXTRA_MODELS:
        file_path = model_file_map.get(model_label)
        if not file_path:
            continue
        input_rows, processed_rows, _dropped = _load_model_rows(file_path, model_label)
        relation_rows_by_model[model_label] = processed_rows
        extra_rows_by_model[model_label] = processed_rows
        extra_input_rows_by_model[model_label] = input_rows

    biz_list = get_biz_list_from_spaces(metadata_rows_by_model)
    biz_by_id = {biz.biz_id: biz for biz in biz_list}
    bkcc_biz_list = [biz for biz in biz_list if biz.space_type_id == "bkcc"]
    other_space_list = [biz for biz in biz_list if biz.space_type_id != "bkcc"]
    effective_biz_list = [biz for biz in biz_list if biz.biz_id not in excluded_biz_ids]
    effective_bkcc_list = [biz for biz in bkcc_biz_list if biz.biz_id not in excluded_biz_ids]
    effective_other_space_list = [biz for biz in other_space_list if biz.biz_id not in excluded_biz_ids]
    scope_by_biz: dict[int, str] = {}
    for biz in effective_biz_list:
        scope_by_biz[biz.biz_id] = get_biz_output_dir(output_dir, biz).name

    global_dir = get_global_output_dir(output_dir)
    global_scope = global_dir.name

    # 业务 metadata 数据
    all_biz_ids = {biz.biz_id for biz in biz_list}
    for biz in effective_bkcc_list:
        biz_dir = get_biz_output_dir(output_dir, biz)
        scope = scope_by_biz[biz.biz_id]
        biz_metadata = get_metadata_by_biz(
            metadata_rows_by_model,
            {biz.biz_id},
            biz_tenant_mapping=BIZ_TENANT_ID_MAPPING,
            default_tenant_id=DEFAULT_TARGET_TENANT_ID,
            relation_rows_by_model=relation_rows_by_model,
        )
        _write_scope_models(
            scope=scope,
            data_by_model=biz_metadata,
            output_dir=biz_dir,
            handled_at=handled_at,
            write_empty_file=write_empty_file,
            dry_run=dry_run,
            records=records,
        )
    for biz in effective_other_space_list:
        biz_dir = get_biz_output_dir(output_dir, biz)
        scope = scope_by_biz[biz.biz_id]
        space_metadata = _get_metadata_by_space(metadata_rows_by_model, biz)
        _write_scope_models(
            scope=scope,
            data_by_model=space_metadata,
            output_dir=biz_dir,
            handled_at=handled_at,
            write_empty_file=write_empty_file,
            dry_run=dry_run,
            records=records,
        )

    # 全局 metadata 数据
    global_metadata = get_global_metadata(
        metadata_rows_by_model,
        all_biz_ids,
        biz_tenant_mapping=BIZ_TENANT_ID_MAPPING,
        default_tenant_id=DEFAULT_TARGET_TENANT_ID,
        relation_rows_by_model=relation_rows_by_model,
    )
    if other_space_list:
        global_metadata = _exclude_metadata_by_spaces(global_metadata, other_space_list)
    _write_scope_models(
        scope=global_scope,
        data_by_model=global_metadata,
        output_dir=global_dir,
        handled_at=handled_at,
        write_empty_file=write_empty_file,
        dry_run=dry_run,
        records=records,
    )

    # 非 metadata 数据
    for file_path in file_paths:
        model_label = reader.infer_model_label_from_path(input_dir, file_path)
        if not model_label:
            click.echo(f"跳过无法识别的文件: {file_path}")
            continue
        if model_label.startswith("metadata."):
            continue

        if model_label in extra_rows_by_model:
            input_rows = extra_input_rows_by_model.get(model_label, [])
            processed_rows = extra_rows_by_model[model_label]
        else:
            input_rows, processed_rows, _dropped = _load_model_rows(file_path, model_label)

        input_by_biz, input_global = split_rows_by_biz(input_rows, model_label, biz_list)
        output_by_biz, output_global = split_rows_by_biz(processed_rows, model_label, biz_list)

        for biz_id, rows in output_by_biz.items():
            if biz_id in excluded_biz_ids:
                continue
            biz_info = biz_by_id.get(biz_id)
            if not biz_info:
                continue
            scope = scope_by_biz[biz_id]
            input_count = len(input_by_biz.get(biz_id, []))
            _write_model_rows(
                scope=scope,
                model_label=model_label,
                rows=rows,
                output_dir=get_biz_output_dir(output_dir, biz_info),
                handled_at=handled_at,
                write_empty_file=write_empty_file,
                dry_run=dry_run,
                records=records,
                input_rows=input_count,
            )

        _write_model_rows(
            scope=global_scope,
            model_label=model_label,
            rows=output_global,
            output_dir=global_dir,
            handled_at=handled_at,
            write_empty_file=write_empty_file,
            dry_run=dry_run,
            records=records,
            input_rows=len(input_global),
        )


def _get_metadata_by_space(rows_by_model: dict[str, list[RowDict]], biz_info: BizInfo) -> dict[str, list[RowDict]]:
    """按空间信息筛选 metadata 数据（非 bkcc 空间）。"""
    space_type_id = biz_info.space_type_id
    space_id = biz_info.space_id
    space_uid = biz_info.space_uid
    space_db_id = biz_info.space_db_id

    result: dict[str, list[RowDict]] = {}
    if not space_type_id or not space_id:
        return result

    space_key = (space_type_id, space_id)

    def _filter_by_fields(rows: list[RowDict], field_names: tuple[str, str]) -> list[RowDict]:
        filtered: list[RowDict] = []
        for row in rows:
            if str(row.get(field_names[0])) == space_key[0] and str(row.get(field_names[1])) == space_key[1]:
                filtered.append(row)
        return filtered

    def _filter_by_space_uid(rows: list[RowDict]) -> list[RowDict]:
        return [row for row in rows if str(row.get("space_uid")) == space_uid]

    def _filter_by_id(rows: list[RowDict]) -> list[RowDict]:
        return [row for row in rows if row.get("id") == space_db_id]

    space_rows = rows_by_model.get("metadata.Space", [])
    if space_rows:
        result["metadata.Space"] = _filter_by_id(space_rows)

    for model_label in (
        "metadata.SpaceDataSource",
        "metadata.SpaceResource",
        "metadata.SpaceRelatedStorageInfo",
        "metadata.SpaceStickyInfo",
    ):
        rows = rows_by_model.get(model_label, [])
        if rows:
            result[model_label] = _filter_by_fields(rows, ("space_type_id", "space_id"))

    space_vm_rows = rows_by_model.get("metadata.SpaceVMInfo", [])
    if space_vm_rows:
        result["metadata.SpaceVMInfo"] = _filter_by_fields(space_vm_rows, ("space_type", "space_id"))

    bk_app_space_rows = rows_by_model.get("metadata.BkAppSpaceRecord", [])
    if bk_app_space_rows:
        result["metadata.BkAppSpaceRecord"] = _filter_by_space_uid(bk_app_space_rows)

    return {model_label: rows for model_label, rows in result.items() if rows}


def _exclude_metadata_by_spaces(
    rows_by_model: dict[str, list[RowDict]], biz_list: list[BizInfo]
) -> dict[str, list[RowDict]]:
    """从 metadata 数据中排除指定空间相关数据。"""
    if not biz_list:
        return rows_by_model

    space_keys = {(biz.space_type_id, biz.space_id) for biz in biz_list}
    space_uids = {biz.space_uid for biz in biz_list}
    space_ids = {biz.space_db_id for biz in biz_list}

    def _exclude_by_fields(rows: list[RowDict], field_names: tuple[str, str]) -> list[RowDict]:
        filtered: list[RowDict] = []
        for row in rows:
            key = (str(row.get(field_names[0])), str(row.get(field_names[1])))
            if key not in space_keys:
                filtered.append(row)
        return filtered

    def _exclude_by_space_uid(rows: list[RowDict]) -> list[RowDict]:
        return [row for row in rows if str(row.get("space_uid")) not in space_uids]

    def _exclude_by_id(rows: list[RowDict]) -> list[RowDict]:
        return [row for row in rows if row.get("id") not in space_ids]

    result = dict(rows_by_model)
    if "metadata.Space" in result:
        result["metadata.Space"] = _exclude_by_id(result["metadata.Space"])
    for model_label in (
        "metadata.SpaceDataSource",
        "metadata.SpaceResource",
        "metadata.SpaceRelatedStorageInfo",
        "metadata.SpaceStickyInfo",
    ):
        if model_label in result:
            result[model_label] = _exclude_by_fields(result[model_label], ("space_type_id", "space_id"))
    if "metadata.SpaceVMInfo" in result:
        result["metadata.SpaceVMInfo"] = _exclude_by_fields(result["metadata.SpaceVMInfo"], ("space_type", "space_id"))
    if "metadata.BkAppSpaceRecord" in result:
        result["metadata.BkAppSpaceRecord"] = _exclude_by_space_uid(result["metadata.BkAppSpaceRecord"])

    return result


def _load_model_rows(file_path: Path, model_label: str) -> tuple[list[RowDict], list[RowDict], int]:
    """读取并处理单表数据。"""
    payload = reader.read_export_file(file_path)
    input_rows = payload["data"]
    pipeline = get_table_pipeline(model_label)
    if pipeline:
        processed_rows, dropped = pipeline.process_batch(input_rows, model_label)
    else:
        processed_rows = input_rows
        dropped = 0
    return input_rows, processed_rows, dropped


def _write_scope_models(
    scope: str,
    data_by_model: dict[str, list[RowDict]],
    output_dir: Path,
    handled_at: str,
    write_empty_file: bool,
    dry_run: bool,
    records: list[HandleRecord],
) -> None:
    """将指定 scope 下的模型数据写出。"""
    for model_label, rows in data_by_model.items():
        _write_model_rows(
            scope=scope,
            model_label=model_label,
            rows=rows,
            output_dir=output_dir,
            handled_at=handled_at,
            write_empty_file=write_empty_file,
            dry_run=dry_run,
            records=records,
            input_rows=len(rows),
        )


def _write_model_rows(
    scope: str,
    model_label: str,
    rows: list[RowDict],
    output_dir: Path,
    handled_at: str,
    write_empty_file: bool,
    dry_run: bool,
    records: list[HandleRecord],
    input_rows: int,
) -> None:
    """写出单模型数据并记录统计。"""
    app_label, model_name = model_label.split(".", 1)
    started_at = time.perf_counter()

    if dry_run:
        duration_sec = time.perf_counter() - started_at
        records.append(
            HandleRecord(
                scope=scope,
                app_label=app_label,
                model_name=model_name,
                input_rows=input_rows,
                output_rows=len(rows),
                filtered_rows=input_rows - len(rows),
                duration_sec=duration_sec,
                size_bytes=0,
            )
        )
        click.echo(
            f"[dry-run] 处理完成: {scope}/{model_label} "
            f"(input={input_rows}, output={len(rows)}, filtered={input_rows - len(rows)})"
        )
        return

    file_out, total, size_bytes = writer.write_export_batches(
        model_label=model_label,
        batches=_iter_batches(rows),
        output_dir=output_dir,
        app_label=app_label,
        exported_at=handled_at,
        write_empty_file=write_empty_file,
    )
    duration_sec = time.perf_counter() - started_at
    records.append(
        HandleRecord(
            scope=scope,
            app_label=app_label,
            model_name=model_name,
            input_rows=input_rows,
            output_rows=total,
            filtered_rows=input_rows - total,
            duration_sec=duration_sec,
            size_bytes=size_bytes,
        )
    )

    if file_out is None:
        click.echo(f"处理完成: {scope}/{model_label} (output=0) 已跳过生成文件")
        return
    relative_path = file_out.relative_to(output_dir).as_posix()
    click.echo(f"处理完成: {scope}/{relative_path} (input={input_rows}, output={total})")


def _iter_batches(rows: list[RowDict], batch_size: int = 1000) -> Iterable[list[RowDict]]:
    """将内存数据切分为批次"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")
    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]


def _exclude_rows_by_biz(rows: list[RowDict], model_label: str, excluded_biz_ids: set[int]) -> list[RowDict]:
    """按业务ID排除数据行。

    Args:
        rows: 原始数据行列表。
        model_label: 模型标签（app_label.ModelName）。
        excluded_biz_ids: 需要排除的业务ID集合。

    Returns:
        过滤后的数据行列表。
    """
    if not rows or not excluded_biz_ids:
        return rows
    filtered: list[RowDict] = []
    for row in rows:
        biz_id = get_row_biz_id(row, model_label)
        if biz_id in excluded_biz_ids:
            continue
        filtered.append(row)
    return filtered


def _format_bytes(size_bytes: int) -> str:
    """将字节数格式化为人类可读单位"""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def _write_handle_report(handled_at: str, output_dir: Path, records: list[HandleRecord]) -> Path:
    """写入处理报告"""
    report_path = output_dir / "handle_report.md"

    by_scope: dict[str, list[HandleRecord]] = {}
    total_input_rows = 0
    total_output_rows = 0
    total_filtered_rows = 0
    total_duration_sec = 0.0
    total_size_bytes = 0
    for record in records:
        by_scope.setdefault(record.scope, []).append(record)
        total_input_rows += record.input_rows
        total_output_rows += record.output_rows
        total_filtered_rows += record.filtered_rows
        total_duration_sec += record.duration_sec
        total_size_bytes += record.size_bytes

    lines: list[str] = []
    lines.append("# 处理报告")
    lines.append("")
    lines.append(f"- 处理时间: {handled_at}")
    lines.append(f"- 模型数量: {len(records)}")
    lines.append(f"- 输入数据量: {total_input_rows}")
    lines.append(f"- 输出数据量: {total_output_rows}")
    lines.append(f"- 过滤数据量: {total_filtered_rows}")
    lines.append(f"- 总耗时: {total_duration_sec:.3f} s")
    lines.append(f"- 总文件大小: {_format_bytes(total_size_bytes)}")
    lines.append("")

    for scope in sorted(by_scope.keys()):
        scope_records = by_scope[scope]
        scope_total_input = sum(r.input_rows for r in scope_records)
        scope_total_output = sum(r.output_rows for r in scope_records)
        scope_total_filtered = sum(r.filtered_rows for r in scope_records)
        scope_total_duration = sum(r.duration_sec for r in scope_records)
        scope_total_size = sum(r.size_bytes for r in scope_records)

        lines.append(f"## {scope}")
        lines.append("")

        by_app: dict[str, list[HandleRecord]] = {}
        for record in scope_records:
            by_app.setdefault(record.app_label, []).append(record)

        for app_label in sorted(by_app.keys()):
            app_records = sorted(by_app[app_label], key=lambda r: r.duration_sec, reverse=True)
            app_total_input = sum(r.input_rows for r in app_records)
            app_total_output = sum(r.output_rows for r in app_records)
            app_total_filtered = sum(r.filtered_rows for r in app_records)
            app_total_duration = sum(r.duration_sec for r in app_records)
            app_total_size = sum(r.size_bytes for r in app_records)

            lines.append(f"### {app_label}")
            lines.append("")
            lines.append("| 模型 | 输入 | 输出 | 过滤 | 耗时(s) | 文件大小 |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for record in app_records:
                lines.append(
                    f"| {record.model_name} | {record.input_rows} | {record.output_rows} | "
                    f"{record.filtered_rows} | {record.duration_sec:.3f} | {_format_bytes(record.size_bytes)} |"
                )
            lines.append("")
            lines.append(f"- 小计输入: {app_total_input}")
            lines.append(f"- 小计输出: {app_total_output}")
            lines.append(f"- 小计过滤: {app_total_filtered}")
            lines.append(f"- 小计耗时: {app_total_duration:.3f} s")
            lines.append(f"- 小计文件大小: {_format_bytes(app_total_size)}")
            lines.append("")

        lines.append(f"- Scope 输入: {scope_total_input}")
        lines.append(f"- Scope 输出: {scope_total_output}")
        lines.append(f"- Scope 过滤: {scope_total_filtered}")
        lines.append(f"- Scope 耗时: {scope_total_duration:.3f} s")
        lines.append(f"- Scope 文件大小: {_format_bytes(scope_total_size)}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _print_dry_run_summary(records: list[HandleRecord]) -> None:
    """打印 dry-run 摘要"""
    total_input = sum(r.input_rows for r in records)
    total_output = sum(r.output_rows for r in records)
    total_filtered = sum(r.filtered_rows for r in records)

    click.echo("")
    click.echo("=" * 60)
    click.echo("[dry-run] 处理摘要")
    click.echo("=" * 60)
    click.echo(f"模型数量: {len(records)}")
    click.echo(f"输入总量: {total_input}")
    click.echo(f"输出总量: {total_output}")
    click.echo(f"过滤总量: {total_filtered}")
    click.echo("=" * 60)
