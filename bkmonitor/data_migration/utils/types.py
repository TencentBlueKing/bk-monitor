"""数据迁移共享类型"""

from __future__ import annotations

from collections.abc import Callable
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
