# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict
from typing import Dict, List

import mock
import pytest
from django.conf import settings
from monitor_web.constants import AGENT_STATUS

from api.cmdb.mock import HOSTS, SERVICE_INSTANCES
from constants.cmdb import TargetNodeType
from core.drf_resource import resource


@pytest.fixture
def mock_unify_query__query_data(mocker, request) -> mock.MagicMock:
    """
    mock unify_query.query_data
    """
    query_data = mocker.patch("bkmonitor.data_source.UnifyQuery.query_data")
    query_data.return_value = request.param
    return query_data


class TestParseTopoTarget:
    """
    测试 resource.cc.parse_topo_target
    根据维度字段，将监控目标解析为主机/服务实例过滤条件
    """

    @mock.patch("core.drf_resource.api.cmdb.get_host_by_id", return_value=HOSTS[0:1])
    @pytest.mark.parametrize(
        "dimensions,target,expected,call_count",
        [
            [["ip"], [[{"value": [{"ip": "127.0.0.1", "bk_cloud_id": 0}]}]], [{"ip": "127.0.0.1"}], 0],
            [
                ["ip", "bk_cloud_id"],
                [{"ip": "127.0.0.1", "bk_cloud_id": 0}],
                [{"ip": "127.0.0.1", "bk_cloud_id": "0"}],
                0,
            ],
            [["bk_target_ip"], [{"ip": "127.0.0.1"}], [{"bk_target_ip": "127.0.0.1"}], 0],
            [
                ["bk_target_ip", "bk_target_cloud_id"],
                [{"ip": "127.0.0.1", "bk_cloud_id": 0}],
                [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}],
                0,
            ],
            [
                ["bk_target_ip", "bk_target_cloud_id"],
                [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0}],
                [{"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"}],
                0,
            ],
            [["ip"], [{"bk_host_id": 1}], [{"ip": HOSTS[0]["bk_host_innerip"]}], 1],
            [["bk_target_ip"], [{"bk_host_id": 1}], [{"bk_target_ip": HOSTS[0]["bk_host_innerip"]}], 1],
            [["bk_host_id"], [{"bk_host_id": 1}], [{"bk_host_id": "1"}], 0],
        ],
    )
    def test_host_target(self, get_host_by_id, dimensions, target, expected, call_count):
        """
        测试主机目标解析
        """
        assert resource.cc.parse_topo_target(2, dimensions, target) == expected
        assert get_host_by_id.call_count == call_count

    @mock.patch("core.drf_resource.api.cmdb.get_host_by_topo_node", return_value=HOSTS)
    @pytest.mark.parametrize(
        "dimensions,target,expected",
        [
            [["ip"], [{"bk_obj_id": "biz", "bk_inst_id": 2}], [{"ip": host.bk_host_innerip} for host in HOSTS]],
            [
                ["bk_target_ip"],
                [{"bk_obj_id": "biz", "bk_inst_id": 2}],
                [{"bk_target_ip": host.bk_host_innerip} for host in HOSTS],
            ],
            [
                ["bk_target_ip", "bk_target_cloud_id"],
                [{"bk_obj_id": "biz", "bk_inst_id": 2}],
                [{"bk_target_ip": host.bk_host_innerip, "bk_target_cloud_id": str(host.bk_cloud_id)} for host in HOSTS],
            ],
            [
                ["bk_host_id"],
                [{"bk_obj_id": "biz", "bk_inst_id": 2}],
                [{"bk_host_id": str(host.bk_host_id)} for host in HOSTS],
            ],
            [
                ["ip"],
                [{"bk_obj_id": "module", "bk_inst_id": 2}, {"bk_obj_id": "set", "bk_inst_id": 3}],
                [{"ip": host.bk_host_innerip} for host in HOSTS],
            ],
        ],
    )
    def test_host_topo_target(self, get_host_by_topo_node, dimensions, target: List[Dict], expected):
        """
        测试主机拓扑目标解析
        """
        self._test_topo(get_host_by_topo_node, dimensions, target, expected)

    @mock.patch("core.drf_resource.api.cmdb.get_host_by_template", return_value=HOSTS)
    @pytest.mark.parametrize(
        "dimensions,target,expected",
        [
            [
                ["ip"],
                [{"bk_obj_id": TargetNodeType.SERVICE_TEMPLATE, "bk_inst_id": 2}],
                [{"ip": host.bk_host_innerip} for host in HOSTS],
            ],
            [
                ["bk_target_ip"],
                [{"bk_obj_id": TargetNodeType.SERVICE_TEMPLATE, "bk_inst_id": 2}],
                [{"bk_target_ip": host.bk_host_innerip} for host in HOSTS],
            ],
            [
                ["bk_target_ip", "bk_target_cloud_id"],
                [{"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 2}],
                [{"bk_target_ip": host.bk_host_innerip, "bk_target_cloud_id": str(host.bk_cloud_id)} for host in HOSTS],
            ],
            [
                ["bk_host_id"],
                [{"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 2}],
                [{"bk_host_id": str(host.bk_host_id)} for host in HOSTS],
            ],
            [
                ["ip"],
                [
                    {"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 2},
                    {"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 3},
                ],
                [{"ip": host.bk_host_innerip} for host in HOSTS],
            ],
        ],
    )
    def test_host_template_target(self, get_host_by_template, dimensions, target: List[Dict], expected):
        """
        测试主机服务模板目标解析
        """
        self._test_template(get_host_by_template, dimensions, target, expected)

    @mock.patch("core.drf_resource.api.cmdb.get_service_instance_by_topo_node", return_value=SERVICE_INSTANCES)
    @pytest.mark.parametrize(
        "dimensions,target,expected",
        [
            [
                ["service_instance_id"],
                [{"bk_obj_id": "biz", "bk_inst_id": 2}],
                [{"service_instance_id": str(service.service_instance_id)} for service in SERVICE_INSTANCES],
            ],
            [
                ["bk_target_service_instance_id"],
                [{"bk_obj_id": "biz", "bk_inst_id": 2}],
                [{"bk_target_service_instance_id": str(service.service_instance_id)} for service in SERVICE_INSTANCES],
            ],
            [
                ["service_instance_id"],
                [{"bk_obj_id": "module", "bk_inst_id": 2}, {"bk_obj_id": "set", "bk_inst_id": 3}],
                [{"service_instance_id": str(service.service_instance_id)} for service in SERVICE_INSTANCES],
            ],
        ],
    )
    def test_service_topo_target(self, get_service_instance_by_topo_node, dimensions, target: List[Dict], expected):
        """
        测试服务拓扑目标解析
        """
        self._test_topo(get_service_instance_by_topo_node, dimensions, target, expected)

    @mock.patch("core.drf_resource.api.cmdb.get_service_instance_by_template", return_value=SERVICE_INSTANCES)
    @pytest.mark.parametrize(
        "dimensions,target,expected",
        [
            [
                ["service_instance_id"],
                [{"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 2}],
                [{"service_instance_id": str(service.service_instance_id)} for service in SERVICE_INSTANCES],
            ],
            [
                ["bk_target_service_instance_id"],
                [{"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 2}],
                [{"bk_target_service_instance_id": str(service.service_instance_id)} for service in SERVICE_INSTANCES],
            ],
        ],
    )
    def test_service_template_target(self, get_service_instance_by_template, dimensions, target: List[Dict], expected):
        """
        测试服务模板目标解析
        """
        self._test_template(get_service_instance_by_template, dimensions, target, expected)

    @staticmethod
    def _test_template(func, dimensions, target: List[Dict], expected):
        template_ids = []
        bk_obj_id = None
        for node in target:
            bk_obj_id = node["bk_obj_id"]
            template_ids.append(node["bk_inst_id"])

        assert resource.cc.parse_topo_target(2, dimensions, target) == expected
        assert func.call_count == 1
        assert func.call_args[1] == {"bk_biz_id": 2, "bk_obj_id": bk_obj_id, "template_ids": template_ids}

    @staticmethod
    def _test_topo(func, dimensions, target: List[Dict], expected):
        topo_nodes = defaultdict(list)
        for node in target:
            topo_nodes[node["bk_obj_id"]].append(node["bk_inst_id"])

        assert resource.cc.parse_topo_target(2, dimensions, target) == expected
        assert func.call_count == 1
        assert func.call_args[1] == {"bk_biz_id": 2, "topo_nodes": topo_nodes}


class TestGetAgentStatus:
    """
    测试获取Agent状态
    """

    @mock.patch(
        "core.drf_resource.api.gse.get_agent_status",
        return_value={
            f"{HOSTS[1].bk_cloud_id}:{HOSTS[0].bk_host_innerip}": {
                "ip": HOSTS[0].bk_host_innerip,
                "bk_cloud_id": HOSTS[0].bk_cloud_id,
                "bk_agent_alive": 1,
            },
            f"{HOSTS[1].bk_cloud_id}:{HOSTS[1].bk_host_innerip}": {
                "ip": HOSTS[1].bk_host_innerip,
                "bk_cloud_id": HOSTS[1].bk_cloud_id,
                "bk_agent_alive": 1,
            },
        },
    )
    @pytest.mark.parametrize(
        "mock_unify_query__query_data",
        [
            [
                {
                    "_result_": 4.8,
                    "bk_target_ip": HOSTS[0].bk_host_innerip,
                    "bk_target_cloud_id": HOSTS[0].bk_cloud_id,
                    "_time_": 1671442260000,
                }
            ],
        ],
        indirect=True,
    )
    def test_old_gse_api(self, get_agent_status, mock_unify_query__query_data):
        """
        测试老版本gse api
        """
        settings.USE_GSE_AGENT_STATUS_NEW_API = False
        assert resource.cc.get_agent_status(2, HOSTS[0:3]) == {
            HOSTS[0].bk_host_id: AGENT_STATUS.ON,
            HOSTS[1].bk_host_id: AGENT_STATUS.NO_DATA,
            HOSTS[2].bk_host_id: AGENT_STATUS.NOT_EXIST,
        }
        assert get_agent_status.call_count == 1

    @mock.patch(
        "core.drf_resource.api.gse.list_agent_state",
        return_value=[
            {
                "bk_agent_id": HOSTS[0].bk_agent_id,
                "bk_cloud_id": 0,
                "version": "2.0.0",
                "run_mode": 1,
                "status_code": 2,
            },
            {
                "bk_agent_id": f"{HOSTS[1].bk_cloud_id}:{HOSTS[1].bk_host_innerip}",
                "bk_cloud_id": 0,
                "version": "2.0.0",
                "run_mode": 1,
                "status_code": 2,
            },
        ],
    )
    @pytest.mark.parametrize(
        "mock_unify_query__query_data",
        [
            [
                {
                    "_result_": 4.8,
                    "bk_target_ip": HOSTS[1].bk_host_innerip,
                    "bk_target_cloud_id": HOSTS[1].bk_cloud_id,
                    "_time_": 1671442260000,
                }
            ],
        ],
        indirect=True,
    )
    def test_new_gse_api(self, list_agent_state, mock_unify_query__query_data):
        """
        测试新版本gse api
        """
        settings.USE_GSE_AGENT_STATUS_NEW_API = True
        assert resource.cc.get_agent_status(2, HOSTS[0:3]) == {
            HOSTS[0].bk_host_id: AGENT_STATUS.NO_DATA,
            HOSTS[1].bk_host_id: AGENT_STATUS.ON,
            HOSTS[2].bk_host_id: AGENT_STATUS.NOT_EXIST,
        }
        assert list_agent_state.call_count == 1
