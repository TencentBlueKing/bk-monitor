from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import nullcontext
from functools import partial
from typing import TypeVar

import pytz
from django.utils import timezone
from opentelemetry.context import attach, detach, get_current

from apps.utils.local import activate_request, del_local_param, get_local_param, get_request, set_local_param

T = TypeVar("T")
R = TypeVar("R")
L = TypeVar("L")
_MISSING = object()


def _bind_current_context(func: Callable[[], R]) -> Callable[[], R]:
    """把调用线程的 OTel context、request 和时区绑定到 worker 线程后再执行 func。

    只用于并发分支：串行回退本来就跑在调用线程上，重复绑定只会白白改写线程变量。
    """
    trace_context = get_current()
    request = get_request(peaceful=True)
    time_zone = get_local_param("time_zone")

    def _run() -> R:
        previous_request = get_local_param("request", _MISSING)
        previous_time_zone = get_local_param("time_zone", _MISSING)
        token = attach(trace_context)
        try:
            if request is not None:
                # 不显式回传 request_id，activate_request 会生成新的 uuid 覆盖掉本次请求的 ID
                activate_request(request, getattr(request, "request_id", None))
            if time_zone:
                set_local_param("time_zone", time_zone)
            timezone_context = timezone.override(pytz.timezone(time_zone)) if time_zone else nullcontext()
            with timezone_context:
                return func()
        finally:
            _restore_local_param("request", previous_request)
            _restore_local_param("time_zone", previous_time_zone)
            detach(token)

    return _run


def _restore_local_param(key: str, previous_value: object) -> None:
    """恢复 worker 原有线程变量，避免共享线程池复用时把本次请求上下文带给下一任务。"""

    if previous_value is _MISSING:
        del_local_param(key)
        return
    set_local_param(key, previous_value)


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
