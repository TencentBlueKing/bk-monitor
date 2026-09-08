# pyright: reportUnknownVariableType=false
# pyright: reportUnknownMemberType=false
# pyright: reportFunctionMemberAccess=false

from abc import ABC, abstractmethod
from importlib import import_module
from typing import Any

from celery import shared_task
from typing_extensions import override

from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.async_poller import (
    AsyncHandler,
    AsyncPoller,
    AsyncPollTask,
    LogHandler,
)
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.declaratives.metrics import TASK_ENGINE_SEND_COUNT


class AbstractEngine(ABC):
    @abstractmethod
    def submit_task(self, instance: Any, task_function_name: str, *args: Any, **kwargs: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def query_task(self, task_cls: type[AsyncPollTask], context: dict[str, Any] | None = None) -> None:
        pass


class CeleryEngine(AbstractEngine):
    @staticmethod
    @shared_task
    def celery_task(class_name: str, task_function_name: str, *args, **kwargs):
        try:
            # 动态导入模块和类
            module_name, class_name = class_name.rsplit(".", 1)
            module = import_module(module_name)
            cls = getattr(module, class_name)

            # 实例化类
            instance = cls()

            # 获取实例方法
            method = getattr(instance, task_function_name)

            # 调用实例方法
            result = method(*args, **kwargs)
            return result
        except Exception:
            logger.exception("Error in celery_task")
            raise

    @override
    def submit_task(self, instance: Any, task_function_name: str, *args, **kwargs):
        try:
            class_name = f"{instance.__class__.__module__}.{instance.__class__.__name__}"
            logger.info(f"Submitting task: {class_name}.{task_function_name} args: {args} and kwargs: {kwargs}")
            TASK_ENGINE_SEND_COUNT.labels(method_name=f"{class_name}.{task_function_name}").inc()

            queue = kwargs.pop("queue", None)
            params = {"args": (class_name, task_function_name, *args), "kwds": kwargs}
            if queue:
                params["queue"] = queue
            task = self.celery_task.apply_async(**params)
            logger.info(f"task: {task} from {class_name}.{task_function_name} has been submitted to queue<{queue}>")
        except Exception:
            logger.exception("Error in submit_task")
            raise

    @override
    def query_task(
        self,
        task_cls: type[AsyncPollTask],
        context: dict | None = None,
        callback_handler_cls: type = AsyncHandler,
    ):
        """通过celery引擎异步地循环执行任务，直到循环任务完成并返回 PollingResult.done为止"""
        name = task_cls.name
        AsyncPoller.start(
            {"query_name": name, "context": context},
            callback_handler_cls,
        )

    def simple_query_task(self, instance, task_function_name: str, *args, **kwargs):
        AsyncPoller.start(
            {
                "context": (args, kwargs),
                "query_name": (f"{instance.__class__.__module__}.{instance.__class__.__name__}", task_function_name),
            },
            LogHandler,
        )
