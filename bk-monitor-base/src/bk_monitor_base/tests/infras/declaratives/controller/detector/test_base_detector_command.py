"""BaseDetectorCommand 单元测试"""

import logging
import multiprocessing
import os
import threading
import time
from multiprocessing import Process
from unittest.mock import MagicMock, Mock, call

import pytest

from bk_monitor_base.infras.declaratives.controller.detector.base_detector import BaseDetector
from bk_monitor_base.infras.declaratives.controller.detector.base_detector_command import (
    DETECTOR_DURATION_ON_PAAS2,
    BaseDetectorCommand,
    _run_detect_task,
    _should_run_on_current_node,
    _sleep_and_exit,
)

# 非 默认 fork 模式的 multiprocessing 有限制,某些测试需要跳过
IS_NON_FORK_MULTIPROCESSING = multiprocessing.get_start_method() != "fork"


def _dummy_detect_task():
    """测试用的检测任务"""
    time.sleep(0.1)


def _failing_detect_task():
    """测试用的失败任务"""
    raise RuntimeError("Detect task failed")


class TestRunDetectTask:
    """_run_detect_task 函数测试"""

    @pytest.mark.skipif(IS_NON_FORK_MULTIPROCESSING, reason="Non-fork multiprocessing signal handling differs")
    def test_resets_signal_handlers(self, mocker):
        """测试重置信号处理器"""
        # Arrange
        mock_reset = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.reset_signal_handlers"
        )
        mock_task = Mock()

        # Act
        _run_detect_task(mock_task)

        # Assert
        mock_reset.assert_called_once()
        mock_task.assert_called_once()

    def test_executes_task(self, mocker):
        """测试执行任务"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.reset_signal_handlers"
        )
        mock_task = Mock()

        # Act
        _run_detect_task(mock_task)

        # Assert
        mock_task.assert_called_once()


class TestShouldRunOnCurrentNode:
    """_should_run_on_current_node 函数测试"""

    def test_returns_true_in_paas3(self, mocker):
        """测试在 PaaS3 环境返回 True"""
        # Arrange
        mocker.patch("bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.IS_PAAS3", True)

        # Act
        result = _should_run_on_current_node()

        # Assert
        assert result is True

    def test_returns_true_when_is_master_set(self, mocker):
        """测试设置 IS_MASTER 环境变量时返回 True"""
        # Arrange
        mocker.patch("bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.IS_PAAS3", False)
        mocker.patch.dict(os.environ, {"IS_MASTER": "1"})

        # Act
        result = _should_run_on_current_node()

        # Assert
        assert result is True

    def test_returns_false_when_not_master(self, mocker):
        """测试非主节点时返回 False"""
        # Arrange
        mocker.patch("bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.IS_PAAS3", False)
        mocker.patch.dict(os.environ, {}, clear=True)

        # Act
        result = _should_run_on_current_node()

        # Assert
        assert result is False


class TestSleepAndExit:
    """_sleep_and_exit 函数测试"""

    def test_logs_message_and_exits(self, mocker, caplog):
        """测试记录日志并退出"""
        # Arrange
        caplog.set_level(logging.INFO)
        mock_sleep = mocker.patch("time.sleep")
        mock_exit = mocker.patch("sys.exit")

        # Act
        _sleep_and_exit()

        # Assert
        assert "Detector only runs on master node" in caplog.text
        mock_sleep.assert_called_once_with(DETECTOR_DURATION_ON_PAAS2)
        mock_exit.assert_called_once_with(0)


class TestBaseDetectorCommandHandle:
    """BaseDetectorCommand.handle 方法测试"""

    def test_exits_when_not_master_node(self, mocker):
        """测试非主节点时退出"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._should_run_on_current_node",
            return_value=False,
        )
        mock_sleep_exit = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._sleep_and_exit"
        )

        class TestDetector(BaseDetector):
            detect_objs = []

        class TestCommand(BaseDetectorCommand):
            detector = TestDetector()

        command = TestCommand()

        # Act
        command.handle()

        # Assert
        mock_sleep_exit.assert_called_once()

    def test_creates_processes_for_all_detect_tasks(self, mocker):
        """测试为所有检测任务创建进程"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._should_run_on_current_node",
            return_value=True,
        )

        task1 = Mock(__qualname__="Task1")
        task2 = Mock(__qualname__="Task2")

        class TestDetector(BaseDetector):
            detect_objs = [task1, task2]

        class TestCommand(BaseDetectorCommand):
            detector = TestDetector()

        command = TestCommand()

        mock_processes = []

        def mock_create_process(task):
            mock_proc = MagicMock(spec=Process)
            mock_proc.is_alive.return_value = False
            mock_proc.exitcode = 0
            mock_proc.pid = len(mock_processes) + 1000
            mock_proc.name = task.__qualname__
            mock_processes.append(mock_proc)
            return mock_proc

        mock_create = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._create_detect_process",
            side_effect=mock_create_process,
        )
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.setup_signal_handlers"
        )
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.run_process_monitor_loop"
        )

        # Act
        command.handle()

        # Assert
        assert mock_create.call_count == 2
        assert mock_create.call_args_list[0] == call(task1)
        assert mock_create.call_args_list[1] == call(task2)

    def test_sets_up_signal_handlers(self, mocker):
        """测试设置信号处理器"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._should_run_on_current_node",
            return_value=True,
        )

        class TestDetector(BaseDetector):
            detect_objs = [Mock(__qualname__="Task1")]

        class TestCommand(BaseDetectorCommand):
            detector = TestDetector()

        command = TestCommand()
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._create_detect_process",
            return_value=MagicMock(spec=Process),
        )

        mock_setup_signals = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.setup_signal_handlers"
        )
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.run_process_monitor_loop"
        )

        # Act
        command.handle()

        # Assert
        mock_setup_signals.assert_called_once()
        call_kwargs = mock_setup_signals.call_args[1]
        assert "shutdown_event" in call_kwargs
        assert "parent_pid" in call_kwargs
        assert call_kwargs["parent_pid"] == os.getpid()
        assert call_kwargs["process_name"] == "Detector"

    def test_runs_monitor_loop(self, mocker):
        """测试运行监控循环"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._should_run_on_current_node",
            return_value=True,
        )

        class TestDetector(BaseDetector):
            detect_objs = [Mock(__qualname__="Task1")]

        class TestCommand(BaseDetectorCommand):
            detector = TestDetector()

        command = TestCommand()
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._create_detect_process",
            return_value=MagicMock(spec=Process),
        )
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.setup_signal_handlers"
        )

        mock_run_loop = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.run_process_monitor_loop"
        )

        # Act
        command.handle()

        # Assert
        mock_run_loop.assert_called_once()
        call_kwargs = mock_run_loop.call_args[1]
        assert "process_list" in call_kwargs
        assert "process_factory" in call_kwargs
        assert "shutdown_event" in call_kwargs
        assert call_kwargs["log_prefix"] == "detector"


class TestBaseDetectorCommandCreateDetectProcess:
    """BaseDetectorCommand._create_detect_process 方法测试"""

    def test_creates_daemon_process_with_correct_params(self, mocker, caplog):
        """测试创建守护进程并传入正确参数"""
        # Arrange

        task = Mock(__qualname__="TestTask")

        mock_process = MagicMock(spec=Process)
        mock_process.pid = 12345
        mock_process.name = "TestTask"

        mock_create_daemon = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.create_daemon_process",
            return_value=mock_process,
        )

        # Act
        from bk_monitor_base.infras.declaratives.controller.detector.base_detector_command import _create_detect_process

        result = _create_detect_process(task)

        # Assert
        mock_create_daemon.assert_called_once()
        call_kwargs = mock_create_daemon.call_args[1]
        assert call_kwargs["target"] == _run_detect_task
        assert call_kwargs["args"] == (task,)
        assert call_kwargs["name"] == "TestTask"
        assert result == mock_process

    def test_logs_process_creation(self, mocker, caplog):
        """测试记录进程创建日志"""
        # Arrange
        caplog.set_level(logging.INFO)

        task = Mock(__qualname__="TestTask")

        mock_process = MagicMock(spec=Process)
        mock_process.pid = 12345

        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.create_daemon_process",
            return_value=mock_process,
        )

        # Act
        from bk_monitor_base.infras.declaratives.controller.detector.base_detector_command import _create_detect_process

        _create_detect_process(task)

        # Assert
        assert "Started detect process" in caplog.text
        assert "12345" in caplog.text
        assert "TestTask" in caplog.text


class TestBaseDetectorCommandIntegration:
    """BaseDetectorCommand 集成测试"""

    @pytest.mark.skipif(IS_NON_FORK_MULTIPROCESSING, reason="Non-fork multiprocessing differs significantly")
    def test_full_lifecycle_with_mocked_tasks(self, mocker):
        """测试完整生命周期(使用 mock 任务)"""
        # Arrange
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command._should_run_on_current_node",
            return_value=True,
        )

        task_executed = threading.Event()

        def test_task():
            task_executed.set()
            time.sleep(0.1)

        class TestDetector(BaseDetector):
            detect_objs = [test_task]

        class TestCommand(BaseDetectorCommand):
            detector = TestDetector()

        command = TestCommand()

        # Mock run_process_monitor_loop to exit after a short time
        def mock_run_loop(*args, **kwargs):
            time.sleep(0.2)
            kwargs["shutdown_event"].set()

        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.detector.base_detector_command.run_process_monitor_loop",
            side_effect=mock_run_loop,
        )

        # Act
        command.handle()

        # Assert - command completed without errors
        # In real scenario, task would be executed in subprocess
