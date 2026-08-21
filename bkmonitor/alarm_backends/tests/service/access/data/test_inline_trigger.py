"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from alarm_backends.service.access.data import processor as access_processor
from alarm_backends.service.access.data.processor import AccessBatchDataProcess, AccessDataProcess
from alarm_backends.service.detect import process as detect_process
from alarm_backends.service.trigger import runner
from core.errors.alarm_backends import LockError


def test_access_data_process_exposes_inline_trigger_entry():
    assert callable(getattr(AccessDataProcess, "run_inline_trigger", None))


def test_access_merge_records_item_pair_after_anomaly_is_pushed(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.record_list = []
    processor.inline_trigger_items = []
    item = mocker.MagicMock(id=1, no_data_config={"is_enabled": False})
    item.strategy.id = 10
    processor.items = [item]

    inline_candidate = mocker.MagicMock()
    inline_candidate.outputs = {1: ["anomaly"]}
    inline_candidate.inline_trigger_items = [1]
    detect_process_class = mocker.patch.object(
        detect_process,
        "DetectProcess",
        return_value=inline_candidate,
    )
    mocker.patch.object(access_processor, "PriorityChecker")
    mocker.patch.object(access_processor, "metrics")

    processor._detect_and_push_abnormal()

    detect_process_class.assert_called_once_with(10)
    inline_candidate.push_data.assert_called_once_with()
    assert processor.inline_trigger_items == [(10, 1)]


def test_access_data_process_runs_recorded_items_and_continues_after_lock_error(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.inline_trigger_items = [(10, 1), (10, 2)]
    publish_anomaly_signals = mocker.MagicMock()
    processor.publish_anomaly_signals = publish_anomaly_signals
    mocker.patch.object(access_processor.settings, "ENABLE_DETECT_INLINE_TRIGGER", False)
    run_trigger_item = mocker.patch.object(
        runner,
        "run_trigger_item",
        side_effect=[LockError(msg="locked"), 1],
    )

    processor.run_inline_trigger()

    assert run_trigger_item.call_args_list == [
        mocker.call(10, 1, executor="detect_inline"),
        mocker.call(10, 2, executor="detect_inline"),
    ]
    publish_anomaly_signals.assert_called_once_with(["10.1"])


def test_access_merge_records_no_inline_item_when_detect_publishes_signal(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.record_list = []
    processor.inline_trigger_items = []
    item = mocker.MagicMock(id=1, no_data_config={"is_enabled": False})
    item.strategy.id = 10
    processor.items = [item]

    inline_candidate = mocker.MagicMock()
    inline_candidate.outputs = {1: ["anomaly"]}
    inline_candidate.inline_trigger_items = []
    mocker.patch.object(detect_process, "DetectProcess", return_value=inline_candidate)
    mocker.patch.object(access_processor, "PriorityChecker")
    mocker.patch.object(access_processor, "metrics")

    processor._detect_and_push_abnormal()

    assert processor.inline_trigger_items == []


def test_access_batch_result_returns_inline_trigger_items(mocker):
    processor = object.__new__(AccessBatchDataProcess)
    processor.strategy_group_key = "group"
    processor.batch_timestamp = 1
    processor.sub_task_id = "1.2"
    processor.process_counts = {}
    processor.inline_trigger_items = [(10, 1), (10, 2)]
    mocker.patch.object(AccessDataProcess, "process", return_value=None)
    batch_result_key = mocker.patch.object(access_processor.key, "ACCESS_BATCH_DATA_RESULT_KEY")
    batch_result_key.get_key.return_value = "batch-result"

    processor.process()

    payload = json.loads(batch_result_key.client.lpush.call_args.args[1])
    assert payload["inline_trigger_items"] == [[10, 1], [10, 2]]


def test_access_main_collects_unique_inline_items_from_batch_results(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.batch_timestamp = 1
    processor.batch_count = 3
    processor.sub_task_id = "1.1"
    processor.process_counts = {}
    processor.inline_trigger_items = [(10, 1)]
    processor.batch_log = mocker.MagicMock()

    batch_result_key = mocker.patch.object(access_processor.key, "ACCESS_BATCH_DATA_RESULT_KEY")
    batch_result_key.get_key.return_value = "batch-result"
    batch_result_key.client.brpop.side_effect = [
        (
            "batch-result",
            json.dumps(
                {
                    "sub_task_id": "1.2",
                    "result": True,
                    "error": "",
                    "process_counts": {},
                    "inline_trigger_items": [[10, 1], [10, 2]],
                }
            ),
        ),
        (
            "batch-result",
            json.dumps(
                {
                    "sub_task_id": "1.3",
                    "result": True,
                    "error": "",
                    "process_counts": {},
                    "inline_trigger_items": [[10, 2], [11, 3]],
                }
            ),
        ),
    ]
    mocker.patch.object(access_processor.base.BaseAccessProcess, "process", return_value=None)
    mocker.patch.object(access_processor, "metrics")

    processor.process()

    assert processor.inline_trigger_items == [(10, 1), (10, 2), (11, 3)]
