"""避免 Celery 池子进程复用父进程文件日志的缓冲流。"""

from logging.handlers import RotatingFileHandler


_inherited_streams = []


class ForkSafeRotatingFileHandler(RotatingFileHandler):
    """池子进程首次写日志时独立打开文件，保留原有大小轮转规则。"""

    def _at_fork_reinit(self):
        super()._at_fork_reinit()
        stream = getattr(self, "stream", None)
        if stream is not None:
            # 旧流可能继承了已消失线程的锁，不能 flush、close 或触发析构。
            # 保留至池子进程退出，由操作系统回收文件描述符。
            _inherited_streams.append(stream)
            self.stream = None
