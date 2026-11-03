"""避免 fork 出的子进程复用父进程文件日志的缓冲流。"""

from logging.handlers import RotatingFileHandler


_inherited_streams = []


class ForkSafeRotatingFileHandler(RotatingFileHandler):
    """子进程首次写日志时独立打开文件，保留原有大小轮转规则。"""

    def _at_fork_reinit(self):
        super()._at_fork_reinit()
        stream = getattr(self, "stream", None)
        if stream is not None:
            # 旧流可能继承了已消失线程的锁，不能 flush、close 或触发析构。
            # 保留引用交由进程退出统一回收：billiard 走 os._exit、gunicorn 走 sys.exit，
            # 两条路径都已验证不会阻塞在旧流的锁上。
            _inherited_streams.append(stream)
            self.stream = None
