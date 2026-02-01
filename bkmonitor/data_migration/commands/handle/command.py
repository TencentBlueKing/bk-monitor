"""处理命令"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click

from ...utils.types import RowDict
from ..export import writer
from ..import_ import reader
from .biz_filter import CACHE_SOURCE_TABLES, EXTRA_PRELOAD_MODELS, preload_relation_cache
from .handle import (
    get_global_required_models,
    get_table_pipeline,
    run_global_pipelines,
)


@dataclass(frozen=True)
class HandleRecord:
    """处理记录"""

    app_label: str
    model_name: str
    input_rows: int
    output_rows: int
    filtered_rows: int
    duration_sec: float
    size_bytes: int


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
    def handle_data(input_path: Path, output_path: Path, write_empty_file: bool, dry_run: bool) -> None:
        """处理数据"""
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
                records: list[HandleRecord] = []
                in_memory_rows: dict[str, list[RowDict]] = {}
                in_memory_meta: dict[
                    str, tuple[str, str, int]
                ] = {}  # model_label -> (app_label, model_name, input_rows)
                in_memory_started_at: dict[str, float] = {}

                for file_path in file_paths:
                    model_label = reader.infer_model_label_from_path(input_dir, file_path)
                    if not model_label:
                        click.echo(f"跳过无法识别的文件: {file_path}")
                        continue

                    app_label, model_name = model_label.split(".", 1)
                    started_at = time.perf_counter()

                    # 读取数据
                    payload = reader.read_export_file(file_path)
                    input_rows = payload["data"]
                    input_count = len(input_rows)

                    # 应用表级 pipeline
                    pipeline = get_table_pipeline(model_label)
                    if pipeline:
                        processed_rows, dropped = pipeline.process_batch(input_rows, model_label)
                    else:
                        processed_rows = input_rows
                        dropped = 0

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

                # 写出报告
                if not dry_run:
                    report_path = _write_handle_report(handled_at=handled_at, output_dir=output_dir, records=records)
                    click.echo(f"已生成处理报告: {report_path.relative_to(output_dir).as_posix()}")
                    if output_zip:
                        zip_path = writer.write_export_archive(output_dir, output_zip)
                        click.echo(f"已生成压缩包: {zip_path}")
                else:
                    _print_dry_run_summary(records)

    return handle_data


def _iter_batches(rows: list[RowDict], batch_size: int = 1000) -> Iterable[list[RowDict]]:
    """将内存数据切分为批次"""
    if batch_size <= 0:
        raise ValueError("batch_size 必须大于 0")
    for i in range(0, len(rows), batch_size):
        yield rows[i : i + batch_size]


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

    by_app: dict[str, list[HandleRecord]] = {}
    total_input_rows = 0
    total_output_rows = 0
    total_filtered_rows = 0
    total_duration_sec = 0.0
    total_size_bytes = 0
    for record in records:
        by_app.setdefault(record.app_label, []).append(record)
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

    for app_label in sorted(by_app.keys()):
        app_records = sorted(by_app[app_label], key=lambda r: r.duration_sec, reverse=True)
        app_total_input = sum(r.input_rows for r in app_records)
        app_total_output = sum(r.output_rows for r in app_records)
        app_total_filtered = sum(r.filtered_rows for r in app_records)
        app_total_duration = sum(r.duration_sec for r in app_records)
        app_total_size = sum(r.size_bytes for r in app_records)

        lines.append(f"## {app_label}")
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
