from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")
L = TypeVar("L")


def map_chunks_concurrently(
    chunks: Sequence[T],
    worker: Callable[[T], R],
    *,
    max_workers: int,
) -> list[R]:
    """按输入顺序返回每个 chunk 的 worker 结果。

    max_workers <= 1 时串行执行，便于对照与调试。
    """
    if not chunks:
        return []
    if max_workers <= 1 or len(chunks) == 1:
        return [worker(chunk) for chunk in chunks]

    workers = min(max_workers, len(chunks))
    results: list[R | None] = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_index = {executor.submit(worker, chunk): index for index, chunk in enumerate(chunks)}
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()
    return results  # type: ignore[return-value]


def run_pair_concurrently(
    left: Callable[[], L],
    right: Callable[[], R],
    *,
    max_workers: int = 2,
) -> tuple[L, R]:
    """并行执行两个无参任务，按 (left, right) 顺序返回结果。

    max_workers <= 1 时串行执行，便于对照与调试。
    任一任务抛出的异常会在对应 future.result() 处原样抛出。
    """
    if max_workers <= 1:
        return left(), right()

    with ThreadPoolExecutor(max_workers=2) as executor:
        left_future = executor.submit(left)
        right_future = executor.submit(right)
        return left_future.result(), right_future.result()
