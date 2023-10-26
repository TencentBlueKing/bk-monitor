# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import concurrent.futures
import logging
import os
import signal
import time
from concurrent.futures import Executor, Future
from threading import RLock

from django.db import close_old_connections

logger = logging.getLogger(__name__)


class BeatShutdown(Exception):
    always_raise = True


class MonitorBeater(object):
    """
    任务执行方式：
    dumy: 单进程堵塞式执行，注意该模式可能会让周期任务调度并不是那么精确，但是消耗最小同时最可靠。
    thread: 线程池执行(默认)，注意： 使用线程池可能会比dumy模式小消耗更多的cpu资源，在资源紧张情况下，可以考虑使用dumy模式。
    通过环境变量: MONITOR_BEAT_EXEC_TYPE可以设置执行方式
    """

    def __init__(self, name="monitor_beater", entries=None):
        if entries is None:
            entries = {}
        self.name = name
        self.entries = entries
        self.max_interval = 1
        self.executor = BeaterExecutor(self, exec_type=os.getenv("MONITOR_BEAT_EXEC_TYPE", "thread"))
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)
        self.__shutdown = False

    def shutdown(self, signum, frame):
        self.__shutdown = True
        self.executor.shutdown(True)

    def maybe_due(self, entry):
        """
        是否需要发布任务
        :param entry: schedule
        :return: 下次运行时间
        """
        is_due, next_time_to_run = entry.is_due()
        new_entry = None
        if is_due:
            logger.info(f"{self.display_name} Sending due task {entry.task.__name__} args: {entry.args}")
            self.executor.execute(entry)
            new_entry = entry.next()
        return next_time_to_run, new_entry

    def tick(self):
        """
        单位调度
        """
        remaining_times = []
        entries_temp = {}
        entry_keys = list(self.entries.keys())
        for entry_key in entry_keys:
            try:
                next_time_to_run, new_entry = self.maybe_due(self.entries[entry_key])
                # 由于并发原因，entries 中可能会出现 key 被修改的情况
                # logger.debug(
                #     f"{self.display_name} Ticks runtime key: {entry_key},"
                #     f"values: {self.entries[entry_key].args}, next_time: {next_time_to_run}"
                # )
                if next_time_to_run:
                    remaining_times.append(next_time_to_run)
                if new_entry:
                    entries_temp[entry_key] = new_entry
            except RuntimeError as e:
                logger.exception(f"{self.display_name} Ticks runtime error:{e}, key: {self.entries[entry_key].args}")

        for group_key, entry in entries_temp.items():
            self.entries[group_key] = entry

        return min(remaining_times + [self.max_interval])

    def beater(self, drift=-0.010):
        """
        调度器
        :param drift: 偏移
        """
        logger.info(f"{self.display_name} Starting, load {len(self.entries)} entries")
        for entry in self.entries.values():
            logger.info(f"{self.display_name} loading entry: {entry.task.__name__}({entry.schedule})")
        while not self.__shutdown:
            interval = self.tick()
            interval = interval + drift if interval else interval
            if interval and interval > 0:
                logger.debug(f"{self.display_name} beat: Waking up in {interval}s.")
                time.sleep(interval)
        else:
            raise BeatShutdown(f"{self.display_name} beat shut down now")

    def __str__(self):
        return f"[monitor.beater.{self.name}]({id(self)})"

    @property
    def display_name(self):
        return str(self)


class DummyExecutor(Executor):
    def __init__(self, max_workers):
        self._shutdown = False
        self._shutdownLock = RLock()

    def submit(self, fn, *args, **kwargs):
        with self._shutdownLock:
            if self._shutdown:
                raise RuntimeError("can't schedule new futures after shutdown")

            f = Future()
            try:
                result = fn(*args, **kwargs)
            except BaseException as e:
                f.set_exception(e)
            else:
                f.set_result(result)

            return f

    def shutdown(self, wait=True):
        with self._shutdownLock:
            self._shutdown = True


class BeaterExecutor(object):
    """
    reference: apscheduler
    """

    exec_map = {
        "dumy": DummyExecutor,
        "thread": concurrent.futures.ThreadPoolExecutor,
        # "process": concurrent.futures.ProcessPoolExecutor,
    }

    def __init__(self, beat, max_workers=3, exec_type="dumy"):
        exector_cls = self.exec_map.get(exec_type)
        if not exector_cls:
            raise Exception(f"BeaterExecutor get unaccepted exec_type: {exec_type}")
        self._pool = exector_cls(int(max_workers))
        self.beat = beat
        self._lock = RLock()

    def shutdown(self, wait=True):
        self._pool.shutdown(wait)

    def execute(self, entry):
        with self._lock:
            self._do_submit_job(entry)

    def _do_submit_job(self, entry):
        def callback(f: Future):
            exc, tb = f.exception(), getattr(f.exception(), "__traceback__", None)
            if exc:
                self._run_job_error(exc, tb)
            else:
                self._run_job_success(f.result())

        future: Future = self._pool.submit(run_entry, entry)
        future.add_done_callback(callback)

    def _run_job_error(self, exc, traceback=None):
        exc_info = (exc.__class__, exc, traceback)
        logger.exception(f"{self.beat.display_name} task error: {exc}", exc_info=exc_info)

    def _run_job_success(self, result):
        entry, _, cost = result
        logger.info(f"{self.beat.display_name} task[{entry.task.__name__}] done in {cost}")


def run_entry(entry):
    start = time.time()
    try:
        result = entry.task(*entry.args)
    except Exception as exc:
        raise exc
    finally:
        close_old_connections()
    return entry, result, time.time() - start
