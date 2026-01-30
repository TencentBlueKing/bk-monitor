"""导入文件读取逻辑

输入约定:
    - 支持目录与 .zip
    - 目录会递归读取所有 `*.json`（兼容按 app_label 分目录）
    - .zip 会先解压到临时目录，再按目录方式读取
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ...utils.types import ExportPayload


def read_export_files(input_dir: Path) -> Iterator[ExportPayload]:
    """读取导出目录中的 JSON 文件"""
    for file_path in sorted(input_dir.rglob("*.json")):
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        yield payload


def read_export_archive(input_zip: Path, work_dir: Path) -> Path:
    """解压 zip 并返回目录"""
    with zipfile.ZipFile(input_zip, "r") as archive:
        archive.extractall(work_dir)
    return work_dir


@contextmanager
def prepare_input_dir(input_path: Path) -> Iterator[Path]:
    """自动识别目录或压缩包"""
    if input_path.is_dir():
        yield input_path
        return
    if input_path.suffix.lower() != ".zip":
        raise ValueError(f"不支持的输入路径: {input_path}")
    temp_dir = Path(tempfile.mkdtemp(prefix="data_migration_import_"))
    try:
        read_export_archive(input_path, temp_dir)
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
