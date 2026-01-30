"""导出文件写入逻辑

设计目标:
    - 流式写入 JSON，避免将整表数据一次性加载到内存
    - 导出文件按 app_label 分目录：`<out>/<app_label>/<ModelName>.json`
    - 默认：若某表导出总量为 0，则跳过生成 JSON 文件（可通过参数控制是否写入空文件）
    - out 支持目录与 .zip：若为 .zip，会在临时目录写入后再打包输出
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from ...utils.types import ExportBatch, ExportPayload


def write_export_batches(
    model_label: str,
    batches: Iterable[ExportBatch],
    output_dir: Path,
    app_label: str,
    exported_at: str,
    write_empty_file: bool = False,
) -> tuple[Path | None, int, int]:
    """按批次流式写入导出文件"""
    model_name = model_label.split(".", 1)[1]
    target_dir = output_dir / app_label
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{model_name}.json"

    total = 0

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        prefix=f"{model_name}.",
        suffix=".json.tmp",
        delete=False,
    )
    temp_path = Path(temp_file.name)
    with temp_file as handle:
        handle.write("{")
        handle.write(f'"model": {json.dumps(model_label)}, ')
        handle.write(f'"exported_at": {json.dumps(exported_at)}, ')
        handle.write('"data": [')
        first = True
        for batch in batches:
            for row in batch:
                if not first:
                    handle.write(", ")
                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        cls=DjangoJSONEncoder,
                        default=_json_default,
                    )
                )
                first = False
                total += 1
        handle.write("], ")
        handle.write('"stats": ' + json.dumps({"total": total}, ensure_ascii=False))
        handle.write("}")

    if total == 0:
        if not write_empty_file:
            temp_path.unlink(missing_ok=True)
            return None, 0, 0
        temp_path.replace(file_path)
        return file_path, 0, file_path.stat().st_size

    temp_path.replace(file_path)
    return file_path, total, file_path.stat().st_size


def write_export_archive(output_dir: Path, output_zip: Path) -> Path:
    """将导出目录压缩为 zip"""
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(output_dir.rglob("*")):
            if not file_path.is_file():
                continue
            arcname = file_path.relative_to(output_dir).as_posix()
            archive.write(file_path, arcname=arcname)
    return output_zip


@contextmanager
def prepare_output_dir(output_path: Path) -> Iterator[tuple[Path, Path | None]]:
    """自动识别输出目录或 zip"""
    if output_path.suffix.lower() != ".zip":
        output_path.mkdir(parents=True, exist_ok=True)
        yield output_path, None
        return
    temp_dir = Path(tempfile.mkdtemp(prefix="data_migration_export_"))
    try:
        yield temp_dir, output_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def write_export_file(payload: ExportPayload, output_dir: Path) -> Path:
    """写入单模型导出文件"""
    model_label = payload["model"]
    app_label, model_name = model_label.split(".", 1)
    target_dir = output_dir / app_label
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{model_name}.json"
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, cls=DjangoJSONEncoder, default=_json_default)
    return file_path


def _json_default(value: Any) -> Any:
    """处理 JSON 序列化的特殊类型"""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
