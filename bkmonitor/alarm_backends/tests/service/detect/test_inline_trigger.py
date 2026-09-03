"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import contextmanager

from django.conf import settings

from alarm_backends.service.detect import process as detect_process
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.service.trigger import runner
from bkmonitor.define import global_config
from core.errors.alarm_backends import LockError


def test_detect_process_exposes_inline_trigger_entry():
    assert callable(getattr(DetectProcess, "run_inline_trigger", None))


def test_inline_trigger_switch_defaults_to_enabled_and_is_dynamic():
    field = global_config.ADVANCED_OPTIONS["ENABLE_DETECT_INLINE_TRIGGER"]

    assert settings.ENABLE_DETECT_INLINE_TRIGGER is True
    assert field.default is True
    assert "ENABLE_DETECT_INLINE_TRIGGER" in global_config.GLOBAL_CONFIGS


def test_detect_process_runs_trigger_only_for_items_with_anomalies(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.inline_trigger_items = [3, 1]
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", False)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item")

    processor.run_inline_trigger()

    assert run_trigger_item.call_args_list == [
        mocker.call("10", 3, executor="detect_inline"),
        mocker.call("10", 1, executor="detect_inline"),
    ]


def test_detect_push_data_defers_signal_and_records_items_when_enabled(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.inputs = {}
    processor.outputs = {
        1: [{"data": {"value": 1}}],
        2: [],
        3: [{"data": {"value": 3}}],
    }
    processor.strategy = mocker.MagicMock(
        items=[mocker.MagicMock(id=3), mocker.MagicMock(id=1), mocker.MagicMock(id=2)]
    )
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", True)
    push_abnormal_data = mocker.patch.object(processor, "push_abnormal_data", return_value=2)
    trim_item = mocker.patch.object(
        detect_process,
        "trim_item_check_results_if_trigger_idle",
        create=True,
    )
    mocker.patch.object(detect_process, "metrics")

    processor.push_data()

    push_abnormal_data.assert_called_once_with(processor.outputs, "10", publish_signal=False)
    trim_item.assert_not_called()
    assert processor.inline_trigger_items == [3, 1]


def test_detect_push_data_publishes_signal_and_records_no_inline_items_when_disabled(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.inputs = {}
    processor.outputs = {1: [{"data": {"value": 1}}]}
    processor.strategy = mocker.MagicMock(items=[mocker.MagicMock(id=1)])
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", False)
    push_abnormal_data = mocker.patch.object(processor, "push_abnormal_data", return_value=1)
    mocker.patch.object(detect_process, "metrics")

    processor.push_data()

    push_abnormal_data.assert_called_once_with(processor.outputs, "10", publish_signal=True)
    assert processor.inline_trigger_items == []


def test_detect_handle_data_does_not_collect_hot_trim_keys(mocker):
    processor = object.__new__(DetectProcess)
    processor.inputs = {1: ["point"]}
    processor.outputs = {}
    item = mocker.MagicMock(id=1)
    item.detect.return_value = []

    processor.handle_data(item)

    item.begin_check_result_trim_batch.assert_not_called()
    item.detect.assert_called_once_with(["point"])


def test_detect_process_continues_after_inline_trigger_lock_error(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.inline_trigger_items = [1, 2]
    publish_anomaly_signals = mocker.MagicMock()
    processor.publish_anomaly_signals = publish_anomaly_signals
    run_trigger_item = mocker.patch.object(
        runner,
        "run_trigger_item",
        side_effect=[LockError(msg="locked"), 1],
    )

    processor.run_inline_trigger()

    assert run_trigger_item.call_args_list == [
        mocker.call("10", 1, executor="detect_inline"),
        mocker.call("10", 2, executor="detect_inline"),
    ]
    publish_anomaly_signals.assert_called_once_with(["10.1"])


def test_detect_process_runs_inline_trigger_after_detect_lock_is_released(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    item = mocker.MagicMock(id=1)
    processor.strategy = mocker.MagicMock(items=[item])
    processor.pull_data = mocker.MagicMock()
    processor.handle_data = mocker.MagicMock()
    processor.double_check = mocker.MagicMock()
    processor.push_data = mocker.MagicMock()
    lock_state = {"active": False}

    @contextmanager
    def detect_lock(*args, **kwargs):
        lock_state["active"] = True
        try:
            yield mocker.sentinel.detect_lock
        finally:
            lock_state["active"] = False

    mocker.patch.object(detect_process, "service_lock", side_effect=detect_lock)
    mocker.patch.object(detect_process.metrics, "DETECT_PROCESS_TIME")

    def assert_lock_released():
        assert lock_state["active"] is False

    processor.run_inline_trigger = mocker.MagicMock(side_effect=assert_lock_released)

    processor.process()

    processor.run_inline_trigger.assert_called_once_with()
