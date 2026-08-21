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

from alarm_backends.service.detect import process as detect_process
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.service.trigger import runner
from core.errors.alarm_backends import LockError


def test_detect_process_exposes_inline_trigger_entry():
    assert callable(getattr(DetectProcess, "run_inline_trigger", None))


def test_detect_process_runs_trigger_only_for_items_with_anomalies(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.outputs = {1: ["anomaly"], 2: [], 3: ["anomaly"]}
    processor.strategy = mocker.MagicMock(
        items=[mocker.MagicMock(id=3), mocker.MagicMock(id=1), mocker.MagicMock(id=2)]
    )
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", True)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item")

    processor.run_inline_trigger()

    assert run_trigger_item.call_args_list == [
        mocker.call("10", 3, executor="detect_inline"),
        mocker.call("10", 1, executor="detect_inline"),
    ]


def test_detect_process_skips_inline_trigger_when_disabled(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.outputs = {1: ["anomaly"]}
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", False)
    run_trigger_item = mocker.patch.object(runner, "run_trigger_item")

    processor.run_inline_trigger()

    run_trigger_item.assert_not_called()


def test_detect_process_continues_after_inline_trigger_lock_error(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.outputs = {1: ["anomaly"], 2: ["anomaly"]}
    processor.strategy = mocker.MagicMock(items=[mocker.MagicMock(id=1), mocker.MagicMock(id=2)])
    mocker.patch.object(detect_process.settings, "ENABLE_DETECT_INLINE_TRIGGER", True)
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


def test_detect_process_runs_inline_trigger_after_detect_lock_is_released(mocker):
    processor = object.__new__(DetectProcess)
    processor.strategy_id = "10"
    processor.strategy = mocker.MagicMock(items=[])
    processor.push_data = mocker.MagicMock()
    lock_state = {"active": False}

    @contextmanager
    def detect_lock(*args, **kwargs):
        lock_state["active"] = True
        try:
            yield
        finally:
            lock_state["active"] = False

    mocker.patch.object(detect_process, "service_lock", side_effect=detect_lock)
    mocker.patch.object(detect_process.metrics, "DETECT_PROCESS_TIME")

    def assert_lock_released():
        assert lock_state["active"] is False

    processor.run_inline_trigger = mocker.MagicMock(side_effect=assert_lock_released)

    processor.process()

    processor.run_inline_trigger.assert_called_once_with()
