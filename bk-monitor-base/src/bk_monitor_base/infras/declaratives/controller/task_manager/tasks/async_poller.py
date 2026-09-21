# pyright: reportUnusedParameter=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnannotatedClassAttribute=false
# pyright: reportUnknownParameterType=false
# pyright: reportArgumentType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
from abc import ABC, abstractmethod
from collections.abc import Callable
from importlib import import_module
from typing import Any, cast

from blue_krill.async_utils.poll_task import CallbackHandler, CallbackResult, CallbackStatus, PollingResult, TaskPoller
from typing_extensions import override

from bk_monitor_base.infras.declaratives.logger import logger


class AsyncPollTaskManager:
    task_cls: dict[str | tuple[str, str], type["AsyncPollTask"]] = {}

    @classmethod
    def _normalize_name(cls, name: str | tuple[str, str] | list[str]) -> str | tuple[str, str]:
        if isinstance(name, list):
            if len(name) != 2:
                raise KeyError(f"Invalid async poll task name: {name}")
            return cast(tuple[str, str], (name[0], name[1]))
        return name

    @classmethod
    def register(cls, name: str | tuple[str, str], cls1: type["AsyncPollTask"]):
        cls.task_cls[name] = cls1

    @classmethod
    def get(cls, name: str | tuple[str, str] | list[str]) -> type["AsyncPollTask"]:
        return cls.task_cls[cls._normalize_name(name)]

    @classmethod
    def get_query(cls, name: str | tuple[str, str] | list[str]) -> Callable:
        """
        如果name是str说明是query_task调用的，直接返回注册的类的方法，
               是tuple说明是simple_query_task调用的，反射加载对应的函数并且解包context中的参数
        """
        name = cls._normalize_name(name)
        if not isinstance(name, tuple):
            return cls.task_cls[name].query
        # 通过反射获取类
        class_name, task_function_name = name
        module_name, class_name = class_name.rsplit(".", 1)
        module = import_module(module_name)
        clz = getattr(module, class_name)
        instance = clz()

        # 拆分context给对应的参数
        def outer(context: tuple[Any, ...]) -> PollingResult:
            args, kwargs = context
            return getattr(instance, task_function_name)(*args, **kwargs)

        return outer


class AsyncPollTask(ABC):
    name = None

    def __init_subclass__(cls, **kwargs: dict[str, Any]) -> None:
        # 抽象类不承载具体任务，跳过注册
        if cls.__dict__.get("_abstract", False):
            return
        if cls.name is None:
            cls.name = f"{cls.__module__}.{cls.__name__}"
        logger.debug(f"注册celery异步短轮询任务 {cls.name}")
        AsyncPollTaskManager.register(cls.name, cls)

    @staticmethod
    @abstractmethod
    def query(context: dict[str, Any]) -> PollingResult:
        """要被循环执行的任务，直到返回PollingResult.done或者出错（如超时，抛出异常）为止

        :return: PollingResult 当次执行的状态，提供2个静态函数构造对应状态：
            PollingResult.doing() 继续循环的状态
            PollingResult.done(data: Any) 终止循环的状态，其中的数据data会传递给post_query_task
        """
        return PollingResult.done(None)

    @staticmethod
    def post_query(data: Any, context: dict[str, Any]) -> None:
        """循环后任务， 循环任务返回done后执行的函数"""
        return

    @staticmethod
    def except_task(result: CallbackResult, context: dict[str, Any]) -> None:
        """异常处理函数， 循环任务出错（如超时，抛出异常）后执行的函数"""
        raise RuntimeError(result.data)


class AsyncPoller(TaskPoller):
    max_retries_on_error = 0

    @override
    def query(self) -> PollingResult:
        query_func = AsyncPollTaskManager.get_query(self.params.get("query_name"))
        res = query_func(self.params.get("context"))
        # assert isinstance(res, PollingResult), "query函数的返回类型应当是 PollingResult"
        return res


class AsyncHandler(CallbackHandler):
    @override
    def handle(self, result: CallbackResult, poller: TaskPoller):
        task_cls = AsyncPollTaskManager.get(poller.params.get("query_name"))
        context = poller.params.get("context")
        if not result.is_exception:
            task_cls.post_query(result.data, context)
            return

        if result.status == CallbackStatus.TIMEOUT:
            logger.warning(f"异步轮询器'{poller.__class__.__name__}' 执行超时，")
        else:
            logger.warning(f"异步轮询器'{poller.__class__.__name__}' 出现异常，异常信息：[ {result.message} ]")

        task_cls.except_task(result, context)


class LogHandler(CallbackHandler):
    @override
    def handle(self, result: CallbackResult, poller: TaskPoller):
        if result.is_exception:
            logger.exception(f"轮询任务 [{poller.__class__.__name__}] 发生意外：{result}")
