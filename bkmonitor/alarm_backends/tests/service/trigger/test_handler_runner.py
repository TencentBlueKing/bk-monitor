"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.service.trigger import handler as trigger_handler
from core.errors.alarm_backends import LockError


def test_handler_delegates_processing_to_public_runner(mocker):
    anomaly_signal_key = mocker.patch.object(trigger_handler, "ANOMALY_SIGNAL_KEY")
    anomaly_signal_key.client.rpop.return_value = "1.2"
    run_trigger_item = mocker.patch.object(trigger_handler, "run_trigger_item", create=True)
    mocker.patch.object(trigger_handler.metrics, "report_all")

    handler = trigger_handler.TriggerHandler()
    handler.DATA_FETCH_TIMEOUT = 0
    handler.handle()

    run_trigger_item.assert_called_once_with("1", "2", executor="trigger_worker")


def test_handler_requeues_signal_when_runner_cannot_get_lock(mocker):
    anomaly_signal_key = mocker.patch.object(trigger_handler, "ANOMALY_SIGNAL_KEY")
    anomaly_signal_key.client.rpop.return_value = "1.2"
    run_trigger_item = mocker.patch.object(
        trigger_handler,
        "run_trigger_item",
        side_effect=LockError(msg="locked"),
    )
    report_all = mocker.patch.object(trigger_handler.metrics, "report_all")

    handler = trigger_handler.TriggerHandler()
    handler.DATA_FETCH_TIMEOUT = 0
    handler.handle()

    run_trigger_item.assert_called_once_with("1", "2", executor="trigger_worker")
    anomaly_signal_key.client.delay.assert_called_once_with(
        "rpush",
        anomaly_signal_key.get_key.return_value,
        "1.2",
        delay=1,
    )
    report_all.assert_not_called()
