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
from collections import defaultdict

from .define import Business, Host, Module, ServiceInstance, Set, TopoTree

"""
这些数据模拟了api.cmdb接口返回的数据结构，用于上层逻辑的测试
"""

# Mock data for Business
BUSINESS = Business(
    **{
        "bk_biz_id": 2,
        "bk_biz_name": "蓝鲸",
        "bk_biz_developer": [],
        "bk_biz_maintainer": ["admin"],
        "bk_biz_tester": [],
        "bk_biz_productor": [],
        "operator": [],
        "time_zone": "Asia/Shanghai",
        "language": "1",
        "life_cycle": "2",
        "bk_supplier_account": "0",
        "create_time": "2022-05-15T19:37:51.109+08:00",
        "default": 0,
        "last_time": "2022-05-15T19:37:51.109+08:00",
    }
)

SPACE_BUSINESS = Business(
    **{
        "id": 1,
        "space_type_id": "bkci",
        "space_id": "1",
        "space_name": "1",
        "status": "normal",
        "space_code": "",
        "space_uid": "bkci__1",
        "type_name": "研发项目",
        "bk_biz_id": -1,
        "bk_biz_developer": [],
        "bk_biz_maintainer": ["admin"],
        "bk_biz_tester": [],
        "bk_biz_productor": [],
        "operator": [],
        "extend": {
            "time_zone": "Asia/Shanghai",
            "language": "zh-hans",
            "is_bcs_valid": False,
            "type_id": "bkci",
            "allow_merge": True,
            "allow_bind": True,
            "dimension_fields": "[\"project_code\"]",
        },
    }
)

BUSINESSES = [BUSINESS, SPACE_BUSINESS]


# Mock data for Module
MODULES = [
    Module(
        **{
            "bk_module_id": 1,
            "bk_module_name": "module1",
            "service_template_id": 0,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 1,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 1,
            "default": 1,
        }
    ),
    Module(
        **{
            "bk_module_id": 2,
            "bk_module_name": "module2",
            "service_template_id": 1,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 2,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 2,
            "default": 1,
        }
    ),
    Module(
        **{
            "bk_module_id": 3,
            "bk_module_name": "module3",
            "service_template_id": 1,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 2,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 2,
            "default": 1,
        }
    ),
    Module(
        **{
            "bk_module_id": 4,
            "bk_module_name": "故障机",
            "service_template_id": 0,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 4,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 4,
            "default": 1,
        }
    ),
    Module(
        **{
            "bk_module_id": 5,
            "bk_module_name": "空闲机",
            "service_template_id": 0,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 4,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 4,
            "default": 1,
        }
    ),
    Module(
        **{
            "bk_module_id": 6,
            "bk_module_name": "待回收",
            "service_template_id": 0,
            "service_category_id": 1,
            "operator": "admin",
            "bk_bak_operator": "",
            "bk_supplier_account": "0",
            "set_template_id": 0,
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_set_id": 4,
            "bk_module_type": "1",
            "host_apply_enabled": False,
            "bk_parent_id": 4,
            "default": 1,
        }
    ),
]

# Mock data for Set
SETS = [
    Set(
        **{
            "bk_set_id": 1,
            "bk_set_name": "set1",
            "bk_parent_id": 2,
            "bk_supplier_account": "0",
            "bk_service_status": "1",
            "bk_set_env": "1",
            "bk_set_desc": "",
            "set_template_id": 0,
            "bk_biz_id": 2,
            "description": "",
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_capacity": None,
            "default": 1,
        }
    ),
    Set(
        **{
            "bk_set_id": 2,
            "bk_set_name": "set2",
            "bk_parent_id": 2,
            "bk_supplier_account": "0",
            "bk_service_status": "1",
            "bk_set_env": "1",
            "bk_set_desc": "",
            "set_template_id": 1,
            "bk_biz_id": 2,
            "description": "",
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_capacity": None,
            "default": 1,
        }
    ),
    Set(
        **{
            "bk_set_id": 3,
            "bk_set_name": "set3",
            "bk_parent_id": 2,
            "bk_supplier_account": "0",
            "bk_service_status": "1",
            "bk_set_env": "1",
            "bk_set_desc": "",
            "set_template_id": 1,
            "bk_biz_id": 2,
            "description": "",
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_capacity": None,
            "default": 1,
        }
    ),
    Set(
        **{
            "bk_set_id": 4,
            "bk_set_name": "空闲机池",
            "bk_parent_id": 2,
            "bk_supplier_account": "0",
            "bk_service_status": "1",
            "bk_set_env": "1",
            "bk_set_desc": "",
            "set_template_id": 0,
            "bk_biz_id": 2,
            "description": "",
            "create_time": "2022-05-15T19:37:51.109+08:00",
            "last_time": "2022-05-15T19:37:51.109+08:00",
            "bk_capacity": None,
            "default": 1,
        }
    ),
]

# Mock data for TopoTree
_module_set_dict = defaultdict(list)
for module in MODULES:
    _module_set_dict[module.bk_set_id].append(module)
TOPO_TREE = TopoTree(
    {
        "bk_inst_id": BUSINESS.bk_biz_id,
        "bk_inst_name": BUSINESS.bk_biz_name,
        "bk_obj_id": "biz",
        "bk_obj_name": "business",
        "child": [
            {
                "bk_inst_id": s.bk_inst_id,
                "bk_inst_name": s.bk_inst_name,
                "bk_obj_id": "set",
                "bk_obj_name": "set",
                "child": [
                    {
                        "bk_inst_id": m.bk_inst_id,
                        "bk_inst_name": m.bk_inst_name,
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                    }
                    for m in _module_set_dict[s.bk_inst_id]
                ],
            }
            for s in SETS
        ],
    }
)

# Mock data for SetTemplate
SET_TEMPLATES = [
    {"id": 1, "name": "set_template1"},
    {"id": 2, "name": "set_template2"},
]

# Mock data for ServiceTemplate
SERVICE_TEMPLATES = [
    {"id": 1, "name": "service_template1"},
    {"id": 2, "name": "service_template2"},
]

# Mock data for CloudArea
CLOUD_AREAS = [
    {
        "bk_vpc_name": "",
        "bk_status_detail": "",
        "bk_account_id": None,
        "bk_status": "1",
        "bk_cloud_name": "default area",
        "bk_supplier_account": "0",
        "bk_creator": "admin",
        "create_time": "2022-10-11T11:04:01.908+08:00",
        "bk_cloud_id": 0,
        "bk_last_editor": "admin",
        "bk_cloud_vendor": None,
        "last_time": "2022-10-14T17:52:20.8+08:00",
        "bk_region": "",
        "bk_vpc_id": "",
    },
    {
        "bk_vpc_name": "",
        "bk_status_detail": "",
        "bk_account_id": None,
        "bk_status": "1",
        "bk_cloud_name": "area1",
        "bk_supplier_account": "0",
        "bk_creator": "admin",
        "create_time": "2022-10-11T11:04:01.908+08:00",
        "bk_cloud_id": 1,
        "bk_last_editor": "admin",
        "bk_cloud_vendor": None,
        "last_time": "2022-10-14T17:52:20.8+08:00",
        "bk_region": "",
        "bk_vpc_id": "",
    },
]

# Mock data for Host
HOSTS = [
    Host(
        **{
            "bk_biz_id": 2,
            "bk_cloud_id": 0,
            "bk_cloud_name": "default area",
            "bk_host_id": 1,
            "ip": "192.168.0.1",
            "bk_host_innerip": "192.168.0.1",
            "bk_host_innerip_v6": "",
            "bk_host_outerip": "",
            "bk_host_outerip_v6": "",
            "bk_host_name": "VM-0-1-centos",
            "bk_isp_name": None,
            "bk_os_name": "linux centos",
            "bk_os_type": "1",
            "bk_os_version": "7.9",
            "bk_province_name": None,
            "bk_state": "",
            "bk_state_name": None,
            "bk_supplier_account": "0",
            "operator": ["admin"],
            "bk_bak_operator": ["admin"],
            "bk_set_ids": [1],
            "bk_module_ids": [1],
            "bk_comment": "",
            "bk_agent_id": "01000000000000000000000000000000",
        }
    ),
    Host(
        **{
            "bk_biz_id": 2,
            "bk_cloud_id": 1,
            "bk_cloud_name": "default area",
            "bk_host_id": 2,
            "ip": "192.168.0.2",
            "bk_host_innerip": "192.168.0.2",
            "bk_host_innerip_v6": "",
            "bk_host_outerip": "",
            "bk_host_outerip_v6": "",
            "bk_host_name": "VM-0-2-centos",
            "bk_isp_name": None,
            "bk_os_name": "linux centos",
            "bk_os_type": "1",
            "bk_os_version": "7.9",
            "bk_province_name": None,
            "bk_state": "",
            "bk_state_name": None,
            "bk_supplier_account": "0",
            "operator": ["admin"],
            "bk_bak_operator": ["admin"],
            "bk_set_ids": [2],
            "bk_module_ids": [2, 3],
            "bk_comment": "",
            "bk_agent_id": "",
        }
    ),
    # host have ipv6
    Host(
        **{
            "bk_biz_id": 2,
            "bk_cloud_id": 1,
            "bk_cloud_name": "default area",
            "bk_host_id": 3,
            "ip": "",
            "bk_host_innerip": "",
            "bk_host_innerip_v6": "fe80::2aa:ff:fe28:9c5a",
            "bk_host_outerip": "",
            "bk_host_outerip_v6": "",
            "bk_host_name": "VM-0-3-centos",
            "bk_isp_name": None,
            "bk_os_name": "linux centos",
            "bk_os_type": "1",
            "bk_os_version": "7.9",
            "bk_province_name": None,
            "bk_state": "",
            "bk_state_name": None,
            "bk_supplier_account": "0",
            "operator": ["admin"],
            "bk_bak_operator": ["admin"],
            "bk_set_ids": [2],
            "bk_module_ids": [2],
            "bk_comment": "",
            "bk_agent_id": "01000000000000000000000000000002",
        }
    ),
    # host have ipv4 and ipv6
    Host(
        **{
            "bk_biz_id": 2,
            "bk_cloud_id": 0,
            "bk_cloud_name": "default area",
            "bk_host_id": 4,
            "ip": "192.168.0.3",
            "bk_host_innerip": "192.168.0.3",
            "bk_host_innerip_v6": "fe80::2aa:ff:fe28:9c5a",
            "bk_host_outerip": "",
            "bk_host_outerip_v6": "",
            "bk_host_name": "VM-0-4-centos",
            "bk_isp_name": None,
            "bk_os_name": "linux centos",
            "bk_os_type": "1",
            "bk_os_version": "7.9",
            "bk_province_name": None,
            "bk_state": "",
            "bk_state_name": None,
            "bk_supplier_account": "0",
            "operator": ["admin"],
            "bk_bak_operator": ["admin"],
            "bk_set_ids": [2],
            "bk_module_ids": [3],
            "bk_comment": "",
            "bk_agent_id": "",
        }
    ),
]

# Mock data for ServiceInstance
SERVICE_INSTANCES = [
    ServiceInstance(
        **{
            "service_instance_id": 1,
            "bk_host_id": 1,
            "bk_module_id": 1,
            "name": "192.168.0.1_mysql_3306",
            "bk_biz_id": 2,
            "id": 1,
            "creator": "admin",
            "modifier": "admin",
            "create_time": "2022-05-20T07:52:45.123Z",
            "last_time": "2022-05-20T07:52:45.123Z",
            "bk_supplier_account": "0",
            "process_instances": [
                {
                    "process": {
                        "proc_num": None,
                        "stop_cmd": "",
                        "restart_cmd": "",
                        "face_stop_cmd": "",
                        "bk_process_id": 1,
                        "bk_func_name": "mysqld",
                        "work_path": "",
                        "priority": None,
                        "reload_cmd": "",
                        "bk_process_name": "mysqld",
                        "pid_file": "",
                        "auto_start": None,
                        "bk_start_check_secs": None,
                        "last_time": "2022-05-20T07:52:45.159Z",
                        "create_time": "2022-05-20T07:52:45.159Z",
                        "bk_biz_id": 3,
                        "start_cmd": "",
                        "user": "",
                        "timeout": None,
                        "description": "",
                        "bk_supplier_account": "0",
                        "bk_start_param_regex": "",
                        "service_instance_id": 1,
                        "bind_info": [
                            {
                                "enable": True,
                                "ip": "192.168.0.1",
                                "port": "3306",
                                "protocol": "1",
                                "template_row_id": 1,
                            }
                        ],
                    },
                    "relation": {
                        "bk_biz_id": 3,
                        "bk_process_id": 1,
                        "service_instance_id": 1,
                        "process_template_id": 1,
                        "bk_host_id": 4,
                        "bk_supplier_account": "0",
                    },
                }
            ],
        }
    )
]
