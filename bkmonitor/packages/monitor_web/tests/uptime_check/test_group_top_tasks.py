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

from monitor_web.uptime_check.resources import UptimeCheckGroupTopTasksResource


def make_task(task_id: int, group_ids: list[int], status: str = "running") -> UptimeCheckTask:
    return UptimeCheckTask(
        bk_tenant_id="tenant",
        id=task_id,
        bk_biz_id=2,
        name=f"任务{task_id}",
        protocol="HTTP",
        status=status,
        config={"period": 60},
        group_ids=group_ids,
    )


def make_available_filler(available_map: dict[int, float]):
    """构造 _batch_query_task_metric 的 side_effect，按 task_id 填充 available"""

    def fake_query(metric, bk_biz_id, data_label, where, period, end_time, result):
        for task_id, value in available_map.items():
            if task_id in result:
                result[task_id]["available"] = value

    return fake_query


@pytest.fixture
def patch_env(mocker):
    mocker.patch("monitor_web.uptime_check.resources.get_request_tenant_id", return_value="tenant")
    return mocker


@pytest.mark.django_db(databases="__all__")
class TestGroupTopTasks:
    def test_sorted_by_available_null_worst(self, patch_env, mocker):
        mocker.patch(
            "monitor_web.uptime_check.resources.list_tasks",
            return_value=[
                make_task(10, [1]),
                make_task(11, [1]),
                make_task(12, [1]),
                make_task(13, [1]),
            ],
        )
        # 13 无数据(null) 视为最差排最前
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=make_available_filler({10: 99.0, 11: 82.5, 12: 95.0}),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1]})

        assert [item["task_id"] for item in result[1]] == [13, 11, 12]
        assert result[1][0]["available"] is None
        assert result[1][1] == {"task_id": 11, "name": "任务11", "status": "running", "available": 82.5}

    def test_stoped_backfill(self, patch_env, mocker):
        mocker.patch(
            "monitor_web.uptime_check.resources.list_tasks",
            return_value=[
                make_task(10, [1]),
                make_task(11, [1], status="stoped"),
                make_task(12, [1], status="stoped"),
            ],
        )
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=make_available_filler({10: 99.0}),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1]})

        # 非停用优先，不足 top_n 用停用任务补齐
        assert [item["task_id"] for item in result[1]] == [10, 11, 12]
        assert result[1][1]["status"] == "stoped"

    def test_top_n_param(self, patch_env, mocker):
        mocker.patch(
            "monitor_web.uptime_check.resources.list_tasks",
            return_value=[make_task(10, [1]), make_task(11, [1]), make_task(12, [1])],
        )
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=make_available_filler({10: 99.0, 11: 82.5, 12: 95.0}),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1], "top_n": 1})

        assert [item["task_id"] for item in result[1]] == [11]

    def test_task_in_multiple_groups(self, patch_env, mocker):
        mocker.patch(
            "monitor_web.uptime_check.resources.list_tasks",
            return_value=[make_task(10, [1, 2]), make_task(11, [2])],
        )
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=make_available_filler({10: 90.0, 11: 80.0}),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1, 2]})

        assert [item["task_id"] for item in result[1]] == [10]
        assert [item["task_id"] for item in result[2]] == [11, 10]

    def test_empty_group_returns_empty_list(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10, [1])])
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=make_available_filler({10: 90.0}),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1, 999]})

        assert result[999] == []

    def test_metric_failure_degrades_to_null(self, patch_env, mocker):
        mocker.patch("monitor_web.uptime_check.resources.list_tasks", return_value=[make_task(10, [1])])
        mocker.patch(
            "monitor_web.uptime_check.resources._batch_query_task_metric",
            side_effect=Exception("influxdb down"),
        )

        result = UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1]})

        assert result[1][0]["available"] is None

    def test_empty_group_ids_rejected(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": []})

    def test_top_n_out_of_range_rejected(self, patch_env):
        with pytest.raises(Exception):
            UptimeCheckGroupTopTasksResource().request({"bk_biz_id": 2, "group_ids": [1], "top_n": 11})
