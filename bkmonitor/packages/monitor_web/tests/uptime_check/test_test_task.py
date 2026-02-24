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

from bk_monitor_base.uptime_check import UptimeCheckNode
from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException  # noqa
from monitor_web.uptime_check.constants import RESULT_MSG


def get_uptime_check_task_params_test():
    return {
        "bk_biz_id": 2,
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


def mock_list_nodes(mocker, is_common=False):
    """Mock uptime_check_operation.list_uptime_check_nodes"""
    node = UptimeCheckNode(
        id=10002,
        bk_tenant_id="default",
        bk_biz_id=2,
        plat_id=0,
        is_common=is_common,
        update_user="admin",
        bk_host_id=1,
        name="test_node",
        location={},
        carrieroperator="telecom",
    )
    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.list_uptime_check_nodes",
        return_value=[node],
    )


def mock_test_task_success(mocker):
    """Mock uptime_check_operation.test_uptime_check_task 成功场景"""
    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.test_uptime_check_task",
        return_value=RESULT_MSG["0"],
    )


def mock_test_task_job_fail(mocker):
    """Mock uptime_check_operation.test_uptime_check_task JOB 执行失败场景"""
    from bk_monitor_base.uptime_check import TestTaskError

    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.test_uptime_check_task",
        side_effect=TestTaskError("JOB执行失败"),
    )


def mock_test_task_collect_fail(mocker):
    """Mock uptime_check_operation.test_uptime_check_task 采集失败场景"""
    from bk_monitor_base.uptime_check import TestTaskError

    return mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.test_uptime_check_task",
        side_effect=TestTaskError("采集失败"),
    )


# test_task接口主要负责处理
@pytest.mark.django_db(databases="__all__")
class TestTestTask:
    # 测试基本流程的执行情况
    def test_perform_request(self, mocker):
        list_nodes_mock = mock_list_nodes(mocker, is_common=False)
        test_mock = mock_test_task_success(mocker)
        params = get_uptime_check_task_params_test()
        result = resource.uptime_check.test_task(params)
        assert result == RESULT_MSG["0"]
        list_nodes_mock.assert_called_once()
        test_mock.assert_called_once()

    # 测试基本流程的执行情况,使用公共节点
    def test_perform_request_common(self, mocker):
        list_nodes_mock = mock_list_nodes(mocker, is_common=True)
        test_mock = mock_test_task_success(mocker)
        # mock 权限检查
        mocker.patch(
            "monitor_web.uptime_check.resources.Permission.is_allowed",
            return_value=True,
        )
        params = get_uptime_check_task_params_test()
        result = resource.uptime_check.test_task(params)
        assert result == RESULT_MSG["0"]
        list_nodes_mock.assert_called_once()
        test_mock.assert_called_once()

    # 测试任务返回了执行失败的情况下的场景
    def test_job_fail(self, mocker):
        list_nodes_mock = mock_list_nodes(mocker, is_common=False)
        test_mock = mock_test_task_job_fail(mocker)
        params = get_uptime_check_task_params_test()
        with pytest.raises(CustomException):
            resource.uptime_check.test_task(params)
        list_nodes_mock.assert_called_once()
        test_mock.assert_called_once()

    # 测试任务返回了error_code情况下的结果
    def test_collect_fail(self, mocker):
        list_nodes_mock = mock_list_nodes(mocker, is_common=False)
        test_mock = mock_test_task_collect_fail(mocker)
        params = get_uptime_check_task_params_test()
        with pytest.raises(CustomException):
            resource.uptime_check.test_task(params)
        list_nodes_mock.assert_called_once()
        test_mock.assert_called_once()
