"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.service.access.data import processor as access_processor
from alarm_backends.service.access.data.processor import AccessDataProcess
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
    mocker.patch.object(access_processor.settings, "ENABLE_DETECT_INLINE_TRIGGER", True)
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


def test_access_data_process_skips_recorded_items_when_disabled(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.inline_trigger_items = [(10, 1)]
    mocker.patch.object(access_processor.settings, "ENABLE_DETECT_INLINE_TRIGGER", False)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item")

    processor.run_inline_trigger()

    run_trigger_item.assert_not_called()
