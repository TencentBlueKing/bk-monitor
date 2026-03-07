from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from django.apps import apps
from django.db.models import Model

from bkmonitor.data_migrate.constants import DEFAULT_ENCODING, SEQUENCE_FILE_NAME, SEQUENCE_MODEL_SPECS
from bkmonitor.data_migrate.utils import (
    _get_next_pk_by_max,
    _get_reserved_auto_increment_start,
    get_auto_increment_start,
    read_json_file,
    reset_auto_increment_start,
    write_json_file,
)


def _get_sequence_models() -> list[type[Model]]:
    """
    返回用于导出自增游标的固定模型列表。

    支持两种枚举方式：
    - ``app_label``: 自动展开该 app 下全部模型
    - ``app_label.ModelName``: 只保留单个模型
    """
    sequence_models: list[type[Model]] = []
    seen_labels: set[str] = set()

    for model_spec in SEQUENCE_MODEL_SPECS:
        if "." not in model_spec:
            app_config = apps.get_app_config(model_spec)
            app_models = sorted(app_config.get_models(), key=lambda model_cls: model_cls._meta.label_lower)
        else:
            app_models = [apps.get_model(model_spec)]

        for model_cls in app_models:
            model_label = model_cls._meta.label_lower
            if model_label in seen_labels:
                continue
            seen_labels.add(model_label)
            sequence_models.append(model_cls)

    return sequence_models


def _build_sequences_payload_from_models(models: Sequence[type[Model]]) -> dict[str, Any]:
    """
    基于固定模型列表构建顶层自增游标信息。

    这里不依赖业务导出的 fetcher 结果，而是独立按模型清单读取数据库当前状态。
    """
    model_state: dict[str, dict[str, Any]] = {}
    for model_cls in models:
        current_start = get_auto_increment_start(model_cls)
        if current_start is None:
            continue

        next_pk_by_max = _get_next_pk_by_max(model_cls)
        model_state[model_cls._meta.label] = {
            "has_auto_increment_pk": True,
            "current_start": current_start,
            "reserved_start": _get_reserved_auto_increment_start(current_start),
            "exported_max_pk": next_pk_by_max - 1,
        }
    return {"models": model_state}


def _apply_sequences_payload(sequences_payload: dict[str, Any]) -> None:
    """根据导出时记录的游标信息恢复数据库自增游标。"""
    for model_label, state in (sequences_payload.get("models") or {}).items():
        app_label, model_name = model_label.split(".", 1)
        model_cls = apps.get_model(app_label, model_name)

        reserved_start = state.get("reserved_start")
        exported_max_pk = state.get("exported_max_pk")
        target_start = reserved_start
        if isinstance(exported_max_pk, int):
            target_start = max(target_start or 0, exported_max_pk + 1)

        if target_start:
            reset_auto_increment_start(model_cls, start=target_start)


def apply_auto_increment_from_directory(directory_path: str | Path) -> None:
    """
    从导出目录读取 ``sequences.json`` 并恢复自增游标。

    这个动作与数据导入解耦，调用方可以在确认数据导入完成后再单独执行。
    """
    target_directory = Path(directory_path)
    manifest = read_json_file(target_directory / "manifest.json", encoding=DEFAULT_ENCODING)
    sequence_file = manifest.get("sequence_file")
    if not sequence_file:
        return
    sequence_path = target_directory / sequence_file
    if not sequence_path.exists():
        return
    _apply_sequences_payload(read_json_file(sequence_path, encoding=DEFAULT_ENCODING))


def export_auto_increment_to_directory(directory_path: str | Path) -> Path:
    """
    将固定模型列表对应的自增游标信息导出到目录。

    这个动作与业务数据导出解耦，调用方可以按需单独执行。
    """
    target_directory = Path(directory_path)
    target_directory.mkdir(parents=True, exist_ok=True)

    sequence_file_path = target_directory / SEQUENCE_FILE_NAME
    write_json_file(
        sequence_file_path,
        _build_sequences_payload_from_models(_get_sequence_models()),
        encoding=DEFAULT_ENCODING,
    )

    manifest_path = target_directory / "manifest.json"
    if manifest_path.exists():
        manifest = read_json_file(manifest_path, encoding=DEFAULT_ENCODING)
        manifest["sequence_file"] = SEQUENCE_FILE_NAME
        write_json_file(manifest_path, manifest, encoding=DEFAULT_ENCODING)

    return sequence_file_path
