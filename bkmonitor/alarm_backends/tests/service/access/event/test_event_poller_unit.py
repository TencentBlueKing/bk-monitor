"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import importlib.util
import sys
import types
from collections import defaultdict, namedtuple
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fakeredis
import pytest


EVENT_DIR = Path(__file__).parents[4] / "service" / "access" / "event"
TopicPartition = namedtuple("TopicPartition", ["topic", "partition"])


class FakeKey:
    def __init__(self, client, key_template, ttl=60):
        self.client = client
        self.key_template = key_template
        self.ttl = ttl

    def get_key(self, **kwargs):
        return self.key_template.format(**kwargs)


def load_source_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def event_poller_module(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    fake_key = SimpleNamespace(
        EVENT_LIST_KEY=FakeKey(client, "access.event.{data_id}"),
        EVENT_PARTITION_LIST_KEY=FakeKey(client, "access.event.{data_id}.partition.{partition}"),
        EVENT_SIGNAL_KEY=FakeKey(client, "access.event.signal"),
        EVENT_PARTITION_SIGNAL_KEY=FakeKey(client, "access.event.partition.signal"),
        EVENT_PARTITION_TASK_KEY=FakeKey(client, "access.event.{data_id}.partition.{partition}.task"),
    )

    cache_module = types.ModuleType("alarm_backends.core.cache")
    cache_module.key = fake_key
    monkeypatch.setitem(sys.modules, "alarm_backends.core.cache", cache_module)

    task = Mock()
    tasks_module = types.ModuleType("alarm_backends.service.access.tasks")
    tasks_module.run_access_event_handler_v2 = task
    monkeypatch.setitem(sys.modules, "alarm_backends.service.access.tasks", tasks_module)

    queue_module = load_source_module("access_event_queue", EVENT_DIR / "queue.py")
    monkeypatch.setitem(sys.modules, "alarm_backends.service.access.event.queue", queue_module)

    common_utils_module = types.ModuleType("bkmonitor.utils.common_utils")
    common_utils_module.safe_int = lambda value: int(value)
    monkeypatch.setitem(sys.modules, "bkmonitor.utils.common_utils", common_utils_module)

    thread_backend_module = types.ModuleType("bkmonitor.utils.thread_backend")
    thread_backend_module.InheritParentThread = Mock()
    monkeypatch.setitem(sys.modules, "bkmonitor.utils.thread_backend", thread_backend_module)

    constants_module = types.ModuleType("constants.strategy")
    constants_module.MAX_RETRIEVE_NUMBER = 10000
    monkeypatch.setitem(sys.modules, "constants.strategy", constants_module)

    drf_module = types.ModuleType("core.drf_resource")
    drf_module.api = Mock()
    monkeypatch.setitem(sys.modules, "core.drf_resource", drf_module)

    metrics = SimpleNamespace(
        ACCESS_EVENT_QUEUE_DROPPED_COUNT=Mock(),
        report_all=Mock(),
    )
    metrics.ACCESS_EVENT_QUEUE_DROPPED_COUNT.labels.return_value.inc = Mock()
    prometheus_module = types.ModuleType("core.prometheus")
    prometheus_module.metrics = metrics
    monkeypatch.setitem(sys.modules, "core.prometheus", prometheus_module)

    module = load_source_module("event_poller_under_test", EVENT_DIR / "event_poller.py")
    module.time.sleep = Mock()
    module.settings = SimpleNamespace(
        ENABLE_ACCESS_EVENT_PARTITION_QUEUE=False,
        ACCESS_EVENT_QUEUE_MAX_LENGTH=10,
        ACCESS_EVENT_PARTITION_TASK_TTL=30,
    )
    module._test_client = client
    module._test_key = fake_key
    module._test_task = task
    return module


def make_poller(module):
    poller = module.EventPoller.__new__(module.EventPoller)
    poller.topics_map = {"topic": 1000}
    poller.polled_info = defaultdict(int)
    poller.pod_id = "test"
    poller.consumer = Mock()
    poller.consumer.partitions_for_topic.return_value = {0, 1}
    poller.topic_partition_counts = {"topic": 2}
    return poller


def test_default_mode_keeps_legacy_queue_and_signal(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module._test_client.pipeline = Mock(wraps=event_poller_module._test_client.pipeline)

    poller.push_to_redis("topic", ["older", "newer"])

    assert event_poller_module._test_client.lrange("access.event.1000", 0, -1) == ["newer", "older"]
    assert event_poller_module._test_client.smembers("access.event.signal") == {"1000"}
    assert event_poller_module._test_client.keys("access.event.1000.partition.*") == []
    event_poller_module._test_client.pipeline.assert_not_called()


def test_partition_mode_writes_isolated_queue_with_total_limit_share(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True

    poller.push_to_redis("topic", ["0", "1", "2", "3", "4", "5"], partition=1)

    assert event_poller_module._test_client.lrange("access.event.1000.partition.1", 0, -1) == [
        "5",
        "4",
        "3",
        "2",
        "1",
    ]
    assert event_poller_module._test_client.smembers("access.event.partition.signal") == {"1000:1"}
    assert event_poller_module._test_client.exists("access.event.1000") == 0
    event_poller_module._test_task.delay.assert_called_once()
    assert event_poller_module._test_task.delay.call_args.kwargs["partition"] == 1
    assert event_poller_module._test_task.delay.call_args.kwargs["partition_task_token"]

    poller.push_to_redis("topic", ["6"], partition=1)
    assert event_poller_module._test_task.delay.call_count == 1


def test_partition_zero_does_not_fall_back_to_legacy_queue(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True

    poller.push_to_redis("topic", ["event"], partition=0)

    assert event_poller_module._test_client.lrange("access.event.1000.partition.0", 0, -1) == ["event"]
    assert event_poller_module._test_client.exists("access.event.1000") == 0
    assert event_poller_module._test_task.delay.call_args.kwargs["partition"] == 0


def test_group_messages_preserves_legacy_shape_when_disabled(event_poller_module):
    poller = make_poller(event_poller_module)
    messages = [
        SimpleNamespace(topic="topic", partition=0, value="p0"),
        SimpleNamespace(topic="topic", partition=1, value="p1"),
    ]

    assert poller.group_messages(messages) == {"topic": ["p0", "p1"]}


def test_group_messages_separates_partitions_when_enabled(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True
    messages = [
        SimpleNamespace(topic="topic", partition=0, value="p0"),
        SimpleNamespace(topic="topic", partition=1, value="p1"),
    ]

    assert poller.group_messages(messages) == {("topic", 0): ["p0"], ("topic", 1): ["p1"]}


def test_two_pollers_share_signal_but_only_one_dispatches_partition_task(event_poller_module):
    poller = make_poller(event_poller_module)
    another_poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True
    event_poller_module._test_client.sadd("access.event.partition.signal", "1000:2")

    poller.kick_tasks_once()
    another_poller.kick_tasks_once()

    assert len(event_poller_module._test_task.delay.call_args_list) == 1
    partition_call = event_poller_module._test_task.delay.call_args_list[0]
    assert partition_call.args == ("1000",)
    assert partition_call.kwargs["partition"] == 2
    assert partition_call.kwargs["partition_task_token"]


def test_partition_recovery_scan_runs_when_producer_flag_is_disabled(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module._test_client.sadd("access.event.partition.signal", "1000:2")

    poller.kick_tasks_once()

    assert event_poller_module._test_task.delay.call_args.kwargs["partition"] == 2


def test_partition_signal_recovers_after_initial_task_publish_failure(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True
    event_poller_module._test_task.delay.side_effect = RuntimeError("publish failed")

    with pytest.raises(RuntimeError, match="publish failed"):
        poller.push_to_redis("topic", ["event"], partition=0)

    assert event_poller_module._test_client.smembers("access.event.partition.signal") == {"1000:0"}
    event_poller_module._test_client.delete("access.event.1000.partition.0.task")
    event_poller_module._test_task.delay.side_effect = None

    poller.kick_tasks_once()

    assert event_poller_module._test_task.delay.call_count == 2
    assert event_poller_module._test_task.delay.call_args.kwargs["partition"] == 0


def test_partition_mode_does_not_poll_without_full_topic_metadata(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True
    poller.consumer.partitions_for_topic.return_value = None

    assert poller.poll_once() == []
    poller.consumer.poll.assert_not_called()
    event_poller_module.time.sleep.assert_called_once_with(1)


def test_partition_count_uses_full_metadata_not_local_assignment(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.settings.ENABLE_ACCESS_EVENT_PARTITION_QUEUE = True
    poller.consumer.partitions_for_topic.return_value = {0, 1, 2}
    poller.consumer.assignment.return_value = {TopicPartition(topic="topic", partition=0)}
    poller.consumer.poll.return_value = {}

    assert poller.poll_once() == []
    assert poller.topic_partition_counts == {"topic": 3}


def test_legacy_mode_does_not_require_partition_metadata(event_poller_module):
    poller = make_poller(event_poller_module)
    poller.consumer.assignment.return_value = set()
    poller.consumer.poll.return_value = {}

    assert poller.poll_once() == []
    poller.consumer.partitions_for_topic.assert_not_called()
    poller.consumer.poll.assert_called_once()


def test_metrics_report_failure_is_isolated(event_poller_module):
    poller = make_poller(event_poller_module)
    event_poller_module.metrics.report_all.side_effect = RuntimeError("report failed")

    poller.report_metrics()
