"""避免 fork 出的子进程复用父进程文件日志的缓冲流。"""

from io import BufferedWriter, FileIO, TextIOWrapper
from logging.handlers import RotatingFileHandler


_inherited_streams = []


class ForkSafeRotatingFileHandler(RotatingFileHandler):
    """子进程首次写日志时独立打开文件，保留原有大小轮转规则。

    标准文件流关闭 raw 层即可让 closed 沿 buffer/text 层传播，后续析构直接返回；
    无法安全关闭的流实现保留引用，交由进程退出回收。
    """

    def _at_fork_reinit(self):
        super()._at_fork_reinit()
        stream = getattr(self, "stream", None)
        if stream is None:
            return
        self.stream = None
        # 只识别 CPython 标准文件流，子类或自定义流走下面的兜底路径
        buffer = stream.buffer if type(stream) is TextIOWrapper else None
        raw = buffer.raw if type(buffer) is BufferedWriter else None
        if type(raw) is FileIO and raw.closefd:
            # 关闭 raw 层不触碰缓冲锁，且 closed 会传播到 buffer/text 层，析构时不会重新加锁；
            # 父子进程持有独立的 file 对象副本，这里只影响子进程的 FD。
            try:
                raw.close()
            except OSError:
                pass
            else:
                return
        # 自定义流或关闭失败时保留引用，避免析构重新获取旧缓冲锁。
        _inherited_streams.append(stream)
