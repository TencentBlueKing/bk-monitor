"""业务数据拆分工具模块。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from data_migration.utils.types import RowDict

from .biz_filter import GLOBAL_TABLES, get_row_biz_id


@dataclass(frozen=True)
class BizInfo:
    """业务信息。"""

    biz_id: int
    space_name: str
    space_type_id: str
    space_id: str
    space_db_id: int
    space_uid: str


def get_biz_list_from_spaces(rows_by_model: dict[str, list[RowDict]]) -> list[BizInfo]:
    """从 Space 数据获取业务列表。

    Args:
        rows_by_model: 模型数据映射。

    Returns:
        业务信息列表。
    """
    spaces = rows_by_model.get("metadata.Space", [])
    if not spaces:
        return []
    biz_map: dict[int, BizInfo] = {}
    for row in spaces:
        space_type_id = _normalize_str(row.get("space_type_id"))
        if not space_type_id:
            continue
        space_id = _normalize_str(row.get("space_id"))
        if not space_id:
            continue
        space_db_id = _normalize_int(row.get("id"))
        if space_type_id == "bkcc":
            biz_id = _normalize_int(space_id)
        else:
            biz_id = -space_db_id if space_db_id is not None else None
        if biz_id is None:
            continue
        space_name = _normalize_str(row.get("space_name")) or f"biz_{biz_id}"
        if biz_id not in biz_map:
            space_uid = f"{space_type_id}__{space_id}"
            biz_map[biz_id] = BizInfo(
                biz_id=biz_id,
                space_name=space_name,
                space_type_id=space_type_id,
                space_id=space_id,
                space_db_id=space_db_id or 0,
                space_uid=space_uid,
            )
    return [biz_map[biz_id] for biz_id in sorted(biz_map.keys())]


def split_rows_by_biz(
    rows: list[RowDict],
    model_label: str,
    biz_list: list[BizInfo],
    global_tables: set[str] | None = None,
) -> tuple[dict[int, list[RowDict]], list[RowDict]]:
    """将数据按业务拆分。

    Args:
        rows: 原始数据行列表。
        model_label: 模型标签（app_label.ModelName）。
        biz_list: 业务列表。
        global_tables: 全局表集合（若为空则使用内置 GLOBAL_TABLES）。

    Returns:
        (业务数据映射, 全局数据)。
    """
    if not rows:
        return {}, []

    if global_tables is None:
        global_tables = GLOBAL_TABLES

    if model_label in global_tables:
        return {}, list(rows)

    biz_id_set = {biz.biz_id for biz in biz_list}
    rows_by_biz: dict[int, list[RowDict]] = {}
    global_rows: list[RowDict] = []
    for row in rows:
        biz_id = get_row_biz_id(row, model_label)
        if biz_id in biz_id_set:
            rows_by_biz.setdefault(biz_id, []).append(row)
        else:
            global_rows.append(row)
    return rows_by_biz, global_rows


def get_biz_output_dir(output_dir: Path, biz_info: BizInfo) -> Path:
    """获取业务输出目录。

    Args:
        output_dir: 根输出目录。
        biz_info: 业务信息。

    Returns:
        业务输出目录路径。
    """
    safe_name = _sanitize_dir_name(biz_info.space_name)
    return output_dir / f"{safe_name}({biz_info.biz_id})"


def get_global_output_dir(output_dir: Path) -> Path:
    """获取全局输出目录。"""
    return output_dir / "global"


def _normalize_int(value: object) -> int | None:
    """将值标准化为 int。"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _normalize_str(value: object) -> str | None:
    """将值标准化为 str。"""
    if value is None:
        return None
    return str(value)


def _sanitize_dir_name(name: str) -> str:
    """清理目录名，避免非法路径字符。"""
    normalized = re.sub(r"[\\/]+", "_", name).strip()
    return normalized or "biz"
