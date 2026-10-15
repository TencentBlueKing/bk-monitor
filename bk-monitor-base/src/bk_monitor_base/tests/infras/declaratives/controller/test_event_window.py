"""EventWindow 和 EventMerger 单元测试"""

import threading
import time
import uuid

import pytest
from fakeredis import FakeStrictRedis

from bk_monitor_base.infras.declaratives.controller.event_window import (
    EventMergeError,
    EventMerger,
    EventWindow,
    MergedEventState,
)
from bk_monitor_base.infras.declaratives.definitions import ResourceAction


def make_event(
    resource_uid: str,
    action: str,
    event_time: str = None,
    spec_value: int = 1,
    event_uid: str = None,
) -> dict:
    """创建测试用的事件数据

    :param resource_uid: 资源 uid
    :param action: 事件动作 (Created/Updated/Deleted)
    :param event_time: 事件时间，用于排序
    :param spec_value: spec 中的 value 值，用于验证资源内容
    :param event_uid: 事件自身的 uid，默认自动生成
    :return: 事件字典
    """
    return {
        "metadata": {
            "uid": event_uid or str(uuid.uuid4()),
            "name": "",
        },
        "action": action,
        "resource": {
            "metadata": {
                "uid": resource_uid,
                "name": f"test-resource-{spec_value}",
            },
            "spec": {"value": spec_value},
            "kind": "TestResource",
            "api_version": "v1",
        },
        "event_time": event_time or f"2025-01-01T00:00:{spec_value:02d}",
        "type": "Normal",
        "source": "test",
    }


class TestEventMerger:
    """EventMerger 事件合并逻辑测试"""

    def test_single_created_event(self):
        """测试单个 Created 事件"""
        resource_uid = str(uuid.uuid4())
        events = [make_event(resource_uid, "Created", spec_value=1)]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        assert result.events[0]["resource"]["spec"]["value"] == 1
        assert result.details[resource_uid] == (["Created"], "Created")

    def test_single_updated_event(self):
        """测试单个 Updated 事件"""
        resource_uid = str(uuid.uuid4())
        events = [make_event(resource_uid, "Updated", spec_value=1)]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Updated"
        assert result.details[resource_uid] == (["Updated"], "Updated")

    def test_single_deleted_event(self):
        """测试单个 Deleted 事件"""
        resource_uid = str(uuid.uuid4())
        events = [make_event(resource_uid, "Deleted", spec_value=1)]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Deleted"
        assert result.details[resource_uid] == (["Deleted"], "Deleted")

    def test_created_then_updated_merges_to_created(self):
        """测试 Created -> Updated 合并为 Created，内容用 Updated 的"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        # 资源内容应该是最后一次 Updated 的
        assert result.events[0]["resource"]["spec"]["value"] == 2
        assert result.details[resource_uid] == (["Created", "Updated"], "Created")

    def test_created_updated_updated_merges_to_created(self):
        """测试 Created -> Updated -> Updated 合并为 Created，资源内容用最后一次 Updated"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:03", spec_value=3),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        assert result.events[0]["resource"]["spec"]["value"] == 3
        assert result.details[resource_uid] == (["Created", "Updated", "Updated"], "Created")

    def test_created_then_deleted_cancels(self):
        """测试 Created -> Deleted 相互抵消，无事件产生"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 0
        assert result.details[resource_uid] == (["Created", "Deleted"], None)

    def test_created_updated_deleted_cancels(self):
        """测试 Created -> Updated -> Deleted 相互抵消"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:03", spec_value=3),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 0
        assert result.details[resource_uid] == (["Created", "Updated", "Deleted"], None)

    def test_updated_then_deleted_merges_to_deleted(self):
        """测试 Updated -> Deleted 合并为 Deleted"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Deleted"
        assert result.details[resource_uid] == (["Updated", "Deleted"], "Deleted")

    def test_updated_updated_merges_to_updated(self):
        """测试 Updated -> Updated 合并为 Updated，内容用最新的"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Updated"
        assert result.events[0]["resource"]["spec"]["value"] == 2
        assert result.details[resource_uid] == (["Updated", "Updated"], "Updated")

    def test_deleted_then_created_recreates(self):
        """测试 Deleted -> Created 重建资源"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        assert result.events[0]["resource"]["spec"]["value"] == 2
        assert result.details[resource_uid] == (["Deleted", "Created"], "Created")

    def test_created_deleted_created_recreates(self):
        """测试 Created -> Deleted -> Created 只保留最后一次 Created"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02", spec_value=2),
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:03", spec_value=3),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        assert result.events[0]["resource"]["spec"]["value"] == 3
        assert result.details[resource_uid] == (["Created", "Deleted", "Created"], "Created")

    def test_multiple_resources_merged_independently(self):
        """测试多个资源独立合并"""
        uid1 = str(uuid.uuid4())
        uid2 = str(uuid.uuid4())
        events = [
            make_event(uid1, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(uid2, "Updated", event_time="2025-01-01T00:00:02", spec_value=10),
            make_event(uid1, "Updated", event_time="2025-01-01T00:00:03", spec_value=2),
            make_event(uid2, "Updated", event_time="2025-01-01T00:00:04", spec_value=20),
        ]

        result = EventMerger.merge_events(events)

        assert len(result.events) == 2
        # 按资源查找事件
        events_by_uid = {e["resource"]["metadata"]["uid"]: e for e in result.events}

        assert events_by_uid[uid1]["action"] == "Created"
        assert events_by_uid[uid1]["resource"]["spec"]["value"] == 2

        assert events_by_uid[uid2]["action"] == "Updated"
        assert events_by_uid[uid2]["resource"]["spec"]["value"] == 20

    def test_error_on_duplicate_created(self):
        """测试重复 Created 抛出异常"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        with pytest.raises(EventMergeError) as exc_info:
            EventMerger.merge_events(events)

        assert exc_info.value.resource_uid == resource_uid
        assert exc_info.value.current_state == MergedEventState.CREATED
        assert exc_info.value.new_action == ResourceAction.Created

    def test_error_on_updated_after_created(self):
        """测试 Updated 状态下 Created 抛出异常"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        with pytest.raises(EventMergeError) as exc_info:
            EventMerger.merge_events(events)

        assert exc_info.value.current_state == MergedEventState.UPDATED
        assert exc_info.value.new_action == ResourceAction.Created

    def test_error_on_updated_after_deleted(self):
        """测试已删除后 Updated 抛出异常"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        with pytest.raises(EventMergeError) as exc_info:
            EventMerger.merge_events(events)

        assert exc_info.value.current_state == MergedEventState.DELETED
        assert exc_info.value.new_action == ResourceAction.Updated

    def test_error_on_duplicate_deleted(self):
        """测试重复 Deleted 抛出异常"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02", spec_value=2),
        ]

        with pytest.raises(EventMergeError) as exc_info:
            EventMerger.merge_events(events)

        assert exc_info.value.current_state == MergedEventState.DELETED
        assert exc_info.value.new_action == ResourceAction.Deleted

    def test_error_on_updated_after_cancelled(self):
        """测试 CANCELLED 状态后 Updated 抛出异常"""
        resource_uid = str(uuid.uuid4())
        events = [
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02", spec_value=2),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:03", spec_value=3),
        ]

        with pytest.raises(EventMergeError) as exc_info:
            EventMerger.merge_events(events)

        assert exc_info.value.current_state == MergedEventState.CANCELLED
        assert exc_info.value.new_action == ResourceAction.Updated

    def test_events_sorted_by_event_time(self):
        """测试事件按 event_time 排序后处理"""
        resource_uid = str(uuid.uuid4())
        # 故意打乱顺序
        events = [
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2),
            make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1),
            make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:03", spec_value=3),
        ]

        result = EventMerger.merge_events(events)

        # 即使输入顺序是 Updated, Created, Updated
        # 排序后应该是 Created, Updated, Updated，合并为 Created
        assert len(result.events) == 1
        assert result.events[0]["action"] == "Created"
        assert result.events[0]["resource"]["spec"]["value"] == 3


class TestEventWindow:
    """EventWindow 单元测试类"""

    # 使用唯一前缀避免测试间干扰
    TEST_KEY_PREFIX = "test:event_window_ut:"

    @pytest.fixture
    def redis_client(self):
        """创建 FakeRedis 客户端用于测试

        使用 fakeredis 模拟 Redis 行为,提供完整的 Redis API 支持
        """
        return FakeStrictRedis(decode_responses=False)

    @pytest.fixture
    def cleanup_redis(self, redis_client):
        """测试后清理 Redis 中的测试数据"""
        yield
        # 清理所有测试相关的 key
        pattern = f"{self.TEST_KEY_PREFIX}*"
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)

    def test_is_enabled_when_window_is_zero(self, redis_client):
        """测试窗口时间为0时，窗口功能不启用"""
        window = EventWindow(redis_client=redis_client, window_seconds=0)
        assert window.is_enabled() is False

    def test_is_enabled_when_window_is_positive(self, redis_client):
        """测试窗口时间大于0时，窗口功能启用"""
        window = EventWindow(redis_client=redis_client, window_seconds=5)
        assert window.is_enabled() is True

    @pytest.mark.usefixtures("cleanup_redis")
    def test_add_event_stores_in_redis(self, redis_client):
        """测试添加事件时正确存储到 Redis"""
        window = EventWindow(redis_client=redis_client, window_seconds=5, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())
        event_uid = str(uuid.uuid4())
        event = make_event(resource_uid, "Created", event_uid=event_uid)

        def callback(ctrl_name, tp, events):
            pass

        window.add_event(controller_name, topic, event, callback)

        # 验证事件被存储（使用事件 uid 作为 key）
        events_key = window._get_events_key(controller_name, topic)
        stored = redis_client.hgetall(events_key)
        assert event_uid.encode() in stored or event_uid in stored

        # 清理定时器
        window.flush_all(controller_name, [topic])

    @pytest.mark.usefixtures("cleanup_redis")
    def test_add_event_keeps_all_events_by_event_uid(self, redis_client):
        """测试不同事件 uid 的事件都会被保留（即使资源 uid 相同）"""
        window = EventWindow(redis_client=redis_client, window_seconds=5, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"

        def callback(ctrl_name, tp, events):
            pass

        resource_uid = str(uuid.uuid4())
        event_uid1 = str(uuid.uuid4())
        event_uid2 = str(uuid.uuid4())

        event1 = make_event(resource_uid, "Created", event_uid=event_uid1, spec_value=1)
        event2 = make_event(resource_uid, "Updated", event_uid=event_uid2, spec_value=2)

        window.add_event(controller_name, topic, event1, callback)
        window.add_event(controller_name, topic, event2, callback)

        # 验证两个事件都被存储（因为事件 uid 不同）
        events_key = window._get_events_key(controller_name, topic)
        stored = redis_client.hgetall(events_key)
        stored_keys = [k.decode() if isinstance(k, bytes) else k for k in stored.keys()]
        assert event_uid1 in stored_keys
        assert event_uid2 in stored_keys

        # 清理定时器
        window.flush_all(controller_name, [topic])

    @pytest.mark.usefixtures("cleanup_redis")
    def test_flush_window_merges_and_calls_callback(self, redis_client):
        """测试窗口刷新时合并事件并调用回调函数"""
        window = EventWindow(redis_client=redis_client, window_seconds=0.1, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())

        # 添加 Created 和 Updated 事件
        event1 = make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01", spec_value=1)
        event2 = make_event(resource_uid, "Updated", event_time="2025-01-01T00:00:02", spec_value=2)

        callback_called = threading.Event()
        received_events = []

        def callback(ctrl_name, tp, events):
            received_events.extend(events)
            callback_called.set()

        window.add_event(controller_name, topic, event1, callback)
        window.add_event(controller_name, topic, event2, callback)

        # 等待窗口刷新
        callback_called.wait(timeout=1)

        assert callback_called.is_set()
        # 合并后应该只有一个事件
        assert len(received_events) == 1
        # 合并后 action 应该是 Created
        assert received_events[0]["action"] == "Created"
        # 资源内容应该是最后一次的
        assert received_events[0]["resource"]["spec"]["value"] == 2

    @pytest.mark.usefixtures("cleanup_redis")
    def test_flush_window_clears_redis(self, redis_client):
        """测试窗口刷新后清除 Redis 中的事件"""
        window = EventWindow(redis_client=redis_client, window_seconds=0.1, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())
        event = make_event(resource_uid, "Created")

        callback_called = threading.Event()

        def callback(ctrl_name, tp, events):
            callback_called.set()

        window.add_event(controller_name, topic, event, callback)

        # 等待窗口刷新
        callback_called.wait(timeout=1)

        # 验证 Redis 中的事件已被清除
        events_key = window._get_events_key(controller_name, topic)
        stored = redis_client.hgetall(events_key)
        assert len(stored) == 0

    @pytest.mark.usefixtures("cleanup_redis")
    def test_flush_window_cancels_events(self, redis_client):
        """测试窗口刷新时 Created -> Deleted 相互抵消不调用回调"""
        window = EventWindow(redis_client=redis_client, window_seconds=0.1, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())

        event1 = make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01")
        event2 = make_event(resource_uid, "Deleted", event_time="2025-01-01T00:00:02")

        received_events = []

        def callback(ctrl_name, tp, events):
            received_events.extend(events)

        window.add_event(controller_name, topic, event1, callback)
        window.add_event(controller_name, topic, event2, callback)

        # 等待窗口刷新
        time.sleep(0.2)

        # 合并后无事件，callback 不应该被调用（或被调用但 events 为空）
        assert len(received_events) == 0

    @pytest.mark.usefixtures("cleanup_redis")
    def test_timer_not_reset_on_subsequent_events(self, redis_client):
        """测试后续事件不会重置定时器"""
        window = EventWindow(redis_client=redis_client, window_seconds=0.2, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"

        callback_called = threading.Event()

        def callback(ctrl_name, tp, events):
            callback_called.set()

        # 添加第一个事件
        uid1 = str(uuid.uuid4())
        event1 = make_event(uid1, "Created")
        window.add_event(controller_name, topic, event1, callback)

        # 记录定时器启动时间
        start_time = time.time()

        # 100ms 后添加第二个事件
        time.sleep(0.1)
        uid2 = str(uuid.uuid4())
        event2 = make_event(uid2, "Created")
        window.add_event(controller_name, topic, event2, callback)

        # 等待回调被调用
        callback_called.wait(timeout=1)

        # 验证回调在约 200ms 后被调用（从第一个事件开始计算），而不是 300ms
        elapsed = time.time() - start_time
        assert elapsed < 0.35

    @pytest.mark.usefixtures("cleanup_redis")
    def test_flush_all_cancels_timers(self, redis_client):
        """测试 flush_all 取消所有定时器"""
        window = EventWindow(redis_client=redis_client, window_seconds=10, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())
        event = make_event(resource_uid, "Created")

        def callback(ctrl_name, tp, events):
            pass

        window.add_event(controller_name, topic, event, callback)

        # 确保定时器已启动
        timer_key = f"{controller_name}:{topic}"
        assert timer_key in window._timers
        assert window._timers[timer_key].is_alive()

        # 调用 flush_all
        window.flush_all(controller_name, [topic])

        # 验证定时器已被取消
        assert timer_key not in window._timers

    def test_get_events_key_format(self, redis_client):
        """测试 Redis key 格式正确"""
        window = EventWindow(redis_client=redis_client, window_seconds=5, redis_key_prefix="test:")
        key = window._get_events_key("MyController", "my-topic")
        assert key == "test:event_window:MyController:my-topic"

    @pytest.mark.usefixtures("cleanup_redis")
    def test_flush_window_handles_merge_error(self, redis_client):
        """测试窗口刷新时合并错误不会阻止流程"""
        window = EventWindow(redis_client=redis_client, window_seconds=0.1, redis_key_prefix=self.TEST_KEY_PREFIX)
        controller_name = "TestController"
        topic = "test-topic"
        resource_uid = str(uuid.uuid4())

        # 创建会导致错误的事件序列：Created -> Created
        event1 = make_event(resource_uid, "Created", event_time="2025-01-01T00:00:01")
        event2 = make_event(resource_uid, "Created", event_time="2025-01-01T00:00:02")

        received_events = []

        def callback(ctrl_name, tp, events):
            received_events.extend(events)

        window.add_event(controller_name, topic, event1, callback)
        window.add_event(controller_name, topic, event2, callback)

        # 等待窗口刷新（不应该抛出异常）
        time.sleep(0.2)

        # 合并错误时不调用回调
        assert len(received_events) == 0
