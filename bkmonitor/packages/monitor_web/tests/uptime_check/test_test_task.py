"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import UserList
from os import path
from unittest.mock import Mock

import pytest
from django.conf import settings

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException  # noqa
from monitor_web.models.uptime_check import UptimeCheckNode
from monitor_web.uptime_check.constants import RESULT_MSG


class FilterList(UserList):
    def filter(self, *args, **kwargs):
        return Mock(return_value=self)


def get_uptime_check_task_params_test():
    return {
        "protocol": "HTTP",
        "node_id_list": [10002],
        "config": {
            "timeout": 3000,
            "period": 60,
            "response": "304",
            "response_format": "nin",
            "method": "GET",
            "urls": "http://www.baidu.com",
            "request": None,
            "headers": [{"name": "Accept-Language", "value": "sdsa"}],
            "response_code": "200",
            "insecure_skip_verify": True,
        },
    }


def mock_node_model(mocker):
    node = UptimeCheckNode(bk_biz_id=2, ip="10.0.1.10", plat_id=0, is_common=False, update_user="admin", bk_host_id=1)
    all_nodes = FilterList()
    all_nodes.append(node)
    filter_func = mocker.patch("monitor_web.models.uptime_check.UptimeCheckNode.objects.filter", return_value=all_nodes)
    return filter_func


def mock_node_model_common(mocker):
    node = UptimeCheckNode(bk_biz_id=2, ip="10.0.1.10", plat_id=0, is_common=True, update_user="admin", bk_host_id=1)
    all_nodes = FilterList()
    all_nodes.append(node)
    filter_func = mocker.patch("monitor_web.models.uptime_check.UptimeCheckNode.objects.filter", return_value=all_nodes)
    return filter_func


def mock_uptimecheck_collector_test(mocker):
    f = open(
        path.join(
            settings.BASE_DIR, "packages", "monitor_web", "tests", "uptime_check", "test_file", "success_content"
        ),
        encoding="utf-8",
    )
    content = f.read()
    success_result = {"bk_cloud_id": 0, "ip": "10.0.1.10", "log_content": content, "plat_id": 0, "bk_host_id": 1}
    result = {
        "failed": [],
        "pending": [],
        "success": [success_result],
    }
    test = mocker.patch("monitor_web.uptime_check.collector.collector.UptimeCheckCollector.test", return_value=result)
    return test


def mock_uptimecheck_collector_test_job_fail(mocker):
    success_result = {
        "bk_cloud_id": 0,
        "ip": "10.0.1.10",
        "log_content": "",
        "plat_id": 0,
        "errmsg": "failed",
        "bk_host_id": 1,
    }
    result = {
        "failed": [success_result],
        "pending": [],
        "success": [],
    }
    test = mocker.patch("monitor_web.uptime_check.collector.collector.UptimeCheckCollector.test", return_value=result)
    return test


def mock_uptimecheck_collector_test_collect_fail(mocker):
    f = open(
        path.join(
            settings.BASE_DIR, "packages", "monitor_web", "tests", "uptime_check", "test_file", "collect_fail_content"
        ),
        encoding="utf-8",
    )
    content = f.read()
    success_result = {"bk_cloud_id": 0, "ip": "10.0.1.10", "log_content": content, "plat_id": 0, "bk_host_id": 1}
    result = {
        "failed": [],
        "pending": [],
        "success": [success_result],
    }
    test = mocker.patch("monitor_web.uptime_check.collector.collector.UptimeCheckCollector.test", return_value=result)
    return test


# test_task接口主要负责处理
@pytest.mark.django_db(databases="__all__")
class TestTestTask:
    # 测试基本流程的执行情况
    def test_perform_request(self, mocker):
        filter_func = mock_node_model(mocker)
        test_func = mock_uptimecheck_collector_test(mocker)
        filter_func.start()
        test_func.start()
        params = get_uptime_check_task_params_test()
        result = resource.uptime_check.test_task(params)
        assert result == result == RESULT_MSG["0"]
        filter_func.assert_called_once()
        test_func.assert_called_once()
        filter_func.stop()
        test_func.stop()

    # 测试基本流程的执行情况,使用公共节点
    def test_perform_request_common(self, mocker):
        filter_func = mock_node_model_common(mocker)
        test_func = mock_uptimecheck_collector_test(mocker)
        filter_func.start()
        test_func.start()
        params = get_uptime_check_task_params_test()
        result = resource.uptime_check.test_task(params)
        assert result == RESULT_MSG["0"]
        filter_func.assert_called_once()
        test_func.assert_called_once()
        filter_func.stop()
        test_func.stop()

    # 测试任务返回了执行失败的情况下的场景
    def test_job_fail(self, mocker):
        filter_func = mock_node_model(mocker)
        test_func = mock_uptimecheck_collector_test_job_fail(mocker)
        filter_func.start()
        test_func.start()
        params = get_uptime_check_task_params_test()
        with pytest.raises(CustomException):
            resource.uptime_check.test_task(params)
        filter_func.assert_called_once()
        test_func.assert_called_once()
        filter_func.stop()
        test_func.stop()

    # 测试任务返回了error_code情况下的结果
    def test_collect_fail(self, mocker):
        filter_func = mock_node_model(mocker)
        test_func = mock_uptimecheck_collector_test_collect_fail(mocker)
        filter_func.start()
        test_func.start()
        params = get_uptime_check_task_params_test()
        with pytest.raises(CustomException):
            resource.uptime_check.test_task(params)
        filter_func.assert_called_once()
        test_func.assert_called_once()
        filter_func.stop()
        test_func.stop()
