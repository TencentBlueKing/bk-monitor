from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

L = TypeVar("L")
R = TypeVar("R")


class PairExecutor(Protocol):
    """双栈并发的注入点：按传入顺序执行两个任务，并按相同顺序返回结果。

    实现必须传播调用线程的 request / 时区 / OTel context，否则 worker 里打的
    鉴权日志会丢 request_id。项目约定实现是 ``apps.iam.concurrency.run_pair_concurrently``，
    业务模块不要自己 new ThreadPoolExecutor。
    """

    def __call__(
        self,
        left: Callable[[], L],
        right: Callable[[], R],
    ) -> tuple[L, R]: ...
