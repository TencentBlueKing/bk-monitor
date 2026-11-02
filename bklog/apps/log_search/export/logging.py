"""分片导出日志在状态提交后输出，避免日志阻塞长期占用行锁。"""

from copy import deepcopy

from django.db import transaction


def log_after_commit(log_method, message, *args):
    if not transaction.get_connection().in_atomic_block:
        log_method(message, *args)
        return

    snapshot_args = deepcopy(args)

    def emit():
        log_method(message, *snapshot_args)

    transaction.on_commit(emit, robust=True)
