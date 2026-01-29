"""导入命令"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import click

from bkmonitor.data_migration.commands.import_ import reader, sql


def create_command() -> click.Command:
    """创建导入命令"""

    import_help_text = "从导出文件导入 ORM 表数据"
    import_epilog_text = """\
\b
输入说明:
  - input: 目录或 .zip
    - 目录会递归读取 *.json（支持按 app_label 分目录）
    - .zip 会先解压到临时目录再读取

\b
冲突策略:
  - update: 使用 MySQL `ON DUPLICATE KEY UPDATE` 执行 UPSERT
  - skip: 预先读取已存在唯一键集合，仅插入不存在的数据

\b
示例:
  - uv run python -m bkmonitor.data_migration.cli import --input /tmp/export_dir --conflict update
  - uv run python -m bkmonitor.data_migration.cli import --input /tmp/export.zip --conflict skip --dry-run
"""

    @click.command("import", help=import_help_text, epilog=import_epilog_text)  # type: ignore[attr-defined]
    @click.option(
        "--input",
        "input_path",
        required=True,
        type=click.Path(path_type=Path),
        help="输入路径（目录或 .zip）",
    )
    @click.option(
        "--conflict",
        "conflict_strategy",
        type=click.Choice(["update", "skip"], case_sensitive=False),
        default="update",
        show_default=True,
        help="冲突处理策略",
    )
    @click.option("--dry-run", is_flag=True, default=False, help="仅统计不写入")
    def import_data(input_path: Path, conflict_strategy: str, dry_run: bool) -> None:
        """导入数据"""
        strategy = cast(Literal["update", "skip"], conflict_strategy)
        with reader.prepare_input_dir(input_path) as input_dir:
            for payload in reader.read_export_files(input_dir):
                model_label = payload["model"]
                stats = sql.import_orm_data(
                    model_label=model_label,
                    rows=payload["data"],
                    conflict_strategy=strategy,
                    batch_size=sql.DEFAULT_BATCH_SIZE,
                    dry_run=dry_run,
                )
                click.echo(
                    f"导入完成: {model_label} total={stats.total} "
                    f"inserted={stats.inserted} updated={stats.updated} "
                    f"skipped={stats.skipped} failed={stats.failed}"
                )

    return import_data
