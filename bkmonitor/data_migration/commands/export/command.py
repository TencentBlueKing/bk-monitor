"""导出命令"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click
from django.apps import apps

from ...config import DEFAULT_EXPORT_MODELS, EXCLUDE_EXPORT_MODELS
from ...utils.types import RowDict
from ..handle.handle import get_global_required_models, run_global_pipelines
from . import sql, writer


@dataclass(frozen=True)
class ExportRecord:
    """导出记录"""

    app_label: str
    model_name: str
    rows: int
    filtered_rows: int
    duration_sec: float
    size_bytes: int


def create_command() -> click.Command:
    """创建导出命令"""

    export_help_text = "导出指定 ORM 表数据为 JSON"
    export_epilog_text = """\
\b
输出结构:
  - <out>/<app_label>/<ModelName>.json
  - <out>/export_report.md

\b
模型选择与输出补充:
  - model: 支持 app_label 或 app_label.ModelName
    - 当参数不包含 '.' 时，视为 app_label 并展开为该 app 下所有模型
    - 不传 --model 时使用 DEFAULT_EXPORT_MODELS
    - 默认会排除 EXCLUDE_EXPORT_MODELS
  - out: 目录或 .zip
    - 若为 .zip，会先导出到临时目录后再打包输出

\b
示例:
  - uv run python -m data_migration.cli export --model metadata --out /tmp/export_dir
  - uv run python -m data_migration.cli export --model metadata.ResultTable --out /tmp/export.zip
  - uv run python -m data_migration.cli export --disable-handle --model metadata --out /tmp/export_dir
"""

    @click.command("export", help=export_help_text, epilog=export_epilog_text)  # type: ignore[attr-defined]
    @click.option(
        "--model",
        "models",
        multiple=True,
        help="模型标签，可多次指定",
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
    @click.option(
        "--enable-handle/--disable-handle",
        "enable_handle",
        default=False,
        show_default=True,
        help="是否启用数据处理 pipeline（行级/跨表 handle 逻辑），默认开启",
    )
    def export_data(models: tuple[str, ...], output_path: Path, write_empty_file: bool, enable_handle: bool) -> None:
        """导出数据"""
        model_labels = list(models) if models else list(DEFAULT_EXPORT_MODELS)
        model_labels = _expand_model_labels(model_labels)
        excluded_models = set(_expand_model_labels(EXCLUDE_EXPORT_MODELS))
        model_labels = [label for label in model_labels if label not in excluded_models]
        if not model_labels:
            raise click.ClickException("未指定模型，且默认导出列表为空。")

        global_required_models = get_global_required_models() if enable_handle else set()
        if enable_handle:
            required_but_excluded = global_required_models & excluded_models
            if required_but_excluded:
                required_text = ", ".join(sorted(required_but_excluded))
                raise click.ClickException(f"全局处理依赖的模型被排除: {required_text}")

            missing_required_models = sorted(global_required_models - set(model_labels))
            if missing_required_models:
                model_labels.extend(missing_required_models)

        exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with writer.prepare_output_dir(output_path) as (output_dir, output_zip):
            records: list[ExportRecord] = []
            in_memory_rows: dict[str, list[RowDict]] = {}
            in_memory_started_at: dict[str, float] = {}
            in_memory_meta: dict[str, tuple[str, str]] = {}
            in_memory_sql_stats: dict[str, sql.ExportOrmDataStats] = {}
            in_memory_pre_global_len: dict[str, int] = {}
            for model_label in model_labels:
                model = apps.get_model(model_label)
                if model is None:
                    raise click.ClickException(f"未找到模型: {model_label}")

                app_label = model._meta.app_label
                model_name = model.__name__

                export_stats = sql.ExportOrmDataStats()
                batches = sql.export_orm_data(model_label, stats=export_stats, apply_pipeline=enable_handle)
                started_at = time.perf_counter()
                # 全局处理依赖的表：在表级 pipeline 处理后先收集到内存，待全局处理完成后再落地
                if model_label in global_required_models:
                    rows: list[RowDict] = []
                    for batch in batches:
                        rows.extend(batch)
                    in_memory_rows[model_label] = rows
                    in_memory_pre_global_len[model_label] = len(rows)
                    in_memory_started_at[model_label] = started_at
                    in_memory_meta[model_label] = (app_label, model_name)
                    in_memory_sql_stats[model_label] = export_stats
                    continue

                file_path, total, size_bytes = writer.write_export_batches(
                    model_label=model_label,
                    batches=batches,
                    output_dir=output_dir,
                    app_label=app_label,
                    exported_at=exported_at,
                    write_empty_file=write_empty_file,
                )
                duration_sec = time.perf_counter() - started_at
                records.append(
                    ExportRecord(
                        app_label=app_label,
                        model_name=model_name,
                        rows=total,
                        filtered_rows=export_stats.dropped_rows,
                        duration_sec=duration_sec,
                        size_bytes=size_bytes,
                    )
                )

                if file_path is None:
                    click.echo(f"导出完成: {app_label}.{model_name} (total=0) 已跳过生成文件")
                else:
                    relative_path = file_path.relative_to(output_dir).as_posix()
                    click.echo(f"导出完成: {relative_path} (total={total})")

            if enable_handle and global_required_models:
                # 全局处理跨表处理：只对其 required_models 生效，允许覆盖多表数据
                try:
                    run_global_pipelines(in_memory_rows)
                except RuntimeError as exc:
                    raise click.ClickException(str(exc)) from exc

                # 全局处理执行后，将依赖表的数据最终落地
                for model_label in model_labels:
                    if model_label not in global_required_models:
                        continue
                    app_label, model_name = in_memory_meta[model_label]
                    started_at = in_memory_started_at[model_label]
                    rows = in_memory_rows.get(model_label, [])
                    export_stats = in_memory_sql_stats.get(model_label, sql.ExportOrmDataStats())
                    pre_global_len = in_memory_pre_global_len.get(model_label, len(rows))
                    batches = _iter_batches(rows, batch_size=sql.DEFAULT_BATCH_SIZE)
                    file_path, total, size_bytes = writer.write_export_batches(
                        model_label=model_label,
                        batches=batches,
                        output_dir=output_dir,
                        app_label=app_label,
                        exported_at=exported_at,
                        write_empty_file=write_empty_file,
                    )
                    duration_sec = time.perf_counter() - started_at
                    filtered_by_global = max(0, pre_global_len - len(rows))
                    records.append(
                        ExportRecord(
                            app_label=app_label,
                            model_name=model_name,
                            rows=total,
                            filtered_rows=export_stats.dropped_rows + filtered_by_global,
                            duration_sec=duration_sec,
                            size_bytes=size_bytes,
                        )
                    )

                    if file_path is None:
                        click.echo(f"导出完成: {app_label}.{model_name} (total=0) 已跳过生成文件")
                    else:
                        relative_path = file_path.relative_to(output_dir).as_posix()
                        click.echo(f"导出完成: {relative_path} (total={total})")

            report_path = _write_export_report(exported_at=exported_at, output_dir=output_dir, records=records)
            click.echo(f"已生成导出报告: {report_path.relative_to(output_dir).as_posix()}")
            if output_zip:
                zip_path = writer.write_export_archive(output_dir, output_zip)
                click.echo(f"已生成压缩包: {zip_path}")

    return export_data


def _expand_model_labels(model_labels: Iterable[str]) -> list[str]:
    """展开模型标签，支持 app_label"""
    expanded: list[str] = []
    seen: set[str] = set()
    for label in model_labels:
        if "." in label:
            if label not in seen:
                expanded.append(label)
                seen.add(label)
            continue
        try:
            app_config = apps.get_app_config(label)
        except LookupError as exc:
            raise click.ClickException(f"未找到应用: {label}") from exc
        for model in app_config.get_models():
            model_label = model._meta.label
            if model_label in seen:
                continue
            expanded.append(model_label)
            seen.add(model_label)
    return expanded


def _filter_excluded_models(model_labels: list[str], excluded_labels: Iterable[str]) -> list[str]:
    """过滤被排除的模型标签"""
    excluded = set(_expand_model_labels(excluded_labels))
    return [label for label in model_labels if label not in excluded]


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


def _write_export_report(exported_at: str, output_dir: Path, records: list[ExportRecord]) -> Path:
    """写入导出报告"""
    report_path = output_dir / "export_report.md"

    by_app: dict[str, list[ExportRecord]] = {}
    total_rows = 0
    total_filtered_rows = 0
    total_duration_sec = 0.0
    total_size_bytes = 0
    for record in records:
        by_app.setdefault(record.app_label, []).append(record)
        total_rows += record.rows
        total_filtered_rows += record.filtered_rows
        total_duration_sec += record.duration_sec
        total_size_bytes += record.size_bytes

    lines: list[str] = []
    lines.append("# 导出报告")
    lines.append("")
    lines.append(f"- 导出时间: {exported_at}")
    lines.append(f"- 模型数量: {len(records)}")
    lines.append(f"- 总数据量: {total_rows}")
    lines.append(f"- 总过滤量: {total_filtered_rows}")
    lines.append(f"- 总耗时: {total_duration_sec:.3f} s")
    lines.append(f"- 总文件大小: {_format_bytes(total_size_bytes)}")
    lines.append("")

    for app_label in sorted(by_app.keys()):
        app_records = sorted(by_app[app_label], key=lambda r: r.duration_sec, reverse=True)
        app_total_rows = sum(r.rows for r in app_records)
        app_total_filtered_rows = sum(r.filtered_rows for r in app_records)
        app_total_duration_sec = sum(r.duration_sec for r in app_records)
        app_total_size_bytes = sum(r.size_bytes for r in app_records)

        lines.append(f"## {app_label}")
        lines.append("")
        lines.append("| 模型 | 数据量 | 过滤量 | 耗时(s) | 文件大小 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for record in app_records:
            lines.append(
                f"| {record.model_name} | {record.rows} | {record.filtered_rows} | {record.duration_sec:.3f} | {_format_bytes(record.size_bytes)} |"
            )
        lines.append("")
        lines.append(f"- 小计数据量: {app_total_rows}")
        lines.append(f"- 小计过滤量: {app_total_filtered_rows}")
        lines.append(f"- 小计耗时: {app_total_duration_sec:.3f} s")
        lines.append(f"- 小计文件大小: {_format_bytes(app_total_size_bytes)}")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _iter_batches(rows: list[RowDict], batch_size: int) -> Iterable[list[RowDict]]:
    """将内存数据切分为批次"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")
    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]
