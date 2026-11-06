import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from multiprocessing import Process
from typing import Any, ClassVar, cast

from django_redis import get_redis_connection
from redis.lock import Lock

from bk_monitor_base.infras.declaratives.constants import ThreadLocalKey
from bk_monitor_base.infras.declaratives.controller.constants import REDIS_KEY_PREFIX
from bk_monitor_base.infras.declaratives.controller.event_window import EventWindow
from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.async_task_define import AbstractEngine
from bk_monitor_base.infras.declaratives.controller.task_manager.tasks.task_factory import TaskFactory
from bk_monitor_base.infras.declaratives.definitions import Resource, ResourceAction
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.declaratives.metrics import (
    CONTROLLER_RECONCILE_COUNT,
    CONTROLLER_RECONCILE_DURATION,
    CONTROLLER_RECONCILE_FINISHED_COUNT,
    CONTROLLER_RECONCILE_PREPARE_COUNT,
)
from bk_monitor_base.infras.declaratives.protocols import EventProviderProtocol, event_registry
from bk_monitor_base.infras.declaratives.registry import DefaultResourceRegistry
from bk_monitor_base.infras.metrics import observe_time
from bk_monitor_base.infras.process.process_manager import (
    create_daemon_process,
    run_process_monitor_loop,
    setup_signal_handlers,
)
from bk_monitor_base.infras.threading.local import set_local_param


class BaseController:
    """controller 的抽象基类

    Attributes:
        controller_name: 当前Controller的名字，会被储存在thread_local中。
            获取kafka时要排除相同Controller发送的消息防止重复消费
            在处理Resource时可能要发送kafka，发送时要带上这个名字防止重复消费。
            默认为类名。
        handles: 具体处理Resource的方法，根据Resource.kind来查找
        list_interval: 执行list的最小时间间隔，单位为秒，默认为3600s
        list_excludes: 不希望被执行list的资源，其值应当为handles的键的子集，默认为空集。
                    example: list_excludes = {(CollectSetConfig.kind, CollectSetConfig.api_version)}
        event_window_seconds: 事件窗口时间，单位为秒，默认为0（不启用窗口）。
            启用后，在窗口期内对同一资源的事件会被合并，只保留最后一个事件。
    """

    controller_name: ClassVar[str]
    handles: ClassVar[dict[type[Resource], Callable]] = {}

    # list行为的最小时间间隔，以秒为单位，默认为3600s
    list_interval: ClassVar[int] = 60 * 60
    # 黑名单，不进行list的资源
    list_excludes: ClassVar[set[type[Resource]]] = set()
    # 事件窗口时间，单位为秒，为0则不启用窗口
    event_window_seconds: ClassVar[float] = 60
    # 资源处理锁
    resource_lock_key_template = f"{REDIS_KEY_PREFIX}controller_resource_handler_{{}}"
    # 资源锁过期时间s
    resource_lock_timeout = 3 * 60

    resource_kind_queue_map: ClassVar[dict[str, str]] = {}

    _event_provider: ClassVar[EventProviderProtocol | None] = None
    _async_task_handler: ClassVar[AbstractEngine | None] = None  # 延迟初始化，避免子进程导入时引擎未注册

    @classmethod
    def _get_async_task_handler(cls) -> AbstractEngine:
        """延迟获取异步任务处理器，确保在 Django 应用初始化后才创建"""
        if cls._async_task_handler is None:
            handler = TaskFactory().get_task_handler()
            if not isinstance(handler, AbstractEngine):
                raise TypeError("Task handler must be an AbstractEngine instance")
            cls._async_task_handler = handler
        return cls._async_task_handler

    @classmethod
    def _get_event_provider(cls) -> EventProviderProtocol:
        """
        获取事件提供者实例，延迟初始化。

        如果未注册 provider 将抛出异常。
        """
        if cls._event_provider is None:
            provider_class = event_registry.get_provider_class()
            if provider_class is None:
                message = (
                    "Event provider not registered. Please call register_default_providers() from candidacy "
                    "before using controller."
                )
                raise RuntimeError(message)
            cls._event_provider = provider_class()
        return cls._event_provider

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # 为controller_name提供默认值为类名
        if "controller_name" not in cls.__dict__:
            cls.controller_name = cls.__name__
        super().__init_subclass__(**kwargs)

    def __init__(self, event_window_seconds: float | None = None):
        """
        :param event_window_seconds: 事件窗口时间（秒），为 None 时使用类变量默认值
        """
        self.list_time_key = f"{REDIS_KEY_PREFIX}{self.controller_name}_list_time"
        # 如果传入了参数，使用参数值；否则使用类变量默认值
        self._event_window_seconds = (
            event_window_seconds if event_window_seconds is not None else self.event_window_seconds
        )
        # 事件窗口延迟初始化，避免在 multiprocessing 时因为 threading.Lock 无法 pickle 的问题
        self._event_window: EventWindow | None = None

    def _get_event_window(self) -> EventWindow:
        """获取事件窗口实例，延迟初始化"""
        if self._event_window is None:
            self._event_window = EventWindow(
                redis_client=get_redis_connection(), window_seconds=self._event_window_seconds
            )
        return self._event_window

    def start(self):
        """启动Controller

        另外开启一个线程执行list
        在主线程执行watch
        """
        # 暂不启用list功能
        # self.start_list_process()
        self.watch_process()

    def start_list_process(self):
        """单独开一个线程执行list任务"""
        thread = threading.Thread(target=self.list_process)
        thread.daemon = True
        thread.name = f"{self.controller_name} - list 线程 #{hash(thread)}"
        thread.start()

    def list_process(self):
        """执行list兜底任务
        多个Controller实例中有1个执行list即可，仅在启动时执行一次
        """
        lock = get_redis_connection().lock(
            name=f"{REDIS_KEY_PREFIX}list_lock_for_{self.controller_name}",
            timeout=self.list_interval,
            sleep=self.list_interval // 3,
            blocking_timeout=0,  # 如果发生竞争
        )

        if lock.acquire():
            try:
                logger.info(f"thread {threading.current_thread().name} got list lock")
                curr_time = int(time.time())
                last_list_time = get_redis_connection().get(self.list_time_key)
                if not last_list_time:
                    # 如果为空则立即执行一次
                    get_redis_connection().set(self.list_time_key, curr_time)
                    logger.info(f"thread {threading.current_thread().name} apply list right now")
                    self.apply_listed_resources()
                    return

                last_list_time = int(last_list_time)  # type: ignore
                next_list_time = last_list_time + self.list_interval
                wait_seconds = max(next_list_time - curr_time, 0)
                logger.info(f"thread {threading.current_thread().name} apply list after {wait_seconds} seconds")
                time.sleep(wait_seconds)
                get_redis_connection().set(self.list_time_key, int(time.time()))
                self.apply_listed_resources(last_list_time)
            finally:
                lock.release()

    def apply_listed_resources(self, since: int = 0):
        """在数据库中找到每一个resource的实例，重新apply"""
        for resource_cls in self.handles.keys() - self.list_excludes:
            logger.info(
                "[controller_list] %s list apply %s-%s, since: %s",
                self.controller_name,
                resource_cls.kind,
                resource_cls.api_version,
                since,
            )

            filters = {}
            if since > 0:
                # 仅处理自since以来更新的资源
                filters["updated_at__gte"] = since * 1000

            for resource in resource_cls.store.list(common_filter=filters):
                try:
                    with self.get_resource_lock(resource.metadata.uid.hex):
                        self.handle_resource(resource, ResourceAction.Updated)
                except Exception:
                    logger.exception(f"[controller_list] {self.controller_name} do list apply for {resource} failed")

    def watch_process(self):
        """启动 watch 进程,监听 Kafka topics 并自动重启失败的进程"""
        topics = self.get_kafka_topics()
        if not topics:
            logger.warning("[controller] %s has no topics to watch", self.controller_name)
            return

        process_list: list[tuple[Process, str]] = []
        parent_pid = os.getpid()
        shutdown_event = threading.Event()

        # 创建并启动所有监控进程
        for topic in topics:
            process = self._create_watch_process(topic)
            process_list.append((process, topic))

        # 设置信号处理器
        setup_signal_handlers(
            shutdown_event=shutdown_event,
            parent_pid=parent_pid,
            process_name=f"[controller] {self.controller_name}",
        )

        # 主监控循环: 检测并重启崩溃的进程
        run_process_monitor_loop(
            process_list=process_list,
            process_factory=self._create_watch_process,
            shutdown_event=shutdown_event,
            log_prefix="controller",
        )

    def _create_watch_process(self, topic: str) -> Process:
        """创建并启动监控指定 topic 的子进程

        Args:
            topic: Kafka topic 名称

        Returns:
            已启动的 Process 实例
        """
        process = create_daemon_process(
            target=self._watch,
            args=(topic,),
            name=f"{topic}-Controller",
        )
        logger.info(
            "[controller] %s started watch process pid=%s for topic %s",
            self.controller_name,
            process.pid,
            topic,
        )
        return process

    def _watch(self, topic: str):
        # 即使 event_provider.watch 支持同时监听多个 topic，但为了避免某一个topic异常导致其他 topic 也无法消费，
        # 所以这里分进程监听每一个 topic
        logger.info("[controller] %s watch topic %s", self.controller_name, topic)
        for event in self._get_event_provider().watch([topic], group_id=self.controller_name):
            try:
                self._process_event(event, topic, self._get_async_task_handler())
            except Exception:
                logger.exception("[controller] %s process event %s in %s failed", self.controller_name, event, topic)

    def _process_event(self, event: Any, topic: str, async_task_handler: AbstractEngine) -> None:
        event_data = json.loads(event.value)
        if not isinstance(event_data, dict):
            raise TypeError("event payload must be a dict")
        # 避免多个 Controller 对事件进行重复响应
        if event_data.get("ignore_self", False) and event_data["source"] == self.controller_name:
            return

        # 如果启用了事件窗口，将事件添加到窗口中
        event_window = self._get_event_window()
        if event_window.is_enabled():
            event_window.add_event(
                controller_name=self.controller_name,
                topic=topic,
                event=event_data,
                flush_callback=self._on_window_flush,
            )
            return

        # 未启用窗口，直接处理事件
        self._submit_event_task(event_data, async_task_handler)

    def _submit_event_task(self, event: dict[str, Any], async_task_handler: AbstractEngine) -> None:
        """提交单个事件到异步任务处理器

        :param event: 事件数据
        :param async_task_handler: 异步任务处理器
        """
        # 对于同uid的资源只允许单个时间处于执行状态
        uid = event["resource"]["metadata"]["uid"]
        lock = self.get_resource_lock(uid)
        if not lock.acquire():
            logger.warning(f"[controller] event {uid} acquire lock failed")
            return

        # 按照资源的 Kind 来分发到不同的处理队列
        kind = event["resource"].get("kind")
        queue = None
        if self.resource_kind_queue_map:
            queue = self.resource_kind_queue_map.get(kind)
            logger.info(f"[controller] event {uid} dispatch to queue {queue} by kind {kind}")
        async_task_handler.submit_task(self, "handle", event, queue=queue)  # pyright: ignore[reportArgumentType]
        CONTROLLER_RECONCILE_PREPARE_COUNT.labels(
            resource_type=event["resource"]["kind"], operation_type=event["action"]
        ).inc()

    def _on_window_flush(self, controller_name: str, topic: str, events: list[dict[str, Any]]) -> None:
        """事件窗口刷新回调，处理合并后的事件

        :param controller_name: Controller 名称
        :param topic: Kafka topic
        :param events: 合并后的事件列表
        """
        for event in events:
            try:
                self._submit_event_task(event, self._get_async_task_handler())
            except Exception:
                logger.exception(
                    "[controller] %s failed to submit event from window: topic=%s, uid=%s",
                    controller_name,
                    topic,
                    event.get("resource", {}).get("metadata", {}).get("uid"),
                )

    @classmethod
    def handle(cls, event_record: dict[str, Any]) -> None:
        try:
            resource, action = cls.build_resource(event_record)
            # 保存name到thread_local，给其他模块发kafka时用
            set_local_param(ThreadLocalKey.DECLARATIVE_DEPARTMENT_NAME, cls.controller_name)
            CONTROLLER_RECONCILE_COUNT.labels(resource_type=resource.kind, operation_type=action).inc()
            with observe_time(
                CONTROLLER_RECONCILE_DURATION,
                resource_type=str(resource.kind),
                operation_type=action,
            ):
                cls.handle_resource(resource, action)
        finally:
            cls.release_resource_lock(event_record["resource"]["metadata"]["uid"])
            CONTROLLER_RECONCILE_FINISHED_COUNT.labels(
                resource_type=event_record["resource"]["kind"],
                operation_type=event_record["action"],
            ).inc()

    @classmethod
    def build_resource(cls, event_record: dict[str, Any]) -> tuple[Resource, ResourceAction]:
        """从kafka消息中重建对应的Resource"""
        resource_class: type[Resource] | None = DefaultResourceRegistry.get(
            event_record["resource"]["kind"], event_record["resource"]["api_version"]
        )
        if resource_class is None:
            raise ValueError(
                "[controller] invalid resource type %s-%s",
                event_record["resource"]["kind"],
                event_record["resource"]["api_version"],
            )

        action = ResourceAction(event_record["action"])
        resource = resource_class(**event_record["resource"])
        return resource, action

    def get_kafka_topics(self) -> list[str]:
        """指定Controller监听的kafka_topic为注册的handle的kind和ApiVersion"""
        return [str(k.kind) + "-" + str(k.api_version) for k in self.handles.keys()]

    @classmethod
    def handle_resource(cls, resource: Resource, action: ResourceAction):
        """具体处理Resource的方法交由具体的controller实现"""
        handler = cls.handles[resource.__class__]
        # 从db中获取最新的状态
        if action != ResourceAction.Deleted:
            new_resource = resource.store.get(uid=resource.metadata.uid)
            resource.status = new_resource.status
            resource.metadata = resource.metadata.copy(update={"labels": new_resource.metadata.labels})
        handler(resource, action)

    @classmethod
    def get_resource_lock(cls, uid: str) -> Lock:
        uid = uuid.UUID(uid).hex
        return cast(
            Lock,
            get_redis_connection().lock(cls.resource_lock_key_template.format(uid), timeout=180, blocking_timeout=60),
        )

    @classmethod
    def release_resource_lock(cls, uid: str):
        # uid统一使用hex
        uid = uuid.UUID(uid).hex
        get_redis_connection().delete(cls.resource_lock_key_template.format(uid))
