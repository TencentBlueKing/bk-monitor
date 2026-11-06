import os
import sys
import threading
import time
from multiprocessing import Process
from typing import ClassVar

from django.core.management import BaseCommand

from bk_monitor_base.infras.declaratives.controller.detector.base_detector import BaseDetector
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.paas import IS_PAAS3
from bk_monitor_base.infras.process.process_manager import (
    create_daemon_process,
    reset_signal_handlers,
    run_process_monitor_loop,
    setup_signal_handlers,
)

# PaaS2 非 MASTER Detector自杀前休眠时间(秒)
DETECTOR_DURATION_ON_PAAS2 = 24 * 60 * 60  # 24小时


def _run_detect_task(task) -> None:
    """子进程入口函数,重置信号处理器后执行任务

    Args:
        task: 可调用的检测任务
    """
    # 子进程中恢复默认信号处理,避免继承父进程的处理器
    reset_signal_handlers()
    task()


def _should_run_on_current_node() -> bool:
    """检查当前节点是否应该运行检测器

    Returns:
        True 如果应该运行, False 否则
    """
    return IS_PAAS3 or bool(os.getenv("IS_MASTER"))


def _sleep_and_exit() -> None:
    """在非主节点上休眠后退出, 避免僵尸进程或不断重启"""
    logger.info("Detector only runs on master node in PaaS2 environment, sleeping for daily restart")
    time.sleep(DETECTOR_DURATION_ON_PAAS2)
    sys.exit(0)


def _create_detect_process(task) -> Process:
    """创建并启动检测任务的子进程

    Args:
        task: 可调用的检测任务

    Returns:
        已启动的 Process 实例
    """
    process = create_daemon_process(
        target=_run_detect_task,
        args=(task,),
        name=task.__qualname__,
    )
    logger.info("Started detect process pid=%s for task %s", process.pid, task.__qualname__)
    return process


class BaseDetectorCommand(BaseCommand):
    detector: ClassVar[BaseDetector]

    def handle(self, *args, **options) -> None:
        """Django command 入口,启动检测器进程并监控其健康状态"""
        if not _should_run_on_current_node():
            _sleep_and_exit()
            return

        detect_task_list = self.detector.detect_objs
        process_list: list[tuple[Process, object]] = []
        parent_pid = os.getpid()
        shutdown_event = threading.Event()

        # 设置信号处理器
        setup_signal_handlers(
            shutdown_event=shutdown_event,
            parent_pid=parent_pid,
            process_name="Detector",
        )

        # 创建并启动所有检测进程
        for task in detect_task_list:
            process = _create_detect_process(task)
            process_list.append((process, task))

        # 主监控循环: 检测并重启崩溃的进程
        run_process_monitor_loop(
            process_list=process_list,
            process_factory=_create_detect_process,
            shutdown_event=shutdown_event,
            log_prefix="detector",
        )
