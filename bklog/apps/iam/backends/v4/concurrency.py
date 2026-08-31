from __future__ import annotations

# ---------------------------------------------------------------------------
# V4 批量分片并发
#
# 只服务 V4 Provider 的 chunk 扇出。双栈 pair 并发在 apps.iam.concurrency，
# 不要把 run_pair_concurrently 再放回这个方言模块。
# ---------------------------------------------------------------------------

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import TypeVar

from apps.iam.concurrency import bind_current_context

T = TypeVar("T")
R = TypeVar("R")


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
        future_to_index = {
            executor.submit(bind_current_context(partial(worker, chunk))): index for index, chunk in enumerate(chunks)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()
    return results  # type: ignore[return-value]
