"""分片导出状态日志的提交后输出。

状态函数都在 transaction.atomic() 内持有行锁。日志一旦阻塞，事务无法提交、行锁不会释放，
调度器的入队更新只能等到锁等待超时，于是单个任务的开销会扩散成整批任务停摆。
把日志挪到提交后，是为了让日志 I/O 不落在持有行锁的时间窗内。
"""

from copy import deepcopy

from django.db import transaction


def log_after_commit(log_method, message="", *args, **kwargs):
    # 异常上下文在提交后已失效，带 exc_info 的日志只能同步输出
    if kwargs.get("exc_info") or not transaction.get_connection().in_atomic_block:
        log_method(message, *args, **kwargs)
        return

    # 提交前冻结参数：失败上下文常在事务内被就地重置
    snapshot_args = deepcopy(args)
    snapshot_kwargs = deepcopy(kwargs)

    def emit():
        log_method(message, *snapshot_args, **snapshot_kwargs)

    transaction.on_commit(emit, robust=True)


class CommitSafeLogger:
    """
    事务内的状态日志延后到提交后输出。

    起因：日志 handler 在 fork 后可能继承已消失线程的缓冲流锁，写入会在 futex 上永久等待。
    该阻塞发生在持有行锁的事务内，导致行锁不释放、并发入队全部锁等待超时，整批任务停在收尾前。

    定位是防御措施，不是业务时序要求：
    - 只用于运维排查日志，审计日志仍需与业务数据同事务写入
    - exception/critical 依赖当前异常上下文，保持同步输出
    - 非事务场景立即输出，不引入额外延迟
    """

    _DEFERRED_METHODS = frozenset({"debug", "info", "warning", "error"})

    def __init__(self, logger):
        self._logger = logger

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        target = getattr(self._logger, name)
        if name not in self._DEFERRED_METHODS:
            return target

        def emit(message="", *args, **kwargs):
            log_after_commit(target, message, *args, **kwargs)

        return emit
