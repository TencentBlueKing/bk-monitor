"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.core.processor import base
from alarm_backends.core.processor.base import BaseAbnormalPushProcessor


def test_push_abnormal_data_can_defer_signal_until_inline_trigger(mocker):
    anomaly_list_key = mocker.patch.object(base.key, "ANOMALY_LIST_KEY")
    anomaly_signal_key = mocker.patch.object(base.key, "ANOMALY_SIGNAL_KEY")
    list_pipeline = anomaly_list_key.client.pipeline.return_value

    anomaly_count = BaseAbnormalPushProcessor.push_abnormal_data(
        {1: [{"data": {"value": 1}}]},
        strategy_id="10",
        publish_signal=False,
    )

    assert anomaly_count == 1
    list_pipeline.lpush.assert_called_once()
    list_pipeline.expire.assert_called_once()
    list_pipeline.execute.assert_called_once_with()
    anomaly_signal_key.client.pipeline.assert_not_called()


def test_push_abnormal_data_publishes_signal_by_default(mocker):
    anomaly_list_key = mocker.patch.object(base.key, "ANOMALY_LIST_KEY")
    anomaly_signal_key = mocker.patch.object(base.key, "ANOMALY_SIGNAL_KEY")
    anomaly_signal_key.get_key.return_value = "detect.anomaly.signal"
    signal_pipeline = anomaly_signal_key.client.pipeline.return_value

    BaseAbnormalPushProcessor.push_abnormal_data({1: [{"data": {"value": 1}}]}, strategy_id="10")

    anomaly_list_key.client.pipeline.return_value.execute.assert_called_once_with()
    signal_pipeline.lpush.assert_called_once_with("detect.anomaly.signal", "10.1")
    signal_pipeline.execute.assert_called_once_with()


def test_publish_anomaly_signals_pushes_deferred_item(mocker):
    anomaly_signal_key = mocker.patch.object(base.key, "ANOMALY_SIGNAL_KEY")
    anomaly_signal_key.get_key.return_value = "detect.anomaly.signal"
    signal_pipeline = anomaly_signal_key.client.pipeline.return_value

    BaseAbnormalPushProcessor.publish_anomaly_signals(["10.1"])

    signal_pipeline.lpush.assert_called_once_with("detect.anomaly.signal", "10.1")
    signal_pipeline.expire.assert_called_once_with("detect.anomaly.signal", anomaly_signal_key.ttl)
    signal_pipeline.execute.assert_called_once_with()
