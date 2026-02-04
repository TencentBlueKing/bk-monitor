"""设置自增起始值命令。

说明:
    - 该命令基于导出阶段生成的 auto_increment_report.json 进行计算
    - 建议在导入前执行，用于预留足够主键空间
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import click
from django.apps import apps
from django.db import connection, models

from ...utils.types import AutoIncrementReport
from ..export import sql
from ..import_ import reader


def create_command() -> click.Command:
    """创建设置自增起始值命令。

    Returns:
        click.Command: Click 命令对象。
    """

    help_text = "根据导出报告设置 MySQL 表自增起始值"
    epilog_text = """\
\b
输入说明:
  - input: 导出目录、导出 .zip 或 auto_increment_report.json 文件
  - 自增起始值使用报告中的 total_rows 计算

\b
示例:
  - uv run python -m data_migration.cli set-auto-increment --input /tmp/export_dir
  - uv run python -m data_migration.cli set-auto-increment --input /tmp/export.zip --dry-run
"""

    @click.command("set-auto-increment", help=help_text, epilog=epilog_text)  # type: ignore[attr-defined]
    @click.option(
        "--input",
        "input_path",
        required=True,
        type=click.Path(path_type=Path),
        help="输入路径（目录、zip 或报告文件）",
    )
    @click.option("--dry-run", is_flag=True, default=False, help="仅输出计划不执行写入")
    def set_auto_increment(input_path: Path, dry_run: bool) -> None:
        """设置自增起始值。

        Args:
            input_path: 报告输入路径（目录/zip/报告文件）。
            dry_run: 是否仅输出计划不执行写入。
        """
        if connection.vendor != "mysql":
            raise click.ClickException("仅支持 MySQL/MariaDB 连接。")
        report = _load_auto_increment_report(input_path)
        for item in report["items"]:
            # 报告中保存的是导出时的模型与数据量信息
            model_label = item["model"]
            model = apps.get_model(model_label)
            if model is None:
                click.echo(f"跳过: 未找到模型 {model_label}")
                continue
            if not _is_auto_increment_model(model):
                click.echo(f"跳过: 非自增主键模型 {model_label}")
                continue

            table_name = model._meta.db_table
            total_rows = int(item.get("total_rows", 0))
            # 基于导出的数据量估算预留自增空间
            recommended = _compute_recommended_auto_increment(total_rows)
            current_auto_increment = sql.get_mysql_auto_increment_value(model) or 0
            # 不回退自增值，仅在需要时向上调整
            target_auto_increment = max(current_auto_increment, recommended)
            if target_auto_increment <= current_auto_increment:
                click.echo(f"无需调整: {model_label} auto_increment={current_auto_increment} rows={total_rows}")
                continue
            if dry_run:
                click.echo(
                    f"[dry-run] {model_label} rows={total_rows} "
                    f"auto_increment={current_auto_increment} -> {target_auto_increment}"
                )
                continue
            _set_auto_increment(table_name, target_auto_increment)
            click.echo(
                f"已设置: {model_label} rows={total_rows} "
                f"auto_increment={current_auto_increment} -> {target_auto_increment}"
            )

    return set_auto_increment


def _compute_recommended_auto_increment(total_rows: int) -> int:
    """根据数据量计算建议的自增起始值。

    Args:
        total_rows: 当前表数据量。

    Returns:
        建议的自增起始值（向上取整后的预留值）。
    """
    # 规则说明：用区间上浮保证预留空间，避免导入后快速达到上限
    if total_rows <= 50_000:
        return 100_000
    if total_rows <= 100_000:
        return 200_000
    if total_rows <= 500_000:
        return 1_000_000
    if total_rows <= 1_000_000:
        return 2_000_000
    if total_rows <= 5_000_000:
        return 10_000_000
    return int(math.ceil(total_rows * 1.5))


def _load_auto_increment_report(input_path: Path) -> AutoIncrementReport:
    """加载自增值报告文件。

    Args:
        input_path: 导出目录、zip 或报告文件路径。

    Returns:
        自增值报告结构。
    """
    # 允许直接传入 auto_increment_report.json
    if input_path.is_file() and input_path.suffix.lower() == ".json":
        report_path = input_path
        return _read_report_file(report_path)
    # 目录/zip 场景下默认读取根目录中的 auto_increment_report.json
    with reader.prepare_input_dir(input_path) as input_dir:
        report_path = input_dir / "auto_increment_report.json"
        if not report_path.exists():
            raise click.ClickException(f"未找到自增值报告: {report_path}")
        return _read_report_file(report_path)


def _read_report_file(report_path: Path) -> AutoIncrementReport:
    """读取自增值报告文件。

    Args:
        report_path: 报告文件路径。

    Returns:
        报告解析结果。
    """
    with report_path.open("r", encoding="utf-8") as handle:
        report: AutoIncrementReport = json.load(handle)
    return report


def _is_auto_increment_model(model: type[models.Model]) -> bool:
    """判断模型是否为自增主键。

    Args:
        model: Django 模型类型。

    Returns:
        是否为自增主键模型。
    """
    pk_field = model._meta.pk
    if pk_field is None:
        return False
    return isinstance(pk_field, models.AutoField | models.BigAutoField | models.SmallAutoField)


def _set_auto_increment(table_name: str, auto_increment: int) -> None:
    """设置表的自增起始值。

    Args:
        table_name: 表名。
        auto_increment: 目标自增起始值。
    """
    quoted = connection.ops.quote_name
    sql_text = f"ALTER TABLE {quoted(table_name)} AUTO_INCREMENT = %s"
    with connection.cursor() as cursor:
        cursor.execute(sql_text, [auto_increment])
