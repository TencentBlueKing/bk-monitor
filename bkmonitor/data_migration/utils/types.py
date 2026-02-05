"""数据迁移共享类型"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

RowDict = dict[str, Any]
RowHandlerFn = Callable[[RowDict], RowDict | None]
ExportBatch = list[RowDict]


class AutoIncrementReportItem(TypedDict):
    """自增值报告条目"""

    model: str
    table: str
    total_rows: int
    auto_increment: int | None


class AutoIncrementReport(TypedDict):
    """自增值报告结构"""

    exported_at: str
    items: list[AutoIncrementReportItem]


class ExportPayload(TypedDict):
    """单模型导出结构"""

    model: str
    exported_at: str
    data: list[RowDict]
    stats: ExportStats


class ExportStats(TypedDict):
    """导出统计信息"""

    total: int
    auto_increment: int | None
