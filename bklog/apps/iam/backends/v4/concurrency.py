from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from typing import TypeVar

import pytz
from django.utils import timezone
from opentelemetry.context import attach, detach, get_current

from apps.utils.local import activate_request, get_local_param, get_request, set_local_param

T = TypeVar("T")
R = TypeVar("R")
L = TypeVar("L")


def _bind_current_context(func: Callable[[], R]) -> Callable[[], R]:
    """把调用线程的 OTel context、request 和时区绑定到 worker 线程后再执行 func。

    只用于并发分支：串行回退本来就跑在调用线程上，重复绑定只会白白改写线程变量。
    """
    trace_context = get_current()
    request = get_request(peaceful=True)
    time_zone = get_local_param("time_zone")

    def _run() -> R:
        token = attach(trace_context)
        try:
            if request is not None:
                # 不显式回传 request_id，activate_request 会生成新的 uuid 覆盖掉本次请求的 ID
                activate_request(request, getattr(request, "request_id", None))
            if time_zone:
                set_local_param("time_zone", time_zone)
                timezone.activate(pytz.timezone(time_zone))
            return func()
        finally:
            detach(token)

    return _run


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
            executor.submit(_bind_current_context(partial(worker, chunk))): index for index, chunk in enumerate(chunks)
        }
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
        left_future = executor.submit(_bind_current_context(left))
        right_future = executor.submit(_bind_current_context(right))
        return left_future.result(), right_future.result()
