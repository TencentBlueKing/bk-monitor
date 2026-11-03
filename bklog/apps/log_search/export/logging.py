"""分片导出日志在状态提交后输出，避免日志阻塞长期占用行锁。"""

from copy import deepcopy

from django.db import transaction


def log_after_commit(log_method, message="", *args, **kwargs):
    # 异常上下文在提交后已失效，带 exc_info 的日志只能同步输出
    if kwargs.get("exc_info") or not transaction.get_connection().in_atomic_block:
        log_method(message, *args, **kwargs)
        return

    snapshot_args = deepcopy(args)
    snapshot_kwargs = deepcopy(kwargs)

    def emit():
        log_method(message, *snapshot_args, **snapshot_kwargs)

    transaction.on_commit(emit, robust=True)


class CommitSafeLogger:
    """
    事务内的状态日志延后到提交后输出，避免日志 I/O 长时间占用行锁。

    非事务场景保持原样输出；exception/critical 等依赖当前异常上下文的接口不透传延迟逻辑。
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
