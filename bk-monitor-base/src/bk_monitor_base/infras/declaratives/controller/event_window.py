import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from redis.client import Redis

from bk_monitor_base.infras.declaratives.definitions import ResourceAction
from bk_monitor_base.infras.declaratives.logger import logger

from .constants import REDIS_KEY_PREFIX


class MergedEventState(str, Enum):
    """合并后的事件状态"""

    # 初始状态，窗口内还没有收到该资源的事件
    INIT = "INIT"
    # 收到了创建事件（或从 CANCELLED/DELETED 状态重新创建）
    CREATED = "CREATED"
    # 收到了更新事件（窗口内首个事件就是 Updated）
    UPDATED = "UPDATED"
    # 收到了删除事件
    DELETED = "DELETED"
    # 创建后又删除，相互抵消，无需产生事件
    CANCELLED = "CANCELLED"


class EventMergeError(Exception):
    """事件合并异常"""

    def __init__(self, message: str, resource_uid: str, current_state: MergedEventState, new_action: ResourceAction):
        self.resource_uid = resource_uid
        self.current_state = current_state
        self.new_action = new_action
        super().__init__(message)


@dataclass
class MergeResult:
    """合并结果

    :param events: 合并后的事件列表
    :param details: 合并详情，格式为 {resource_uid: (event_sequence, final_action)}
    """

    events: list[dict] = field(default_factory=list)
    details: dict[str, tuple[list[str], str | None]] = field(default_factory=dict)


@dataclass
class MergedEvent:
    """合并后的事件

    :param state: 合并后的状态
    :param event: 最终的事件数据（包含最新的资源内容）
    :param event_sequence: 事件序列，用于调试
    """

    state: MergedEventState = MergedEventState.INIT
    event: dict | None = None
    event_sequence: list[str] = field(default_factory=list)

    def get_final_action(self) -> ResourceAction | None:
        """获取合并后应该产生的 action

        :return: 合并后的 action，如果不需要产生事件则返回 None
        """
        if self.state == MergedEventState.CREATED:
            return ResourceAction.Created
        elif self.state == MergedEventState.UPDATED:
            return ResourceAction.Updated
        elif self.state == MergedEventState.DELETED:
            return ResourceAction.Deleted
        else:
            # INIT 或 CANCELLED 状态不产生事件
            return None


class EventMerger:
    """事件合并器

    对同一资源在窗口期内的多个事件进行合并，合并规则如下：

    状态转换表：
    | 当前状态   | 新事件   | 结果状态   | 说明                           |
    |-----------|---------|-----------|-------------------------------|
    | INIT      | Created | CREATED   | 新建资源                       |
    | INIT      | Updated | UPDATED   | 更新已有资源                    |
    | INIT      | Deleted | DELETED   | 删除已有资源                    |
    | CREATED   | Created | 异常      | 重复创建                       |
    | CREATED   | Updated | CREATED   | 内容用 Updated，action 保持 Created |
    | CREATED   | Deleted | CANCELLED | 创建后删除，相互抵消            |
    | UPDATED   | Created | 异常      | 资源已存在不能创建              |
    | UPDATED   | Updated | UPDATED   | 内容用新的 Updated              |
    | UPDATED   | Deleted | DELETED   | 更新后删除                      |
    | DELETED   | Created | CREATED   | 删除后重建，用新的 Created 内容  |
    | DELETED   | Updated | 异常      | 已删除不能更新                  |
    | DELETED   | Deleted | 异常      | 重复删除                       |
    | CANCELLED | Created | CREATED   | 抵消后重建                      |
    | CANCELLED | Updated | 异常      | 已抵消（删除）不能更新          |
    | CANCELLED | Deleted | 异常      | 已抵消（删除）不能再删除        |

    示例：
    1. Created -> Updated -> Updated：合并成 Created，资源内容用最后一次 Updated
    2. Created -> Updated -> Deleted：无事件产生（CANCELLED）
    3. Created -> Updated -> Deleted -> Updated：抛出异常
    4. Created -> Updated -> Deleted -> Created：只保留最后一次 Created
    """

    # 状态转换表: (当前状态, 新action) -> (新状态, 是否异常)
    STATE_TRANSITIONS: dict[tuple[MergedEventState, ResourceAction], tuple[MergedEventState, bool]] = {
        # INIT 状态
        (MergedEventState.INIT, ResourceAction.Created): (MergedEventState.CREATED, False),
        (MergedEventState.INIT, ResourceAction.Updated): (MergedEventState.UPDATED, False),
        (MergedEventState.INIT, ResourceAction.Deleted): (MergedEventState.DELETED, False),
        # CREATED 状态
        (MergedEventState.CREATED, ResourceAction.Created): (MergedEventState.CREATED, True),  # 异常：重复创建
        (MergedEventState.CREATED, ResourceAction.Updated): (MergedEventState.CREATED, False),  # 保持 Created，内容更新
        (MergedEventState.CREATED, ResourceAction.Deleted): (MergedEventState.CANCELLED, False),  # 相互抵消
        # UPDATED 状态
        (MergedEventState.UPDATED, ResourceAction.Created): (MergedEventState.UPDATED, True),  # 异常：已存在不能创建
        (MergedEventState.UPDATED, ResourceAction.Updated): (MergedEventState.UPDATED, False),  # 内容更新
        (MergedEventState.UPDATED, ResourceAction.Deleted): (MergedEventState.DELETED, False),  # 删除
        # DELETED 状态
        (MergedEventState.DELETED, ResourceAction.Created): (MergedEventState.CREATED, False),  # 重建
        (MergedEventState.DELETED, ResourceAction.Updated): (MergedEventState.DELETED, True),  # 异常：已删除不能更新
        (MergedEventState.DELETED, ResourceAction.Deleted): (MergedEventState.DELETED, True),  # 异常：重复删除
        # CANCELLED 状态
        (MergedEventState.CANCELLED, ResourceAction.Created): (MergedEventState.CREATED, False),  # 重建
        (MergedEventState.CANCELLED, ResourceAction.Updated): (
            MergedEventState.CANCELLED,
            True,
        ),  # 异常：已抵消不能更新
        (MergedEventState.CANCELLED, ResourceAction.Deleted): (
            MergedEventState.CANCELLED,
            True,
        ),  # 异常：已抵消不能删除
    }

    @classmethod
    def merge_events(cls, events: list[dict]) -> MergeResult:
        """合并事件列表

        :param events: 原始事件列表
        :return: 合并结果
        :raises EventMergeError: 如果事件序列不合法
        """
        # 按资源 uid 分组
        resource_events: dict[str, list[dict]] = {}
        for event in events:
            resource_uid = event.get("resource", {}).get("metadata", {}).get("uid", "unknown")
            if resource_uid not in resource_events:
                resource_events[resource_uid] = []
            resource_events[resource_uid].append(event)

        result = MergeResult()

        for resource_uid, res_events in resource_events.items():
            # 按事件时间排序（确保事件顺序正确）
            res_events.sort(key=lambda e: e.get("event_time", ""))

            merged = MergedEvent()

            for event in res_events:
                action = ResourceAction(event.get("action", ""))
                merged.event_sequence.append(action.value)
                # 遇到错误直接抛出异常
                cls._apply_event(merged, event, resource_uid, action)

            # 生成最终事件
            final_action = merged.get_final_action()
            if final_action and merged.event:
                # 更新事件的 action 为合并后的 action
                final_event = merged.event.copy()
                final_event["action"] = final_action.value
                result.events.append(final_event)
                result.details[resource_uid] = (merged.event_sequence, final_action.value)
            else:
                result.details[resource_uid] = (merged.event_sequence, None)

        return result

    @classmethod
    def _apply_event(cls, merged: MergedEvent, event: dict, resource_uid: str, action: ResourceAction):
        """应用一个事件到合并状态

        :param merged: 当前合并状态
        :param event: 新事件
        :param resource_uid: 资源 uid
        :param action: 事件动作
        :raises EventMergeError: 如果事件序列不合法
        """
        transition_key = (merged.state, action)

        if transition_key not in cls.STATE_TRANSITIONS:
            raise EventMergeError(
                f"Unknown state transition: {merged.state} + {action.value}",
                resource_uid,
                merged.state,
                action,
            )

        new_state, is_error = cls.STATE_TRANSITIONS[transition_key]

        if is_error:
            raise EventMergeError(
                f"Invalid event sequence: cannot apply '{action.value}' when state is '{merged.state}'",
                resource_uid,
                merged.state,
                action,
            )

        # 更新状态
        merged.state = new_state
        # 始终保留最新的事件内容（除非是 CANCELLED 状态）
        if new_state != MergedEventState.CANCELLED:
            merged.event = event


class EventWindow:
    """事件窗口管理器

    在指定的时间窗口内收集事件，窗口结束后统一处理。
    - 每个事件通过其自身的 uid 进行存储，确保不会丢失
    - 窗口时间到期后，将所有事件批量发送到 flush_callback
    - 事件的合并逻辑（如对同一资源的多个事件合并）由 flush_callback 实现

    :param window_seconds: 窗口时间，单位秒，默认为 0（不启用窗口）
    :param redis_key_prefix: Redis key 前缀
    """

    # Redis key 模板
    WINDOW_EVENTS_KEY = "{prefix}event_window:{controller}:{topic}"
    WINDOW_TIMER_KEY = "{prefix}event_window_timer:{controller}:{topic}"

    def __init__(
        self,
        redis_client: Redis,
        window_seconds: float = 0,
        redis_key_prefix: str = REDIS_KEY_PREFIX,
    ):
        self.redis_client = redis_client
        self.window_seconds = window_seconds
        self.redis_key_prefix = redis_key_prefix
        self._timers: dict[str, threading.Timer] = {}
        self._timer_lock = threading.Lock()
        logger.debug(
            "[event_window] EventWindow initialized: window_seconds=%s, redis_key_prefix=%s, enabled=%s",
            window_seconds,
            redis_key_prefix,
            self.is_enabled(),
        )

    def is_enabled(self) -> bool:
        """检查窗口功能是否启用"""
        return self.window_seconds > 0

    def _get_events_key(self, controller_name: str, topic: str) -> str:
        """获取存储窗口事件的 Redis key"""
        return self.WINDOW_EVENTS_KEY.format(
            prefix=self.redis_key_prefix,
            controller=controller_name,
            topic=topic,
        )

    def _get_timer_key(self, controller_name: str, topic: str) -> str:
        """获取窗口定时器的 Redis key"""
        return self.WINDOW_TIMER_KEY.format(
            prefix=self.redis_key_prefix,
            controller=controller_name,
            topic=topic,
        )

    def add_event(
        self,
        controller_name: str,
        topic: str,
        event: dict,
        flush_callback: Callable[[str, str, list[dict]], None],
    ) -> bool:
        """添加事件到窗口

        :param controller_name: Controller 名称
        :param topic: Kafka topic
        :param event: 事件数据（已解析的 dict）
        :param flush_callback: 窗口结束时的回调函数，参数为 (controller_name, topic, events)
        :return: 是否成功添加
        """
        # 使用事件自身的 uid 作为 hash field
        # 事件 uid 唯一，不会相互覆盖，确保窗口内所有事件都被保留
        uid = event["metadata"]["uid"]
        resource_uid = event.get("resource", {}).get("metadata", {}).get("uid", None)
        action = event.get("action", None)
        if resource_uid is None or action is None:
            logger.warning(
                "[event_window] Event missing resource_uid or action: controller=%s, topic=%s, event_uid=%s",
                controller_name,
                topic,
                uid,
            )
            return False

        events_key = self._get_events_key(controller_name, topic)

        logger.debug(
            "[event_window] Adding event: controller=%s, topic=%s, event_uid=%s, resource_uid=%s, action=%s",
            controller_name,
            topic,
            uid,
            resource_uid,
            action,
        )

        self.redis_client.hset(events_key, uid, json.dumps(event))
        # 设置过期时间，防止数据残留（窗口时间的 3 倍）
        self.redis_client.expire(events_key, int(self.window_seconds * 3) + 60)

        # 启动或重置定时器
        self._ensure_timer(controller_name, topic, flush_callback)

        logger.debug(
            "[event_window] Added event to window: controller=%s, topic=%s, uid=%s",
            controller_name,
            topic,
            uid,
        )
        return True

    def _ensure_timer(
        self,
        controller_name: str,
        topic: str,
        flush_callback: Callable[[str, str, list[dict]], None],
    ):
        """确保定时器已启动

        只有在窗口首次收到事件时启动定时器，后续事件不会重置定时器。
        """
        timer_key = f"{controller_name}:{topic}"

        with self._timer_lock:
            if timer_key in self._timers and self._timers[timer_key].is_alive():
                # 定时器已存在且运行中，不需要重新创建
                logger.debug(
                    "[event_window] Timer already running: controller=%s, topic=%s, timer_key=%s",
                    controller_name,
                    topic,
                    timer_key,
                )
                return

            logger.debug(
                "[event_window] Creating new timer: controller=%s, topic=%s, timer_key=%s",
                controller_name,
                topic,
                timer_key,
            )
            # 创建新定时器
            timer = threading.Timer(
                self.window_seconds,
                self._flush_window,
                args=(controller_name, topic, flush_callback),
            )
            timer.daemon = True
            timer.name = f"EventWindow-{controller_name}-{topic}"
            self._timers[timer_key] = timer
            timer.start()

            logger.debug(
                "[event_window] Started window timer: controller=%s, topic=%s, window=%ss",
                controller_name,
                topic,
                self.window_seconds,
            )

    def _flush_window(
        self,
        controller_name: str,
        topic: str,
        flush_callback: Callable[[str, str, list[dict]], None],
    ):
        """刷新窗口，处理所有积累的事件"""
        logger.debug(
            "[event_window] Timer fired, starting flush: controller=%s, topic=%s",
            controller_name,
            topic,
        )
        events_key = self._get_events_key(controller_name, topic)
        timer_key = f"{controller_name}:{topic}"

        # 原子性地获取并删除所有事件
        pipe = self.redis_client.pipeline()
        pipe.hgetall(events_key)
        pipe.delete(events_key)
        results = pipe.execute()

        events_data = results[0]

        # 清理定时器引用
        with self._timer_lock:
            self._timers.pop(timer_key, None)

        if not events_data:
            logger.debug(
                "[event_window] Window flushed but no events: controller=%s, topic=%s",
                controller_name,
                topic,
            )
            return

        # 解析事件
        events = []
        for uid, event_json in events_data.items():
            try:
                # Redis 返回的 key 可能是 bytes
                if isinstance(event_json, bytes):
                    event_json = event_json.decode("utf-8")
                events.append(json.loads(event_json))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(
                    "[event_window] Failed to parse event: uid=%s, error=%s",
                    uid,
                    e,
                )

        # 合并事件
        try:
            merge_result = EventMerger.merge_events(events)
        except EventMergeError as e:
            logger.info(
                "[event_window] Flush failed due to merge error: controller=%s, topic=%s, "
                "resource_uid=%s, state=%s, action=%s",
                controller_name,
                topic,
                e.resource_uid,
                e.current_state,
                e.new_action.value,
            )
            return

        # 格式化合并详情: resource_uid -> sequence -> result
        details_str = "".join(
            f"\n{uid}: {' -> '.join(seq)} => {action or 'cancelled'}"
            for uid, (seq, action) in merge_result.details.items()
        )

        logger.info(
            "[event_window] Flushed: controller=%s, topic=%s, resources=%d, raw_events=%d, merged=%d | %s",
            controller_name,
            topic,
            len(merge_result.details),
            len(events),
            len(merge_result.events),
            details_str,
        )

        if not merge_result.events:
            return

        # 调用回调处理合并后的事件
        flush_callback(controller_name, topic, merge_result.events)

    def flush_all(self, controller_name: str, topics: list[str]):
        """立即刷新所有窗口（用于 shutdown 场景）

        :param controller_name: Controller 名称
        :param topics: 需要刷新的 topic 列表
        """
        logger.debug(
            "[event_window] flush_all called: controller=%s, topics=%s",
            controller_name,
            topics,
        )
        for topic in topics:
            timer_key = f"{controller_name}:{topic}"
            with self._timer_lock:
                timer = self._timers.pop(timer_key, None)
                if timer:
                    timer.cancel()

            # 直接获取并处理剩余事件
            events_key = self._get_events_key(controller_name, topic)
            events_data = self.redis_client.hgetall(events_key)
            if events_data:
                logger.info(
                    "[event_window] Force flush on shutdown: controller=%s, topic=%s, event_count=%d",
                    controller_name,
                    topic,
                    len(events_data),
                )
                self.redis_client.delete(events_key)
