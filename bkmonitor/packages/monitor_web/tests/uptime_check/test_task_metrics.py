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

from monitor_web.uptime_check.resources import UptimeCheckTaskMetricsResource

BK_BIZ_ID = 2


@pytest.mark.django_db(databases="__all__")
class TestTaskMetrics:
    """集成测试：UptimeCheckTaskMetricsResource 走真实 ORM + mock ES/InfluxDB"""

    def test_metric_values_filled(self, create_task, mock_third_party):
        task = create_task(name="HTTP任务", protocol="HTTP", config={"period": 60, "url_list": ["http://a.com"]})

        def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
            if metric == "available":
                result[task.pk]["available"] = 99.5
            else:
                result[task.pk]["task_duration"] = 120.3

        mock_third_party.batch_metric.side_effect = fake_query

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk]})

        assert result["data"][task.pk]["available"] == 99.5
        assert result["data"][task.pk]["task_duration"] == 120.3
        assert result["partial"] is False
        assert result["errors"] == []

    def test_missing_task_stays_null(self, create_task, mock_third_party):
        task = create_task()

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk, 99999]})

        assert result["data"][99999]["available"] is None
        assert result["data"][99999]["task_duration"] is None

    def test_alarm_info_merged(self, create_task, mock_third_party):
        task = create_task()
        mock_third_party.alarm_info.return_value = {
            task.pk: {"alarm_num": 2, "available_alarm": True, "task_duration_alarm": False}
        }

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk]})

        assert result["data"][task.pk]["alarm_num"] == 2
        assert result["data"][task.pk]["available_alarm"] is True

    def test_alarm_query_failure_partial(self, create_task, mock_third_party):
        task = create_task()
        mock_third_party.alarm_info.side_effect = Exception("ES down")

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk]})

        assert result["partial"] is True
        assert "alarm_query_failed" in result["errors"]
        # 降级为默认值
        assert result["data"][task.pk]["alarm_num"] == 0

    def test_metric_query_failure_degrades(self, create_task, mock_third_party):
        task = create_task()
        mock_third_party.batch_metric.side_effect = Exception("influxdb down")

        result = UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk]})

        # InfluxDB 异常在线程中被捕获，指标保持 None
        assert result["data"][task.pk]["available"] is None
        assert result["data"][task.pk]["task_duration"] is None

    def test_grouped_by_protocol_and_period(self, create_task, mock_third_party):
        create_task(name="HTTP60", protocol="HTTP", config={"period": 60, "url_list": ["http://a.com"]})
        create_task(name="HTTP60b", protocol="HTTP", config={"period": 60, "url_list": ["http://b.com"]})
        _task3 = create_task(
            name="TCP300", protocol="TCP", config={"period": 300, "port": "80", "ip_list": ["127.0.0.1"]}
        )

        from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel

        all_ids = list(
            UptimeCheckTaskModel.objects.filter(bk_biz_id=BK_BIZ_ID, is_deleted=False).values_list("pk", flat=True)
        )

        UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": all_ids})

        # 2种协议 x 2个指标 = 4次调用
        assert mock_third_party.batch_metric.call_count == 4
        called_labels = {
            (call.args[0], call.args[2], call.args[4]) for call in mock_third_party.batch_metric.call_args_list
        }
        assert called_labels == {
            ("available", "uptimecheck_http", 60),
            ("task_duration", "uptimecheck_http", 60),
            ("available", "uptimecheck_tcp", 300),
            ("task_duration", "uptimecheck_tcp", 300),
        }

    def test_empty_task_ids_rejected(self):
        with pytest.raises(Exception):
            UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": []})

    def test_task_ids_limit(self):
        with pytest.raises(Exception):
            UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": list(range(501))})

    def test_alarm_query_uses_task_ids_filter(self, create_task, mock_third_party):
        """验证 ES 告警查询传入了 task_ids 参数限定范围"""
        task = create_task()

        UptimeCheckTaskMetricsResource().request({"bk_biz_id": BK_BIZ_ID, "task_ids": [task.pk]})

        mock_third_party.alarm_info.assert_called_once_with(BK_BIZ_ID, task_ids=[task.pk])
