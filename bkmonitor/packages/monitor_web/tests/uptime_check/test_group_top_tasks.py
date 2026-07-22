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

from monitor_web.uptime_check.resources import UptimeCheckGroupTopTasksResource

BK_BIZ_ID = 2


@pytest.mark.django_db(databases="__all__")
class TestGroupTopTasks:
    """集成测试：UptimeCheckGroupTopTasksResource 走真实 ORM + mock ES/InfluxDB"""

    def test_sorted_by_available_null_worst(self, create_task, create_group, mock_third_party):
        task1 = create_task(name="任务1", protocol="HTTP", config={"period": 60, "url_list": ["http://a.com"]})
        task2 = create_task(name="任务2", protocol="HTTP", config={"period": 60, "url_list": ["http://b.com"]})
        task3 = create_task(name="任务3", protocol="HTTP", config={"period": 60, "url_list": ["http://c.com"]})
        task4 = create_task(name="任务4", protocol="HTTP", config={"period": 60, "url_list": ["http://d.com"]})
        group = create_group(name="分组", tasks=[task1, task2, task3, task4])

        # task4 无数据(null) 视为最差排最前
        def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
            if metric == "available":
                if task1.pk in result:
                    result[task1.pk]["available"] = 99.0
                if task2.pk in result:
                    result[task2.pk]["available"] = 82.5
                if task3.pk in result:
                    result[task3.pk]["available"] = 95.0

        mock_third_party.batch_metric.side_effect = fake_query

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk]})

        top_tasks = result["data"][group.pk]["top_tasks"]
        assert [item["task_id"] for item in top_tasks] == [task4.pk, task2.pk, task3.pk]
        assert top_tasks[0]["available"] is None
        assert top_tasks[1]["available"] == 82.5

    def test_stoped_backfill(self, create_task, create_group, mock_third_party):
        task1 = create_task(name="运行中", status="running", config={"period": 60, "url_list": ["http://a.com"]})
        task2 = create_task(name="停用1", status="stoped", config={"period": 60, "url_list": ["http://b.com"]})
        task3 = create_task(name="停用2", status="stoped", config={"period": 60, "url_list": ["http://c.com"]})
        group = create_group(name="分组", tasks=[task1, task2, task3])

        def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
            if metric == "available" and task1.pk in result:
                result[task1.pk]["available"] = 99.0

        mock_third_party.batch_metric.side_effect = fake_query

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk]})

        top_tasks = result["data"][group.pk]["top_tasks"]
        # 非停用优先，不足 top_n 用停用任务补齐
        assert top_tasks[0]["task_id"] == task1.pk
        assert top_tasks[1]["status"] == "stoped"
        assert len(top_tasks) == 3

    def test_top_n_param(self, create_task, create_group, mock_third_party):
        task1 = create_task(name="任务1", config={"period": 60, "url_list": ["http://a.com"]})
        task2 = create_task(name="任务2", config={"period": 60, "url_list": ["http://b.com"]})
        task3 = create_task(name="任务3", config={"period": 60, "url_list": ["http://c.com"]})
        group = create_group(name="分组", tasks=[task1, task2, task3])

        def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
            if metric == "available":
                if task1.pk in result:
                    result[task1.pk]["available"] = 99.0
                if task2.pk in result:
                    result[task2.pk]["available"] = 82.5
                if task3.pk in result:
                    result[task3.pk]["available"] = 95.0

        mock_third_party.batch_metric.side_effect = fake_query

        result = UptimeCheckGroupTopTasksResource().request(
            {"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk], "top_n": 1}
        )

        assert len(result["data"][group.pk]["top_tasks"]) == 1
        assert result["data"][group.pk]["top_tasks"][0]["task_id"] == task2.pk

    def test_alarm_num_aggregated(self, create_task, create_group, mock_third_party):
        task1 = create_task(name="任务1", config={"period": 60, "url_list": ["http://a.com"]})
        task2 = create_task(name="任务2", config={"period": 60, "url_list": ["http://b.com"]})
        group = create_group(name="分组", tasks=[task1, task2])

        mock_third_party.alarm_info.return_value = {
            task1.pk: {"alarm_num": 2, "available_alarm": True, "task_duration_alarm": False},
            task2.pk: {"alarm_num": 1, "available_alarm": False, "task_duration_alarm": True},
        }

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk]})

        assert result["data"][group.pk]["alarm_num"] == 3

    def test_alarm_query_failure_partial(self, create_task, create_group, mock_third_party):
        task = create_task(config={"period": 60, "url_list": ["http://a.com"]})
        group = create_group(name="分组", tasks=[task])
        mock_third_party.alarm_info.side_effect = Exception("ES down")

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk]})

        assert result["partial"] is True
        assert "alarm_query_failed" in result["errors"]
        assert result["data"][group.pk]["alarm_num"] == 0

    def test_empty_group_returns_empty(self, create_task, create_group, mock_third_party):
        task = create_task(config={"period": 60, "url_list": ["http://a.com"]})
        group = create_group(name="有任务", tasks=[task])

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk, 99999]})

        assert result["data"][99999]["top_tasks"] == []
        assert result["data"][99999]["alarm_num"] == 0

    def test_metric_failure_degrades_to_null(self, create_task, create_group, mock_third_party):
        task = create_task(config={"period": 60, "url_list": ["http://a.com"]})
        group = create_group(name="分组", tasks=[task])
        mock_third_party.batch_metric.side_effect = Exception("influxdb down")

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [group.pk]})

        assert result["data"][group.pk]["top_tasks"][0]["available"] is None

    def test_empty_group_ids_rejected(self):
        with pytest.raises(Exception):
            UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": []})

    def test_top_n_out_of_range_rejected(self):
        with pytest.raises(Exception):
            UptimeCheckGroupTopTasksResource().request({"bk_biz_id": BK_BIZ_ID, "group_ids": [1], "top_n": 11})

    def test_task_biz_isolation(self, create_task, create_group, mock_third_party):
        """分组关联的其他业务任务不应出现在 top_tasks 中"""
        task_biz2 = create_task(name="业务2任务", bk_biz_id=2, config={"period": 60, "url_list": ["http://a.com"]})
        task_biz3 = create_task(name="业务3任务", bk_biz_id=3, config={"period": 60, "url_list": ["http://b.com"]})
        group = create_group(name="分组", bk_biz_id=2, tasks=[task_biz2, task_biz3])

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [group.pk]})

        task_ids = [item["task_id"] for item in result["data"][group.pk]["top_tasks"]]
        assert task_biz2.pk in task_ids
        assert task_biz3.pk not in task_ids
