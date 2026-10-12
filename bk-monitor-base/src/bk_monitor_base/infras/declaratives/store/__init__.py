from dataclasses import dataclass
from enum import Enum

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from bk_monitor_base.infras.declaratives import Resource, ResourceEvent
from bk_monitor_base.infras.declaratives.base import EventModel, ResourceEventDocument
from bk_monitor_base.infras.declaratives.constants import ES_RESOURCE_STORE
from bk_monitor_base.infras.declaratives.logger import logger
from bk_monitor_base.infras.declaratives.protocols import event_registry


class DeleteMode(Enum):
    """BaseStore 的删除模式（for local db）"""

    # 支持2阶段提交
    PREPARE_PHASE = "PREPARE_PHASE"
    COMMIT_PHASE = "COMMIT_PHASE"
    # 直接删除
    DIRECT = "DIRECT"


@dataclass
class BaseStore:
    resource_cls: type[Resource]
    resource: Resource | None = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"record_event failed (attempt {retry_state.attempt_number}/3), retrying..."
        ),
    )
    def _send_event_with_retry(self, event: ResourceEvent):
        """
        发送事件到消息通道(带重试)
        每次重试都会重新获取 event_producer,以应对初始化失败的情况
        """
        # 每次重试都重新获取 producer
        try:
            producer = event_registry.get_producer()
            if producer is None:
                raise Exception("Event producer is None")
        except Exception as e:
            logger.warning(f"Failed to initialize event producer: {str(e)}")
            raise

        producer.produce(event)
        logger.info(f"{event} has been sent to message channel")

    def record_event(self, event: ResourceEvent):
        """
        记录资源事件

        :param event: 资源事件对象
        """
        # 发送到消息通道(带重试和 producer 重新初始化)
        try:
            self._send_event_with_retry(event)
        except Exception as e:
            logger.exception(
                f"Failed to send event to message channel after retries, clients may miss the event,"
                f"failed_send_event: {event.resource.kind}|{event.resource.metadata.uid}， error: {e}"
            )
        else:
            # 持久化到数据库
            if ResourceEvent.store_class == ES_RESOURCE_STORE:
                try:
                    ResourceEventDocument.apply(event)
                except Exception as e:
                    logger.exception(f"resource event apply to ES failed, error: {e}")
            else:
                try:
                    EventModel.objects.apply(event)
                except Exception as e:
                    logger.exception(f"resource event apply to DB failed, error: {e}")
