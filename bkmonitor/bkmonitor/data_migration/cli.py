"""数据迁移 CLI"""

from __future__ import annotations

import os

import click
import django
import dotenv

from bkmonitor.data_migration.commands.export.command import create_command as create_export_command
from bkmonitor.data_migration.commands.import_.command import create_command as create_import_command

CLI_HELP_TEXT = """\
\b
数据迁移命令入口

\b
注意事项:
  - 该模块会初始化 Django 环境，优先从当前目录加载 `.env`
  - 导入导出均使用 raw SQL，适用于 MySQL 5.7

\b
使用方式:
  - 导出: `python -m bkmonitor.data_migration.cli export --help`
  - 导入: `python -m bkmonitor.data_migration.cli import --help`
"""


def _setup_django() -> None:
    """初始化 Django 环境"""
    dotenv.load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    django.setup()


@click.group(help=CLI_HELP_TEXT)
def cli() -> None:
    _setup_django()


# click.group 装饰器会将 cli 变为 click.Group 实例，类型系统无法准确识别
cli.add_command(create_export_command())  # type: ignore[attr-defined]
cli.add_command(create_import_command())  # type: ignore[attr-defined]

if __name__ == "__main__":
    cli()
