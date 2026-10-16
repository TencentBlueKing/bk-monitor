from __future__ import annotations

# ---------------------------------------------------------------------------
# V4 批量分片并发
#
# 只服务 V4 Provider 的 chunk 扇出。双栈 pair 并发在 apps.iam.concurrency，
# 不要把 run_pair_concurrently 再放回这个方言模块。
# ---------------------------------------------------------------------------

from collections.abc import Callable, Sequence
from iam_engine.concurrency import map_chunks_concurrently as _map_chunks
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
    return _map_chunks(chunks, worker, bind=bind_current_context, max_workers=max_workers)
