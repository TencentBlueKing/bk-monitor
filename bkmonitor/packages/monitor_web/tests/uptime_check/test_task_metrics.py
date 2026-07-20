"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from bk_monitor_base.uptime_check import UptimeCheckTask

from monitor_web.uptime_check.resources import UptimeCheckTaskMetricsResource


def make_task(task_id: int, protocol: str = "HTTP", period: int = 60) -> UptimeCheckTask:
    return UptimeCheckTask(
        bk_tenant_id="tenant",
        id=task_id,
        bk_biz_id=2,
        name=f"任务{task_id}",
        protocol=protocol,
        status="running",
        config={"period": period},
    )


@pytest.fixture
def patch_env(mocker):
    mocker.patch("monitor_web.uptime_check.resources.get_request_tenant_id", return_value="tenant")
    mocker.patch("monitor_web.uptime_check.resources._query_task_alarm_info", return_value={})
    return mocker


@pytest.mark.django_db(databases="__all__")
class TestTaskMetrics:
    def test_metric_values_filled(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10)])

        def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
            if metric == "available":
                result[10]["available"] = 99.5
            else:
                result[10]["task_duration"] = 120.3

        mocker.patch("monitor_web.uptime_check.resources._batch_query_task_metric", side_effect=fake_query)

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": [10]})

        assert result[10] == {
            "task_id": 10,
            "available": 99.5,
            "task_duration": 120.3,
            "available_alarm": False,
            "task_duration_alarm": False,
            "alarm_num": 0,
        }

    def test_missing_task_stays_null(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10)])
        mocker.patch("monitor_web.uptime_check.resources._batch_query_task_metric")

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": [10, 999]})

        assert result[999]["task_id"] == 999
        assert result[999]["available"] is None
        assert result[999]["task_duration"] is None

    def test_alarm_info_merged(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10)])
        mocker.patch("monitor_web.uptime_check.resources._batch_query_task_metric")
        mocker.patch(
            "monitor_web.uptime_check.resources._query_task_alarm_info",
            return_value={10: {"alarm_num": 2, "available_alarm": True, "task_duration_alarm": False}},
        )

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": [10, 11]})

        assert result[10]["alarm_num"] == 2
        assert result[10]["available_alarm"] is True
        assert result[11]["alarm_num"] == 0

    def test_query_failure_degrades_to_null(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10)])
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=Exception("influxdb down"),
        )

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": [10]})

        assert result[10]["available"] is None
        assert result[10]["task_duration"] is None

    def test_grouped_by_protocol_and_period(self, patch_env, mocker):
        # 2种协议 x 2个周期 x 2个指标 = 每个组合各查一次
        mocker.patch(
            "monitor_web.uptime_check.resources.list_tasks",
            return_value=[
                make_task(1, protocol="HTTP", period=60),
                make_task(2, protocol="HTTP", period=60),
                make_task(3, protocol="TCP", period=300),
            ],
        )
        batch_query = mocker.patch("monitor_web.uptime_check.resources._batch_query_task_metric")

        UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": [1, 2, 3]})

        assert batch_query.call_count == 4
        called_labels = {(call.args[0], call.args[2], call.args[4]) for call in batch_query.call_args_list}
        assert called_labels == {
            ("available", "uptimecheck_http", 60),
            ("task_duration", "uptimecheck_http", 60),
            ("available", "uptimecheck_tcp", 300),
            ("task_duration", "uptimecheck_tcp", 300),
        }

    def test_empty_task_ids_rejected(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": []})

    def test_task_ids_limit(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckTaskMetricsResource().request({"bk_biz_id": 2, "task_ids": list(range(501))})
