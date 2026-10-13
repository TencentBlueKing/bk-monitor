# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import json
from collections import UserList
from os import path

import pytest
from django.conf import settings
from mock import Mock

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException  # noqa
from monitor_web.models.uptime_check import UptimeCheckNode
from monitor_web.uptime_check.constants import RESULT_MSG
from monitor_web.uptime_check.resources import TestTaskResource


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
        "r",
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
        "r",
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
@pytest.mark.django_db
class TestTestTask(object):
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


class TestTaskResultMessages:
    @pytest.fixture
    def run_test_task(self, mocker):
        """隔离节点与下发接口，验证真实预检方法对采集结果的处理。"""
        node = mocker.Mock(bk_biz_id=2, bk_host_id=1, ip="", is_common=False)
        node.name = "probe-node"
        nodes = mocker.MagicMock()
        nodes.__iter__.side_effect = lambda: iter([node])
        nodes.filter.return_value.first.return_value = node
        nodes.values_list.return_value.distinct.return_value = [1]
        mocker.patch("monitor_web.uptime_check.resources.UptimeCheckNode.objects.filter", return_value=nodes)
        mocker.patch("monitor_web.uptime_check.resources.api.node_man.plugin_search", return_value={"list": []})
        collector_test = mocker.patch("monitor_web.uptime_check.resources.UptimeCheckCollector.test")

        def run(protocol, result):
            collector_test.return_value = {
                "success": [{"bk_host_id": 1, "ip": "", "log_content": json.dumps(result)}],
                "failed": [],
                "pending": [],
            }
            return TestTaskResource().perform_request(
                {"bk_biz_id": 2, "protocol": protocol, "node_id_list": [1], "config": {}}
            )

        return run

    @pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP"])
    @pytest.mark.parametrize("error_code", [1004, 1100, 1101, 1103, 1200, 1202, 1211, 1213, 1501, 2102, 2501])
    def test_current_collector_error_codes(self, run_test_task, protocol, error_code):
        """当前采集器错误应显示可读提示，同时保持预检失败。"""
        with pytest.raises(CustomException) as exc:
            run_test_task(protocol, {"error_code": error_code, "message": ""})
        assert exc.value.message.startswith("node:probe-node, log:")
        assert RESULT_MSG[str(error_code)] in exc.value.message
        assert "未知错误码" not in exc.value.message
        assert '"error_code"' not in exc.value.message

    @pytest.mark.parametrize("response_code", [200, 400])
    def test_http_response_mismatch(self, run_test_task, response_code):
        """HTTP 内容与状态码校验均可返回 1202，提示应覆盖两者。"""
        with pytest.raises(CustomException) as exc:
            run_test_task("HTTP", {"error_code": 1202, "response_code": response_code})
        assert "状态码或响应内容" in exc.value.message

    @pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP", "ICMP"])
    def test_unknown_error_code(self, run_test_task, protocol):
        """未来错误码保留码值，但不将整段采集器 JSON 作为用户提示。"""
        result = {"error_code": 99999, "message": ""}
        if protocol == "ICMP":
            result = {"dimensions": result}
        with pytest.raises(CustomException) as exc:
            run_test_task(protocol, result)
        assert "采集器返回未知错误码（99999）" in exc.value.message
        assert '"error_code"' not in exc.value.message

    @pytest.mark.parametrize(
        "protocol, expected",
        [("HTTP", "请确认响应内容是否正确（3002）"), ("UDP", "响应内容匹配失败，请确认响应内容是否正确（3002）")],
    )
    def test_legacy_error_code(self, run_test_task, protocol, expected):
        """保留旧采集器错误码及 UDP 专用提示。"""
        with pytest.raises(CustomException) as exc:
            run_test_task(protocol, {"error_code": 3002, "message": ""})
        assert expected in exc.value.message

    @pytest.mark.parametrize("error_code", [1004, 1202, 3002])
    def test_icmp_nested_error_code(self, run_test_task, error_code):
        """ICMP 只在 dimensions 中携带错误信息时也能正确解析。"""
        with pytest.raises(CustomException) as exc:
            run_test_task("ICMP", {"dimensions": {"error_code": str(error_code), "message": "probe failed"}})
        assert RESULT_MSG[str(error_code)] in exc.value.message
        assert "probe failed" in exc.value.message
        assert '"dimensions"' not in exc.value.message

    @pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP", "ICMP"])
    def test_success(self, run_test_task, protocol):
        """成功结果仍允许进入保存流程。"""
        result = {"error_code": 0}
        if protocol == "ICMP":
            result = {"dimensions": result}
        assert run_test_task(protocol, result) == RESULT_MSG["0"]
