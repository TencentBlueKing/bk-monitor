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
from core.drf_resource import resource


def get_mock_uptime_check_task_params_test():
    return {
        "bk_biz_id": 2,
        "protocol": "HTTP",
        "test": True,
        "node_id_list": [10002],
        "config": {
            "timeout": 3000,
            "period": 60,
            "response": "304",
            "response_format": "nin",
            "method": "GET",
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "urls": "http://www.baidu.com",
            "body": {"data_type": "raw", "params": [], "content": '{\n"a": 1\n}', "content_type": "json"},
            "query_params": [{"key": "flag", "value": "1", "desc": "", "is_builtin": False, "is_enabled": True}],
            "headers": [
                {"key": "Accept-Language", "value": "sdsa", "desc": "", "is_builtin": False, "is_enabled": True}
            ],
            "response_code": "200",
        },
    }


def get_mock_uptime_check_task_result_test():
    return [
        {
            "available_duration": "3000ms",
            "bk_biz_id": 0,
            "disable_keep_alives": False,
            "insecure_skip_verify": False,
            "period": "60s",
            "proxy": "",
            "steps": [
                {
                    "available_duration": "3000ms",
                    "headers": {"Accept-Language": "sdsa", "Content-Type": "application/json"},
                    "method": "GET",
                    "request": "'{\n\"a\": 1\n}'",
                    "response": "'304'",
                    "response_code": "200",
                    "response_format": "nin",
                    "url": "http://www.baidu.com?flag=1",
                }
            ],
            "task_id": 0,
            "timeout": "15000ms",
        }
    ]


def get_mock_uptime_check_task_result_deploy():
    return [
        {
            "available_duration": "3000ms",
            "bk_biz_id": 2,
            "disable_keep_alives": False,
            "insecure_skip_verify": False,
            "period": "60s",
            "proxy": "",
            "steps": [
                {
                    "available_duration": "3000ms",
                    "headers": {"Cache-Control": "vvvv", "Cookie": "rere"},
                    "method": "GET",
                    "request": "",
                    "response": "'304'",
                    "response_code": "200",
                    "response_format": "nin",
                    "url": "http://mail.qq.com",
                }
            ],
            "task_id": 10065,
            "timeout": "15000ms",
        }
    ]


def mock_uptime_check_task_model(mocker):
    """Mock uptime_check_operation.get_uptime_check_task"""
    from bk_monitor_base.uptime_check import UptimeCheckTask

    task = UptimeCheckTask(
        bk_tenant_id="default",
        bk_biz_id=2,
        id=10065,
        name="test_task",
        protocol="HTTP",
        config={
            "headers": [
                {"key": "Cookie", "value": "rere", "desc": "", "is_builtin": False, "is_enabled": True},
                {"key": "Cache-Control", "value": "vvvv", "desc": "", "is_builtin": False, "is_enabled": True},
            ],
            "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": True},
            "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
            "query_params": [],
            "method": "GET",
            "period": 60,
            "response": "304",
            "response_code": "200",
            "response_format": "nin",
            "timeout": 3000,
            "urls": "http://mail.qq.com",
        },
        node_ids=[],
        group_ids=[],
        status="running",
    )
    mocked_func = mocker.patch(
        "monitor_web.uptime_check.resources.uptime_check_operation.get_uptime_check_task",
        return_value=task,
    )
    return mocked_func


@pytest.mark.django_db(databases="__all__")
class TestGenerateSubConfig:
    def test_perform_request_test(self, mocker):
        """测试模式下生成子配置"""
        params = get_mock_uptime_check_task_params_test()
        result = resource.uptime_check.generate_sub_config(params)
        result_expect = get_mock_uptime_check_task_result_test()
        assert result == result_expect

    def test_perform_request_deploy(self, mocker):
        """部署模式下生成子配置"""
        mocked_func = mock_uptime_check_task_model(mocker)
        params = {
            "bk_biz_id": 2,
            "task_id": 10065,
        }
        result = resource.uptime_check.generate_sub_config(params)
        result_expect = get_mock_uptime_check_task_result_deploy()
        assert result == result_expect
        mocked_func.assert_called_once()
