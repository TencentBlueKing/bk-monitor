"""文件日志在真实 fork 场景下的缓冲流隔离与轮转兼容性。"""

import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.utils.log_handlers import ForkSafeRotatingFileHandler


_FORK_REPRODUCER = r"""
import io
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from apps.utils.log_handlers import ForkSafeRotatingFileHandler
from logging.handlers import RotatingFileHandler


entered = threading.Event()
release = threading.Event()


class BlockingRaw(io.RawIOBase):
    def __init__(self, filename):
        self.file = open(filename, "ab", buffering=0)

    def writable(self):
        return True

    def seekable(self):
        return True

    def seek(self, *args):
        return self.file.seek(*args)

    def tell(self):
        return self.file.tell()

    def write(self, data):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("parent writer was not released")
        return self.file.write(data)

    def close(self):
        self.file.close()
        super().close()


def record(message):
    return logging.LogRecord("fork-test", logging.INFO, "fork_reproducer", 0, message, (), None)


filename = Path(sys.argv[1])
handler_class = ForkSafeRotatingFileHandler if sys.argv[2] == "safe" else RotatingFileHandler
exit_mode = sys.argv[3] if len(sys.argv) > 3 else "os"
handler = handler_class(filename, maxBytes=1024, backupCount=1, encoding="utf-8")
handler.stream.close()
inherited = io.TextIOWrapper(io.BufferedWriter(BlockingRaw(filename)), encoding="utf-8")
handler.stream = inherited
writer = threading.Thread(target=handler.handle, args=(record("parent"),), daemon=True)
writer.start()
child = None
reaped = False
completed = False
exitcode = None
try:
    if not entered.wait(2):
        raise RuntimeError("parent did not hold the buffered stream lock")
    child = os.fork()
    if child == 0:
        try:
            handler.handle(record("child"))
            handler.close()
            if exit_mode == "sys":
                sys.exit(0)
            os._exit(0)
        except SystemExit:
            raise
        except BaseException:
            os._exit(2)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        waited, status = os.waitpid(child, os.WNOHANG)
        if waited:
            reaped = True
            completed = True
            exitcode = os.waitstatus_to_exitcode(status)
            break
        time.sleep(0.01)
finally:
    if child and not reaped:
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(child, 0)
    unchanged = handler.stream is inherited
    release.set()
    writer.join(2)
    if writer.is_alive():
        raise RuntimeError("parent writer did not finish")
    handler.close()

print(json.dumps({
    "completed": completed,
    "exitcode": exitcode,
    "parent_stream_unchanged": unchanged,
    "contents": filename.read_text(encoding="utf-8"),
}))
"""


class ForkSafeRotatingFileHandlerTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "fork"), "需要 fork 支持")
    def test_child_logs_when_parent_holds_buffered_stream_lock(self):
        result = self._run_fork_reproducer("safe")
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["exitcode"], 0, result)
        self.assertTrue(result["parent_stream_unchanged"], result)
        self.assertEqual(sorted(result["contents"].splitlines()), ["child", "parent"])

    @unittest.skipUnless(hasattr(os, "fork"), "需要 fork 支持")
    def test_child_exits_cleanly_through_python_finalization(self):
        # gunicorn worker 走 sys.exit，退出时模块清理不能卡在继承流的锁上
        result = self._run_fork_reproducer("safe", exit_mode="sys")
        self.assertTrue(result["completed"], result)
        self.assertEqual(result["exitcode"], 0, result)

    def _run_fork_reproducer(self, handler_type, exit_mode="os"):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    textwrap.dedent(_FORK_REPRODUCER),
                    str(Path(directory) / "fork.log"),
                    handler_type,
                    exit_mode,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                self.fail(f"fork 回归子进程超时：{stdout}\n{stderr}")
            self.assertEqual(process.returncode, 0, stderr)
            return json.loads(stdout)

    def test_delayed_stream_stays_unopened_after_fork_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "delayed.log"
            handler = ForkSafeRotatingFileHandler(filename, maxBytes=1024, encoding="utf-8", delay=True)
            try:
                with patch.object(handler, "_open", wraps=handler._open) as open_stream:
                    handler._at_fork_reinit()
                    open_stream.assert_not_called()
                    self.assertFalse(filename.exists())
                    handler.handle(self._record("延迟打开"))
                    open_stream.assert_called_once()
                self.assertEqual(filename.read_text(encoding="utf-8"), "延迟打开\n")
            finally:
                handler.close()

    def test_parent_keeps_size_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "rotation.log"
            handler = ForkSafeRotatingFileHandler(filename, maxBytes=20, backupCount=1, encoding="utf-8")
            try:
                handler.handle(self._record("first-record"))
                handler.handle(self._record("second-record"))
                self.assertEqual(filename.read_text(encoding="utf-8"), "second-record\n")
                self.assertEqual(Path(f"{filename}.1").read_text(encoding="utf-8"), "first-record\n")
            finally:
                handler.close()

    def test_parent_keeps_encoding_error_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "encoding.log"
            handler = ForkSafeRotatingFileHandler(filename, encoding="ascii", errors="backslashreplace")
            try:
                handler.handle(self._record("中文"))
                self.assertEqual(filename.read_bytes(), b"\\u4e2d\\u6587\n")
            finally:
                handler.close()

    def test_all_file_loggers_use_fork_safe_handlers(self):
        # web(gunicorn) 与 celery worker 都会 fork，文件 handler 必须统一替换
        from config.log import get_logging_config_dict

        with tempfile.TemporaryDirectory() as directory:
            config = get_logging_config_dict({"LOG_DIR_PREFIX": directory})
            for name in ("root", "component", "mysql", "celery"):
                with self.subTest(handler=name):
                    self.assertEqual(
                        config["handlers"][name]["class"],
                        "apps.utils.log_handlers.ForkSafeRotatingFileHandler",
                    )
                    self.assertEqual(config["handlers"][name]["maxBytes"], 10 * 1024 * 1024)
                    self.assertEqual(config["handlers"][name]["backupCount"], 5)

    @staticmethod
    def _record(message):
        return logging.LogRecord("handler-test", logging.INFO, __file__, 0, message, (), None)
