"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _
from bk_monitor_base.uptime_check import UptimeCheckNode


def get_data():
    return {"bk_biz_id": 2, "carrieroperator": [], "location": [], "task_id": 10080, "time_range": ""}


def get_result():
    return {
        "chart": {
            "available": {
                "chart_type": "spline",
                "duration": 0.427,
                "max_y": 100.0,
                "min_y": None,
                "pointInterval": 300000,
                "series": [
                    {
                        "avg": 98.61,
                        "data": [[1584843000000, None], [1584843300000, 100.0], [1584843600000, 100.0]],
                        "max": 100.0,
                        "max_index": 1,
                        "min": 0.0,
                        "name": _("10.0.1.10 | 0"),
                    }
                ],
                "timezone": "Asia/Shanghai",
                "unit": "%",
                "utcoffset": 28800.0,
                "x_axis": {"minRange": 3600000, "type": "datetime"},
            },
            "task_duration": {
                "chart_type": "spline",
                "duration": 0.417,
                "max_y": 5257,
                "min_y": None,
                "pointInterval": 300000,
                "series": [
                    {
                        "avg": 138.0,
                        "data": [[1584843000000, None], [1584843300000, 39], [1584843600000, 52]],
                        "max": 4272,
                        "max_index": 253,
                        "min": 30,
                        "name": _("10.0.1.10 | 0"),
                    }
                ],
                "timezone": "Asia/Shanghai",
                "unit": "ms",
                "utcoffset": 28800.0,
                "x_axis": {"minRange": 3600000, "type": "datetime"},
            },
        },
        "map": [{"available": 98.61, "location": _("广东"), "name": _("10.0.1.10 | 0"), "task_duration": 138.0}],
        "max_and_min": {
            "available_max": 100.0,
            "available_min": 0.0,
            "task_duration_max": 4272,
            "task_duration_min": 30,
        },
    }  # noqa


def task_detail_func(params):
    if params["type"] == "available":
        return {
            "chart_type": "spline",
            "duration": 0.427,
            "max_y": 100.0,
            "min_y": None,
            "pointInterval": 300000,
            "series": [
                {
                    "avg": 98.61,
                    "data": [[1584843000000, None], [1584843300000, 100.0], [1584843600000, 100.0]],
                    "max": 100.0,
                    "max_index": 1,
                    "min": 0.0,
                    "name": "10.0.1.10 | 0",
                }
            ],
            "timezone": "Asia/Shanghai",
            "unit": "%",
            "utcoffset": 28800.0,
            "x_axis": {"minRange": 3600000, "type": "datetime"},
        }
    if params["type"] == "task_duration":
        return {
            "chart_type": "spline",
            "duration": 0.417,
            "max_y": 5257,
            "min_y": None,
            "pointInterval": 300000,
            "series": [
                {
                    "avg": 138.0,
                    "data": [[1584843000000, None], [1584843300000, 39], [1584843600000, 52]],
                    "max": 4272,
                    "max_index": 253,
                    "min": 30,
                    "name": "10.0.1.10 | 0",
                }
            ],
            "timezone": "Asia/Shanghai",
            "unit": "ms",
            "utcoffset": 28800.0,
            "x_axis": {"minRange": 3600000, "type": "datetime"},
        }


def mock_task_detail(mocker):
    task_detail_resource = mocker.patch("monitor_web.uptime_check.resources.TaskDetailResource.perform_request")
    task_detail_resource.side_effect = task_detail_func
    return task_detail_resource


def mock_get_uptimecheck_node(mocker):
    node = UptimeCheckNode(
        bk_tenant_id="default",
        bk_biz_id=2,
        id=1,
        name=_("10.0.1.10 | 0"),
        location={"city": _("广东"), "country": _("中国")},
        ip="10.0.1.10",
        plat_id=0,
        bk_host_id=1,
        carrieroperator="",
    )
    get_func = mocker.patch("bk_monitor_base.uptime_check.UptimeCheckNodeModel.objects.get")
    get_func.return_value = node
    return get_func


def mock_get_uptimecheck_task(mocker):
    from bk_monitor_base.uptime_check import UptimeCheckTaskModel

    get_func = mocker.patch("bk_monitor_base.uptime_check.UptimeCheckTaskModel.objects.get")
    get_func.return_value = UptimeCheckTaskModel()
    return get_func


# @pytest.mark.django_db
# class TestTaskGraphAndMap(object):
# 测试对给定数据的图像生成是否正常
# def test_perform_request(self, mocker):
#     get_node = mock_get_uptimecheck_node(mocker)
#     get_task = mock_get_uptimecheck_task(mocker)
#     task_detail_resource = mock_task_detail(mocker)
#
#     get_node.start()
#     get_task.start()
#     task_detail_resource.start()
#
#     expected_result = get_result()
#     input_data = get_data()
#     result = resource.uptime_check.task_graph_and_map(input_data)
#     assert result == expected_result
#     assert task_detail_resource.call_count == 2
#     assert get_node.call_count == 2
#     get_task.assert_called_once()
#
#     get_node.stop()
#     get_task.stop()
#     task_detail_resource.stop()
