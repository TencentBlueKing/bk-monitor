from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

L = TypeVar("L")
R = TypeVar("R")


class PairExecutor(Protocol):
    """按传入顺序执行两个任务，并按相同顺序返回结果。"""

    def __call__(
        self,
        left: Callable[[], L],
        right: Callable[[], R],
    ) -> tuple[L, R]: ...
