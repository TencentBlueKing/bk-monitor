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


def iter_export_file_paths(input_dir: Path) -> list[Path]:
    """列出导出目录下的 JSON 文件路径

    说明:
        - 默认按路径排序，保证结果稳定可复现
        - 仅返回路径，不会读取文件内容
    """
    return sorted(input_dir.rglob("*.json"))


def infer_model_label_from_path(input_dir: Path, file_path: Path) -> str | None:
    """从导出目录结构推导 model_label

    约定:
        - 导出结构为 `<out>/<app_label>/<ModelName>.json`
        - 递归读取场景下，也允许 `<out>/<app_label>/.../<ModelName>.json`

    Args:
        input_dir: 导入目录根路径
        file_path: JSON 文件路径

    Returns:
        model_label
        - 解析成功返回 `app_label.ModelName`
        - 无法解析返回 None
    """
    try:
        relative = file_path.relative_to(input_dir)
    except ValueError:
        return None

    if len(relative.parts) < 2:
        return None

    app_label = relative.parts[0]
    model_name = file_path.stem
    if not app_label or not model_name:
        return None
    return f"{app_label}.{model_name}"


def read_export_file(file_path: Path) -> ExportPayload:
    """读取单个导出 JSON 文件"""
    with file_path.open("r", encoding="utf-8") as handle:
        payload: ExportPayload = json.load(handle)
    return payload


def read_export_files(input_dir: Path) -> Iterator[ExportPayload]:
    """读取导出目录中的 JSON 文件"""
    for file_path in iter_export_file_paths(input_dir):
        yield read_export_file(file_path)


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
