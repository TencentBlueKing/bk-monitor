"""BaseController 单元测试"""

import logging
import multiprocessing
import os
import time
import uuid
from multiprocessing import Process
from typing import ClassVar
from unittest.mock import MagicMock, Mock, call

import pytest

from bk_monitor_base.infras.declaratives.controller.base_controller import BaseController
from bk_monitor_base.infras.declaratives.definitions import ApiVersion, Kind, Resource, ResourceAction, Spec

# 非 默认 fork 模式的 multiprocessing 有限制,某些测试需要跳过
IS_NON_FORK_MULTIPROCESSING = multiprocessing.get_start_method() != "fork"


class TestResource(Resource):
    """测试用的 Resource 类"""

    class Spec(Spec):
        """测试资源的 Spec"""

        value: int = 0

    kind: ClassVar[Kind] = Kind("TestResource")
    api_version: ClassVar[ApiVersion] = ApiVersion("v1")
    spec: Spec = Spec()

    class Config:
        arbitrary_types_allowed = True


class TestController(BaseController):
    """测试用的 Controller 子类"""

    controller_name = "TestController"
    handles = {}


def _dummy_watch_task(topic: str):
    """测试用的 watch 任务"""
    time.sleep(0.1)


class TestBaseControllerWatchProcess:
    """BaseController.watch_process 方法测试"""

    def test_no_topics_warning(self, mocker, caplog):
        """测试没有 topic 时输出警告"""
        # Arrange
        controller = TestController()
        mocker.patch.object(controller, "get_kafka_topics", return_value=[])

        # Act
        controller.watch_process()

        # Assert
        assert "has no topics to watch" in caplog.text
        assert "TestController" in caplog.text

    @pytest.mark.skipif(IS_NON_FORK_MULTIPROCESSING, reason="Non-fork multiprocessing signal handling differs")
    def test_creates_process_for_each_topic(self, mocker):
        """测试为每个 topic 创建进程"""
        # Arrange
        controller = TestController()

        topics = ["topic1", "topic2", "topic3"]
        mocker.patch.object(controller, "get_kafka_topics", return_value=topics)

        # Mock process creation
        mock_processes = []

        def mock_create(topic):
            mock_proc = MagicMock(spec=Process)
            mock_proc.is_alive.return_value = False
            mock_proc.exitcode = 0
            mock_proc.pid = len(mock_processes) + 1000
            mock_proc.name = f"{topic}-Controller"
            mock_processes.append(mock_proc)
            return mock_proc

        mocker.patch.object(controller, "_create_watch_process", side_effect=mock_create)

        # Mock run_process_monitor_loop to exit immediately
        mocker.patch("bk_monitor_base.infras.declaratives.controller.base_controller.run_process_monitor_loop")

        # Act
        controller.watch_process()

        # Assert
        assert len(mock_processes) == 3
        assert controller._create_watch_process.call_count == 3
        for i, topic in enumerate(topics):
            assert controller._create_watch_process.call_args_list[i] == call(topic)

    def test_sets_up_signal_handlers(self, mocker):
        """测试设置信号处理器"""
        # Arrange
        controller = TestController()
        mocker.patch.object(controller, "get_kafka_topics", return_value=["topic1"])
        mocker.patch.object(controller, "_create_watch_process", return_value=MagicMock(spec=Process))

        mock_setup_signals = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.setup_signal_handlers"
        )
        mocker.patch("bk_monitor_base.infras.declaratives.controller.base_controller.run_process_monitor_loop")

        # Act
        controller.watch_process()

        # Assert
        mock_setup_signals.assert_called_once()
        call_kwargs = mock_setup_signals.call_args[1]
        assert "shutdown_event" in call_kwargs
        assert "parent_pid" in call_kwargs
        assert call_kwargs["parent_pid"] == os.getpid()
        assert "TestController" in call_kwargs["process_name"]

    def test_runs_monitor_loop(self, mocker):
        """测试运行监控循环"""
        # Arrange
        controller = TestController()
        mocker.patch.object(controller, "get_kafka_topics", return_value=["topic1"])
        mocker.patch.object(controller, "_create_watch_process", return_value=MagicMock(spec=Process))
        mocker.patch("bk_monitor_base.infras.declaratives.controller.base_controller.setup_signal_handlers")

        mock_run_loop = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.run_process_monitor_loop"
        )

        # Act
        controller.watch_process()

        # Assert
        mock_run_loop.assert_called_once()
        call_kwargs = mock_run_loop.call_args[1]
        assert "process_list" in call_kwargs
        assert "process_factory" in call_kwargs
        assert "shutdown_event" in call_kwargs
        assert call_kwargs["log_prefix"] == "controller"


class TestBaseControllerCreateWatchProcess:
    """BaseController._create_watch_process 方法测试"""

    def test_creates_daemon_process_with_correct_params(self, mocker, caplog):
        """测试创建守护进程并传入正确参数"""
        # Arrange
        controller = TestController()
        topic = "test-topic"

        mock_process = MagicMock(spec=Process)
        mock_process.pid = 12345
        mock_process.name = f"{topic}-Controller"

        mock_create_daemon = mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.create_daemon_process",
            return_value=mock_process,
        )

        # Act
        result = controller._create_watch_process(topic)

        # Assert
        mock_create_daemon.assert_called_once()
        call_kwargs = mock_create_daemon.call_args[1]
        assert call_kwargs["target"] == controller._watch
        assert call_kwargs["args"] == (topic,)
        assert call_kwargs["name"] == f"{topic}-Controller"
        assert result == mock_process

    def test_logs_process_creation(self, mocker, caplog):
        """测试记录进程创建日志"""
        # Arrange
        caplog.set_level(logging.INFO)
        controller = TestController()
        topic = "test-topic"

        mock_process = MagicMock(spec=Process)
        mock_process.pid = 12345

        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.create_daemon_process",
            return_value=mock_process,
        )

        # Act
        controller._create_watch_process(topic)

        # Assert
        assert "started watch process" in caplog.text
        assert "12345" in caplog.text
        assert "test-topic" in caplog.text


class TestBaseControllerGetKafkaTopics:
    """BaseController.get_kafka_topics 方法测试"""

    def test_returns_topics_from_handles(self):
        """测试从 handles 生成 topic 列表"""

        # Arrange
        class TestControllerWithHandles(BaseController):
            controller_name = "TestController"
            handles = {
                TestResource: lambda r, a: None,
            }

        controller = TestControllerWithHandles()

        # Act
        topics = controller.get_kafka_topics()

        # Assert
        assert len(topics) == 1
        assert topics[0] == "TestResource-v1"

    def test_returns_empty_list_when_no_handles(self):
        """测试没有 handles 时返回空列表"""
        # Arrange
        controller = TestController()

        # Act
        topics = controller.get_kafka_topics()

        # Assert
        assert topics == []


class TestBaseControllerHandleResource:
    """BaseController.handle_resource 方法测试"""

    def test_calls_correct_handler_for_resource(self, mocker):
        """测试为资源调用正确的处理器"""
        # Arrange
        mock_handler = Mock()
        test_uid = uuid.uuid4()

        class TestController(BaseController):
            controller_name = "TestController"
            handles = {
                TestResource: mock_handler,
            }

        resource = TestResource(
            metadata={"uid": str(test_uid), "name": "test"},
            spec={},
        )

        mock_store = Mock()
        mock_store.get.return_value = resource
        TestResource.store = mock_store

        # Act
        TestController.handle_resource(resource, ResourceAction.Updated)

        # Assert
        mock_handler.assert_called_once()
        call_args = mock_handler.call_args[0]
        assert call_args[0].metadata.uid == resource.metadata.uid
        assert call_args[1] == ResourceAction.Updated

    def test_fetches_latest_resource_from_store(self, mocker):
        """测试从 store 获取最新资源状态"""
        # Arrange
        mock_handler = Mock()
        test_uid = uuid.uuid4()

        class TestController(BaseController):
            controller_name = "TestController"
            handles = {
                TestResource: mock_handler,
            }

        resource = TestResource(
            metadata={"uid": str(test_uid), "name": "test"},
            spec={},
        )

        new_resource = TestResource(
            metadata={"uid": str(test_uid), "name": "test", "labels": {"updated": "true"}},
            spec={},
            status={"phase": "Running"},
        )

        mock_store = Mock()
        mock_store.get.return_value = new_resource
        TestResource.store = mock_store

        # Act
        TestController.handle_resource(resource, ResourceAction.Updated)

        # Assert
        mock_store.get.assert_called_once_with(uid=resource.metadata.uid)

    def test_does_not_fetch_for_deleted_action(self, mocker):
        """测试 Deleted 动作不从 store 获取资源"""
        # Arrange
        mock_handler = Mock()
        test_uid = uuid.uuid4()

        class TestController(BaseController):
            controller_name = "TestController"
            handles = {
                TestResource: mock_handler,
            }

        resource = TestResource(
            metadata={"uid": str(test_uid), "name": "test"},
            spec={},
        )

        mock_store = Mock()
        TestResource.store = mock_store

        # Act
        TestController.handle_resource(resource, ResourceAction.Deleted)

        # Assert
        mock_store.get.assert_not_called()
        mock_handler.assert_called_once()


class TestBaseControllerBuildResource:
    """BaseController.build_resource 方法测试"""

    def test_builds_resource_from_event_record(self, mocker):
        """测试从事件记录构建资源"""
        # Arrange
        test_uid = uuid.uuid4()
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.DefaultResourceRegistry.get",
            return_value=TestResource,
        )

        event_record = {
            "action": "Created",
            "resource": {
                "kind": "TestResource",
                "api_version": "v1",
                "metadata": {"uid": str(test_uid), "name": "test"},
                "spec": {"value": 123},
            },
        }

        # Act
        resource, action = BaseController.build_resource(event_record)

        # Assert
        assert isinstance(resource, TestResource)
        assert str(resource.metadata.uid) == str(test_uid)
        assert resource.spec.value == 123
        assert action == ResourceAction.Created

    def test_raises_error_for_invalid_resource_type(self, mocker):
        """测试无效资源类型抛出异常"""
        # Arrange
        test_uid = uuid.uuid4()
        mocker.patch(
            "bk_monitor_base.infras.declaratives.controller.base_controller.DefaultResourceRegistry.get",
            return_value=None,
        )

        event_record = {
            "action": "Created",
            "resource": {
                "kind": "InvalidResource",
                "api_version": "v1",
                "metadata": {"uid": str(test_uid), "name": "test"},
            },
        }

        # Act & Assert
        with pytest.raises(ValueError):
            BaseController.build_resource(event_record)
