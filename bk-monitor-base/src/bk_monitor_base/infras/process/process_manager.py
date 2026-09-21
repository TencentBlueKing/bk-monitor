"""进程管理工具模块

提供多进程监控、重启和信号处理的通用功能。
主要用于 Controller 和 Detector 等需要进程管理的场景。
"""

import os
import signal
import sys
import threading
from collections.abc import Callable, Iterable
from multiprocessing import Process
from types import FrameType
from typing import Any

from bk_monitor_base.infras.declaratives.logger import logger

# 进程监控常量
PROCESS_MONITOR_INTERVAL_SECONDS = 5
PROCESS_RESTART_ENABLED = True


def log_process_exit(process: Process, log_prefix: str = "process") -> None:
    """记录进程退出信息

    Args:
        process: 已退出的进程实例
        log_prefix: 日志前缀,用于区分不同类型的进程 (如 "controller", "detector")
    """
    if process.exitcode is None:
        logger.warning(
            "[%s] process pid=%s name=%s exitcode is None, process may still be running",
            log_prefix,
            process.pid,
            process.name,
        )
        return

    if process.exitcode == 0:
        logger.info(
            "[%s] process pid=%s name=%s exited normally",
            log_prefix,
            process.pid,
            process.name,
        )
    elif process.exitcode < 0:
        sig = -process.exitcode
        logger.error(
            "[%s] process pid=%s name=%s killed by signal SIG%s",
            log_prefix,
            process.pid,
            process.name,
            sig,
        )
    else:
        logger.error(
            "[%s] process pid=%s name=%s exited abnormally with code %s",
            log_prefix,
            process.pid,
            process.name,
            process.exitcode,
        )


def create_daemon_process(
    target: Callable[..., object],
    args: Iterable[Any] = (),
    name: str | None = None,
) -> Process:
    """创建并启动守护进程

    Args:
        target: 进程要执行的目标函数
        args: 传递给目标函数的参数
        name: 进程名称

    Returns:
        已启动的 Process 实例
    """
    process = Process(
        target=target,
        args=args,
        name=name,
        daemon=True,
    )
    process.start()
    return process


def monitor_and_restart_processes(
    process_list: list[tuple[Process, Any]],
    process_factory: Callable[[Any], Process],
    log_prefix: str = "process",
    restart_enabled: bool = PROCESS_RESTART_ENABLED,
) -> None:
    """监控进程列表,重启崩溃的进程

    Args:
        process_list: (进程, 上下文) 元组列表,会就地修改
        process_factory: 创建新进程的工厂函数,接收上下文参数
        log_prefix: 日志前缀
        restart_enabled: 是否启用自动重启
    """
    for idx, (process, context) in enumerate(process_list[:]):
        if process.is_alive():
            continue

        # 记录进程退出状态
        log_process_exit(process, log_prefix)

        # 重启进程
        if restart_enabled:
            process_list.pop(idx)
            new_process = process_factory(context)
            process_list.append((new_process, context))
            logger.info(
                "[%s] restarted process pid=%s name=%s",
                log_prefix,
                new_process.pid,
                new_process.name,
            )


def setup_signal_handlers(
    parent_pid: int,
    shutdown_event: threading.Event,
    process_name: str = "process",
) -> None:
    """设置信号处理器,用于优雅关闭进程

    Args:
        parent_pid: 父进程 PID,用于避免子进程响应信号
        shutdown_event: 线程事件对象,用于通知主线程
        process_name: 进程名称,用于日志输出
    """

    def signal_handler(signum: int, frame: FrameType | None) -> None:
        """处理终止信号,优雅地关闭所有子进程"""
        if os.getpid() != parent_pid:
            return
        if shutdown_event:
            shutdown_event.set()
        logger.info("%s received signal %s, shutting down gracefully", process_name, signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def reset_signal_handlers() -> None:
    """重置信号处理器为默认行为

    在子进程中调用,避免继承父进程的信号处理器
    """
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)


def run_process_monitor_loop(
    process_list: list[tuple[Process, Any]],
    process_factory: Callable[[Any], Process],
    shutdown_event: threading.Event,
    log_prefix: str = "process",
    monitor_interval: int = PROCESS_MONITOR_INTERVAL_SECONDS,
) -> None:
    """运行进程监控主循环

    Args:
        process_list: (进程, 上下文) 元组列表
        process_factory: 创建新进程的工厂函数
        shutdown_event: 关闭事件
        log_prefix: 日志前缀
        monitor_interval: 监控间隔(秒)
    """
    while not shutdown_event.is_set():
        if shutdown_event.wait(timeout=monitor_interval):
            break

        monitor_and_restart_processes(
            process_list=process_list,
            process_factory=process_factory,
            log_prefix=log_prefix,
        )
