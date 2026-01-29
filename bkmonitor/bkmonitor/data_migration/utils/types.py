"""数据迁移共享类型"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict

RowDict = dict[str, Any]
RowHandlerFn = Callable[[RowDict], RowDict | None]
ExportBatch = list[RowDict]


class ExportPayload(TypedDict):
    """单模型导出结构"""

    model: str
    exported_at: str
    data: list[RowDict]
    stats: dict[str, int]


@dataclass
class ImportStats:
    """导入统计"""

    total: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
