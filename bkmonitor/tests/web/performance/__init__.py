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

import copy


# 用于mock get_request()的return_value
class Request(object):
    def __init__(self, username, biz_id):
        class User(object):
            def __init__(self):
                self.username = username

        self.user = User()
        self.biz_id = biz_id


def mock_request(mocker, username, biz_id):
    mocker.patch("monitor.performance.resources.get_request", return_value=Request(username, biz_id))


def mock_cache(mocker):
    mocker.patch("utils.cache.UsingCache.get_value", return_value=None)

    mocker.patch("utils.cache.UsingCache.set_value")


def mock_cc(mocker):
    search_business_return_value = {
        "message": "success",
        "code": 0,
        "data": {
            "count": 2,
            "info": [{"bk_biz_id": 2, "default": 0, "bk_biz_name": "\\u84dd\\u9cb8", "bk_supplier_id": 0}],
        },
        "result": True,
    }
    search_host_return_value = {
        "message": "success",
        "code": 0,
        "data": {
            "count": 5,
            "info": [
                {
                    "host": {
                        "bk_isp_name": None,
                        "bk_state_name": None,
                        "bk_cpu": 4,
                        "bk_host_id": 1,
                        "bk_os_name": "linux centos",
                        "bk_province_name": None,
                        "bk_host_name": "gse-1",
                        "bk_host_innerip": "10.1.1.1",
                        "bk_os_type": "1",
                        "bk_host_outerip": "",
                        "bk_mac": "52:54:00:19:df:a3",
                        "bk_outer_mac": "",
                        "bk_cloud_id": [
                            {
                                "bk_obj_name": "",
                                "id": "0",
                                "bk_obj_id": "plat",
                                "bk_obj_icon": "",
                                "bk_inst_id": 0,
                                "bk_inst_name": "default area",
                            }
                        ],
                    },
                    "set": [],
                    "biz": [],
                    "module": [
                        {
                            "bk_module_id": 31,
                        },
                        {
                            "bk_module_id": 34,
                        },
                    ],
                },
                {
                    "host": {
                        "bk_isp_name": None,
                        "bk_state_name": None,
                        "bk_cpu": 4,
                        "bk_host_id": 2,
                        "bk_os_name": "linux centos",
                        "bk_province_name": None,
                        "bk_host_name": "nginx-1",
                        "bk_host_innerip": "10.1.1.1",
                        "bk_os_type": "1",
                        "bk_host_outerip": "",
                        "bk_mac": "52:54:00:25:62:03",
                        "bk_outer_mac": "",
                        "bk_cloud_id": [
                            {
                                "bk_obj_name": "",
                                "id": "0",
                                "bk_obj_id": "plat",
                                "bk_obj_icon": "",
                                "bk_inst_id": 0,
                                "bk_inst_name": "default area",
                            }
                        ],
                    },
                    "set": [],
                    "biz": [],
                    "module": [
                        {
                            "bk_module_id": 47,
                        }
                    ],
                },
            ],
        },
        "result": True,
        "request_id": "d0fa0c5362f84427996dcd23aa801eec",
    }
    side_effect_list = []
    for i in range(20):
        side_effect_list.append(copy.deepcopy(search_host_return_value))
    search_biz_inst_topo = {
        "message": "success",
        "code": 0,
        "data": [
            {
                "default": 0,
                "bk_obj_name": "business",
                "bk_obj_id": "biz",
                "child": [
                    {
                        "default": 0,
                        "bk_obj_name": "set",
                        "bk_obj_id": "set",
                        "child": [
                            {
                                "default": 0,
                                "bk_obj_name": "module",
                                "bk_obj_id": "module",
                                "child": [],
                                "bk_inst_id": 31,
                                "bk_inst_name": "dataapi",
                            }
                        ],
                        "bk_inst_id": 7,
                        "bk_inst_name": "数据服务模块",
                    },
                    {
                        "default": 0,
                        "bk_obj_name": "set",
                        "bk_obj_id": "set",
                        "child": [
                            {
                                "default": 0,
                                "bk_obj_name": "module",
                                "bk_obj_id": "module",
                                "child": [],
                                "bk_inst_id": 34,
                                "bk_inst_name": "kafka",
                            }
                        ],
                        "bk_inst_id": 8,
                        "bk_inst_name": "公共组件",
                    },
                    {
                        "default": 0,
                        "bk_obj_name": "set",
                        "bk_obj_id": "set",
                        "child": [
                            {
                                "default": 0,
                                "bk_obj_name": "module",
                                "bk_obj_id": "module",
                                "child": [],
                                "bk_inst_id": 47,
                                "bk_inst_name": "paas",
                            }
                        ],
                        "bk_inst_id": 9,
                        "bk_inst_name": "集成平台",
                    },
                ],
                "bk_inst_id": 2,
                "bk_inst_name": "蓝鲸",
            }
        ],
        "result": True,
        "request_id": "218c7730949643a794db0fa598aa5217",
    }
    get_biz_internal_module = {
        "message": "success",
        "code": 0,
        "data": {
            "bk_set_id": 2,
            "module": [
                {"bk_module_name": "idle machine", "bk_module_id": 3},
                {"bk_module_name": "fault machine", "bk_module_id": 4},
            ],
            "bk_set_name": "idle pool",
        },
        "result": True,
        "request_id": "eb2e9a6f9d7a4fc4aa79778883388ead",
    }
    get_agent_status = {
        "message": "",
        "code": 0,
        "data": [{"status": 1, "ip": "10.1.1.1", "plat_id": 0}, {"status": 1, "ip": "10.1.1.1", "plat_id": 0}],
        "result": True,
        "request_id": "341186e04abd4425b3579fdde6ef437a",
    }
    get_process_port_by_app_id = {
        "message": "",
        "code": 0,
        "data": [
            {
                "ApplicationName": "\u84dd\u9cb8",
                "HostID": "1",
                "Process": [
                    {
                        "ProcessID": "56",
                        "WorkPath": "/data/bkee",
                        "Protocol": "TCP",
                        "BindIP": "",
                        "FuncName": "consul",
                        "ProcessName": "consul-agent",
                        "Owner": "0",
                        "ApplicationID": "2",
                        "Port": "8301,8500,53",
                    },
                    {
                        "ProcessID": "51",
                        "WorkPath": "/data/bkee",
                        "Protocol": "TCP",
                        "BindIP": "",
                        "FuncName": "nginx",
                        "ProcessName": "nginx-paas-http",
                        "Owner": "0",
                        "ApplicationID": "2",
                        "Port": "80",
                    },
                ],
                "OuterIP": "",
                "InnerIP": "10.1.1.1",
                "Source": "0",
                "ApplicationID": "2",
            },
            {
                "ApplicationName": "\u84dd\u9cb8",
                "HostID": "2",
                "Process": [
                    {
                        "ProcessID": "56",
                        "WorkPath": "/data/bkee",
                        "Protocol": "TCP",
                        "BindIP": "",
                        "FuncName": "consul",
                        "ProcessName": "consul-agent",
                        "Owner": "0",
                        "ApplicationID": "2",
                        "Port": "8301,8500,53",
                    },
                    {
                        "ProcessID": "29",
                        "WorkPath": "/data/bkee",
                        "AutoTimeGap": "",
                        "ProNum": "",
                        "LastTime": "",
                        "StartCmd": "",
                        "FuncID": "",
                        "Description": "",
                        "ApplicationID": "2",
                        "FuncName": "license_server",
                        "User": "",
                        "StopCmd": "",
                        "ReloadCmd": "",
                        "ProcessName": "license_server",
                        "OpTimeout": "",
                        "KillCmd": "",
                        "Protocol": "TCP",
                        "Seq": "",
                        "Port": "8443",
                        "ReStartCmd": "",
                        "AutoStart": "false",
                        "Owner": "0",
                        "BindIP": "",
                        "CreateTime": "",
                        "PidFile": "",
                    },
                ],
                "OuterIP": "",
                "InnerIP": "10.1.1.1",
                "Source": "0",
                "ApplicationID": "2",
            },
        ],
        "result": True,
    }
    get_data_value = [
        {
            "ip": "10.1.1.1",
            "proc_exists": 1,
            "display_name": "consul-agent",
            "bk_cloud_id": "0",
            "time": 1555991575000,
        },
        {
            "ip": "10.0.1.84",
            "proc_exists": 1,
            "display_name": "nginx-paas-http",
            "bk_cloud_id": "0",
            "time": 1555991635000,
        },
        {
            "ip": "10.0.1.29",
            "proc_exists": 1,
            "display_name": "license_server",
            "bk_cloud_id": "0",
            "time": 1555991695000,
        },
        {
            "ip": "10.0.1.29",
            "proc_exists": 1,
            "display_name": "cmdb_adminserver",
            "bk_cloud_id": "0",
            "time": 1555991755000,
        },
        {
            "ip": "10.0.1.29",
            "proc_exists": 1,
            "display_name": "cmdb_adminserver1",
            "bk_cloud_id": "0",
            "time": 1555991815000,
        },
        {
            "ip": "10.0.1.29",
            "proc_exists": 1,
            "display_name": "cmdb_apiserver2",
            "bk_cloud_id": "0",
            "time": 1555991575000,
        },
    ]
    mock_client = mocker.patch("bkmonitor.utils.sdk_client.client")
    mocker.patch("utils.query_data.TSDBData.get_data", return_value=get_data_value)
    mock_client.cc.search_business.return_value = search_business_return_value
    mock_client.cc.search_host.side_effect = side_effect_list
    mock_client.cc.search_biz_inst_topo.return_value = search_biz_inst_topo
    mock_client.cc.get_biz_internal_module.return_value = get_biz_internal_module
    mock_client.job.get_agent_status.return_value = get_agent_status
    mock_client.cc.get_process_port_by_app_id.return_value = get_process_port_by_app_id
