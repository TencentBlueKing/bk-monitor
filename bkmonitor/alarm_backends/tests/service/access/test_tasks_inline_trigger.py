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

from alarm_backends.service.access import tasks as access_tasks


def test_run_access_data_runs_inline_trigger_after_access_lock(mocker):
    lock_state = {"active": False}
    events = []

    @contextmanager
    def access_lock(*args, **kwargs):
        lock_state["active"] = True
        try:
            yield
        finally:
            lock_state["active"] = False

    processor = mocker.MagicMock(pull_duration=0.1)
    processor.process.side_effect = lambda: events.append("process")
    processor.run_inline_trigger.side_effect = lambda: events.append("inline")
    task_bucket = mocker.MagicMock()
    task_bucket.acquire.return_value = True

    mocker.patch.object(access_tasks, "service_lock", side_effect=access_lock)
    mocker.patch.object(access_tasks, "AccessDataProcess", return_value=processor)
    mocker.patch.object(access_tasks, "TokenBucket", return_value=task_bucket)

    def report_all():
        assert lock_state["active"] is False
        events.append("report")

    mocker.patch.object(access_tasks.metrics, "report_all", side_effect=report_all)

    access_tasks.run_access_data.run("group", 60)

    assert events[:2] == ["process", "inline"]
    assert events[2:] and set(events[2:]) == {"report"}
    task_bucket.release.assert_called_once_with(0)


def test_run_access_batch_data_leaves_inline_trigger_to_main_task(mocker):
    events = []
    processor = mocker.MagicMock()

    def process():
        events.append("process")
        return "result"

    processor.process.side_effect = process
    mocker.patch.object(access_tasks, "AccessBatchDataProcess", return_value=processor)
    mocker.patch.object(access_tasks.metrics, "report_all", side_effect=lambda: events.append("report"))

    result = access_tasks.run_access_batch_data.run("group", "1.1")

    assert result == "result"
    assert events[0] == "process"
    assert events[1:] and set(events[1:]) == {"report"}
    processor.run_inline_trigger.assert_not_called()
