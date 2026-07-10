"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


PROCESSOR_PATH = Path(__file__).parents[4] / "service" / "access" / "event" / "processorv2.py"


def get_class_node():
    tree = ast.parse(PROCESSOR_PATH.read_text())
    return next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AccessCustomEventGlobalProcessV2"
    )


def get_method_node(class_node, method_name):
    return next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == method_name)


def load_method(method_name, **namespace):
    method = get_method_node(get_class_node(), method_name)
    method_module = ast.Module(body=[method], type_ignores=[])
    ast.fix_missing_locations(method_module)
    exec(compile(method_module, PROCESSOR_PATH, "exec"), namespace)
    return namespace[method_name]


def test_processor_constructor_accepts_optional_partition():
    init = get_method_node(get_class_node(), "__init__")
    argument_names = [argument.arg for argument in init.args.args]

    assert "partition" in argument_names


def test_processor_uses_partition_queue_and_partition_zero_safe_branching():
    source = PROCESSOR_PATH.read_text()

    assert "EVENT_PARTITION_LIST_KEY" in source
    assert "get_event_queue_key" in source
    assert "get_event_lock_id" in source
    assert "partition is None" in source


def test_processor_replaces_full_delete_with_gradual_trim():
    pull_method = get_method_node(get_class_node(), "_pull_from_redis")
    source = ast.get_source_segment(PROCESSOR_PATH.read_text(), pull_method)

    assert "pull_event_records" in source
    assert ".delete(data_channel)" not in source


def test_processor_exposes_partition_task_finalizer():
    class_node = get_class_node()
    finish_method = get_method_node(class_node, "finish_partition_task")
    source = ast.get_source_segment(PROCESSOR_PATH.read_text(), finish_method)

    assert "finish_partition_task" in source
    assert "EVENT_PARTITION_SIGNAL_KEY" in source
    assert "EVENT_PARTITION_TASK_KEY" in source


def test_partition_zero_pulls_partition_queue_atomically():
    client = Mock()
    client.llen.return_value = 2
    pull_records = Mock(return_value=(["older", "newer"], 0))
    legacy_key = Mock()
    partition_key = Mock()
    partition_key.get_key.return_value = "partition-queue"
    event_key = Mock(DATA_LIST_KEY=SimpleNamespace(client=client))
    event_key.EVENT_LIST_KEY = legacy_key
    event_key.EVENT_PARTITION_LIST_KEY = partition_key
    processor = SimpleNamespace(data_id=1000, partition=0, topic="topic")
    method = load_method(
        "_pull_from_redis",
        key=event_key,
        get_event_queue_key=lambda data_id, partition, legacy_key, partition_key: partition_key.get_key(
            data_id=data_id, partition=partition
        ),
        pull_event_records=pull_records,
        settings=SimpleNamespace(ACCESS_EVENT_QUEUE_MAX_LENGTH=10),
        metrics=Mock(),
        logger=Mock(),
        MAX_RETRIEVE_NUMBER=10000,
    )

    assert method(processor, max_records=2) == ["older", "newer"]
    partition_key.get_key.assert_called_once_with(data_id=1000, partition=0)
    pull_records.assert_called_once_with(client, "partition-queue", 2, max_length=0)
    client.lrange.assert_not_called()
    client.ltrim.assert_not_called()


def test_legacy_queue_below_cap_keeps_existing_pull_and_trim_sequence():
    client = Mock()
    client.llen.return_value = 2
    client.lrange.return_value = ["older", "newer"]
    legacy_key = Mock()
    legacy_key.get_key.return_value = "legacy-queue"
    event_key = Mock(DATA_LIST_KEY=SimpleNamespace(client=client))
    event_key.EVENT_LIST_KEY = legacy_key
    event_key.EVENT_PARTITION_LIST_KEY = Mock()
    pull_records = Mock()
    processor = SimpleNamespace(data_id=1000, partition=None, topic="topic")
    method = load_method(
        "_pull_from_redis",
        key=event_key,
        get_event_queue_key=lambda data_id, partition, legacy_key, partition_key: legacy_key.get_key(data_id=data_id),
        pull_event_records=pull_records,
        settings=SimpleNamespace(ACCESS_EVENT_QUEUE_MAX_LENGTH=10),
        metrics=Mock(),
        logger=Mock(),
        MAX_RETRIEVE_NUMBER=10000,
    )

    assert method(processor, max_records=2) == ["older", "newer"]
    client.lrange.assert_called_once_with("legacy-queue", -2, -1)
    client.ltrim.assert_called_once_with("legacy-queue", 0, -3)
    pull_records.assert_not_called()
