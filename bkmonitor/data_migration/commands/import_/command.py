"""导入命令"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import click

from ...config import TABLE_PRIORITY_MAPPING
from . import reader, sql


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
  - uv run python -m data_migration.cli import --input /tmp/export_dir --conflict update
  - uv run python -m data_migration.cli import --input /tmp/export.zip --conflict skip --dry-run
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
            file_paths = reader.iter_export_file_paths(input_dir)
            file_paths.sort(key=lambda file_path: _get_import_sort_key(input_dir, file_path))

            for file_path in file_paths:
                inferred_model_label = reader.infer_model_label_from_path(input_dir, file_path)
                payload = reader.read_export_file(file_path)
                model_label = inferred_model_label or payload["model"]
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


def _get_import_sort_key(input_dir: Path, file_path: Path) -> tuple[int, str, str]:
    """导入文件排序 key

    规则:
        - 优先级越高越先导入（数字越大越先导入）
        - 同优先级按 model_label 升序，保证稳定可复现
    """
    model_label = reader.infer_model_label_from_path(input_dir, file_path) or ""
    priority = TABLE_PRIORITY_MAPPING.get(model_label, 0)
    # Python 默认升序排序，这里将 priority 取负即可实现“高优先级先导入”
    return (-priority, model_label, str(file_path))
