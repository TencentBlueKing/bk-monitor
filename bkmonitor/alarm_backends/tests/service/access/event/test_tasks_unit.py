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
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call


TASKS_PATH = Path(__file__).parents[4] / "service" / "access" / "tasks.py"


class FakeApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class FakePartitionProcessor:
    instances = []
    should_continue = False

    def __init__(self, data_id, partition=None):
        self.data_id = data_id
        self.partition = partition
        self.process = Mock()
        self.finish_partition_task = Mock(return_value=self.should_continue)
        self.instances.append(self)


def install_module(monkeypatch, name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


def load_tasks(monkeypatch):
    FakePartitionProcessor.instances = []
    FakePartitionProcessor.should_continue = False
    task_key = SimpleNamespace(
        client=Mock(),
        get_key=Mock(return_value="task-key"),
    )
    install_module(
        monkeypatch,
        "alarm_backends.core.cache",
        key=SimpleNamespace(EVENT_PARTITION_TASK_KEY=task_key),
    )
    install_module(monkeypatch, "alarm_backends.core.lock.service_lock", service_lock=Mock())
    install_module(monkeypatch, "alarm_backends.service.access", ACCESS_TYPE_TO_CLASS={})
    install_module(
        monkeypatch,
        "alarm_backends.service.access.data",
        AccessBatchDataProcess=Mock(),
        AccessDataProcess=Mock(),
    )
    install_module(monkeypatch, "alarm_backends.service.access.data.token", TokenBucket=Mock())
    install_module(
        monkeypatch,
        "alarm_backends.service.access.event.processor",
        AccessCustomEventGlobalProcess=Mock(),
    )
    install_module(
        monkeypatch,
        "alarm_backends.service.access.event.processorv2",
        AccessCustomEventGlobalProcessV2=FakePartitionProcessor,
    )
    start_task = Mock(return_value="active-token")
    keep_alive = Mock(side_effect=lambda **kwargs: nullcontext())
    install_module(
        monkeypatch,
        "alarm_backends.service.access.event.queue",
        keep_partition_task_alive=keep_alive,
        start_partition_task=start_task,
    )
    install_module(monkeypatch, "alarm_backends.service.access.incident", AccessIncidentProcess=Mock())
    install_module(monkeypatch, "alarm_backends.service.scheduler.app", app=FakeApp())
    metrics = SimpleNamespace(report_all=Mock())
    install_module(monkeypatch, "core.prometheus", metrics=metrics)

    spec = importlib.util.spec_from_file_location("access_tasks_under_test", TASKS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.settings = SimpleNamespace(
        ACCESS_EVENT_PARTITION_TASK_TTL=30,
        ACCESS_EVENT_PARTITION_TASK_MAX_LEASE=3600,
    )
    module.run_access_event_handler_v2.delay = Mock()
    module._test_start_task = start_task
    module._test_keep_alive = keep_alive
    return module


def test_legacy_task_keeps_existing_processor_construction(monkeypatch):
    tasks = load_tasks(monkeypatch)

    tasks.run_access_event_handler_v2(1000)

    processor = FakePartitionProcessor.instances[-1]
    assert processor.data_id == 1000
    assert processor.partition is None
    processor.process.assert_called_once_with()
    processor.finish_partition_task.assert_not_called()
    tasks.run_access_event_handler_v2.delay.assert_not_called()


def test_partition_zero_finishes_claim_and_continues_same_task(monkeypatch):
    FakePartitionProcessor.should_continue = True
    tasks = load_tasks(monkeypatch)
    FakePartitionProcessor.should_continue = True

    tasks.run_access_event_handler_v2(1000, partition=0, partition_task_token="token")

    processor = FakePartitionProcessor.instances[-1]
    assert processor.partition == 0
    processor.process.assert_called_once_with()
    processor.finish_partition_task.assert_called_once_with("active-token")
    assert tasks.run_access_event_handler_v2.delay.call_args_list == [
        call(1000, partition=0, partition_task_token="active-token")
    ]


def test_partition_task_does_not_continue_after_queue_drain(monkeypatch):
    tasks = load_tasks(monkeypatch)

    tasks.run_access_event_handler_v2(1000, partition=1, partition_task_token="token")

    processor = FakePartitionProcessor.instances[-1]
    processor.finish_partition_task.assert_called_once_with("active-token")
    tasks.run_access_event_handler_v2.delay.assert_not_called()


def test_stale_partition_task_exits_before_processor_pull(monkeypatch):
    tasks = load_tasks(monkeypatch)
    tasks._test_start_task.return_value = None

    tasks.run_access_event_handler_v2(1000, partition=1, partition_task_token="stale-token")

    assert FakePartitionProcessor.instances == []
