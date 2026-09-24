"""
Event Provider 和 Event Producer 的协议定义和注册机制。

由于 base 不能引用 candidacy，这里只定义接口协议，
具体实现由 candidacy 或场景层注册。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, TypeVar

from typing_extensions import Protocol

if TYPE_CHECKING:
    from bk_monitor_base.infras.declaratives import ResourceEvent


logger = logging.getLogger(__name__)


class EventProviderProtocol(Protocol):
    """事件提供者协议 - 用于消费事件（如 Kafka Consumer）"""

    def watch(
        self,
        topic: list[str],
        partition: int = 0,
        offset: int = 0,
        group_id: str | None = None,
    ) -> Iterator[object]:
        """
        监听事件流。

        :param topic: 要监听的主题列表
        :param partition: 分区号
        :param offset: 偏移量
        :param group_id: 消费者组 ID
        :yields: 事件消息
        """
        raise NotImplementedError("Event provider must implement watch method")


class EventProducerProtocol(Protocol):
    """事件生产者协议 - 用于发送事件（如 Kafka Producer）"""

    def produce(self, event: ResourceEvent) -> None:
        """
        发送事件。

        :param event: 资源事件对象
        """
        raise NotImplementedError("Event producer must implement produce method")


T = TypeVar("T")

# 模块级变量存储注册的提供者和工厂
_registered_provider_class: type[EventProviderProtocol] | None = None
_registered_producer_factory: Callable[[], EventProducerProtocol] | None = None


class _EventProviderRegistry:
    """
    事件提供者/生产者的注册中心。

    允许外部（candidacy 或场景层）注册具体实现，
    base 内部通过此注册中心获取实现。
    """

    @classmethod
    def register_provider(cls, provider_class: type[EventProviderProtocol]) -> None:
        """
        注册事件提供者类。

        :param provider_class: 实现了 EventProviderProtocol 的类
        """
        global _registered_provider_class
        _registered_provider_class = provider_class
        logger.info(f"Registered event provider: {provider_class.__name__}")

    @classmethod
    def register_producer_factory(cls, factory: Callable[[], EventProducerProtocol]) -> None:
        """
        注册事件生产者工厂函数。

        :param factory: 返回 EventProducerProtocol 实例的工厂函数
        """
        global _registered_producer_factory
        _registered_producer_factory = factory
        logger.info("Registered event producer factory")

    @classmethod
    def get_provider_class(cls) -> type[EventProviderProtocol] | None:
        """
        获取已注册的事件提供者类。

        :return: 事件提供者类，如果未注册则返回 None
        """
        return _registered_provider_class

    @classmethod
    def get_producer(cls) -> EventProducerProtocol | None:
        """
        获取事件生产者实例。

        :return: 事件生产者实例，如果未注册则返回 None
        """
        if _registered_producer_factory is None:
            return None
        return _registered_producer_factory()

    @classmethod
    def is_provider_registered(cls) -> bool:
        """检查是否已注册事件提供者"""
        return _registered_provider_class is not None

    @classmethod
    def is_producer_registered(cls) -> bool:
        """检查是否已注册事件生产者"""
        return _registered_producer_factory is not None


# 全局注册中心实例
event_registry = _EventProviderRegistry()
