from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseDirectoryHandler(ABC):
    """
    目录级数据处理器基类。

    handler 的职责仅限于修改导出目录中的 fixture 文件和 manifest 元数据，
    不参与 ORM 查询、数据库写入或游标恢复。
    """

    name: str = ""

    @abstractmethod
    def get_manifest_payload(self) -> dict[str, Any]:
        """返回写入 manifest 的处理器元数据。"""

    @abstractmethod
    def handle_records(
        self,
        records: list[dict[str, Any]],
        biz_id: int,
        relative_file_path: str,
    ) -> bool:
        """
        原地处理单个文件中的 fixture 记录。

        返回值表示该文件是否发生修改。
        """


class HandlerExecutionError(RuntimeError):
    """handler 执行失败。"""

    def __init__(self, handler_name: str, file_path: Path, reason: str):
        super().__init__(f"handler[{handler_name}] failed for {file_path}: {reason}")
        self.handler_name = handler_name
        self.file_path = file_path
        self.reason = reason
