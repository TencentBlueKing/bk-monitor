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
import pytest
from django.conf import settings
from django.utils.functional import empty

import settings as monitor_settings
from api.cmdb.client import ListServiceInstanceDetail


def pytest_configure():
    # Setup django for every upper key in the settings.py
    config_dict = {key: getattr(monitor_settings, key) for key in dir(monitor_settings) if key.upper() == key}

    # fix database collation
    config_dict["DATABASES"]["default"]["TEST"] = {
        "CHARSET": "utf8",
        "COLLATION": "utf8_general_ci",
    }

    config_dict["DATABASES"]["monitor_api"]["TEST"] = {
        "CHARSET": "utf8",
        "COLLATION": "utf8_general_ci",
    }

    if settings._wrapped is empty:
        settings.configure(**config_dict)


@pytest.fixture
def monkeypatch_list_service_instance_detail(monkeypatch):
    mock_return_value = {
        "count": 1,
        "info": [
            {
                "bk_biz_id": 2,
                "process_instances": [
                    {
                        "process": {
                            "proc_num": None,
                            "bk_start_check_secs": None,
                            "bind_info": [
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 1,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 1,
                                    "port": "80",
                                },
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 2,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 2,
                                    "port": "7000-8000",
                                },
                                {
                                    "enable": True,
                                    "protocol": "1",
                                    "approval_status": "2",
                                    "template_row_id": 3,
                                    "ip": "0.0.0.0",
                                    "type": "custom",
                                    "company_port_id": 3,
                                    "port": "8800",
                                },
                            ],
                            "priority": None,
                            "pid_file": "",
                            "auto_start": None,
                            "stop_cmd": "",
                            "description": "",
                            "bk_process_id": 1,
                            "bk_process_name": "process_name",
                            "bk_start_param_regex": "",
                            "start_cmd": "",
                            "user": "",
                            "face_stop_cmd": "",
                            "bk_biz_id": 2,
                            "bk_func_name": "process_name",
                            "work_path": "",
                            "service_instance_id": 1,
                            "reload_cmd": "",
                            "timeout": None,
                            "bk_supplier_account": "tencent",
                            "restart_cmd": "",
                        },
                        "relation": {
                            "bk_biz_id": 2,
                            "process_template_id": 1,
                            "bk_host_id": 1,
                            "service_instance_id": 1,
                            "bk_process_id": 1,
                            "bk_supplier_account": "tencent",
                        },
                    }
                ],
                "bk_module_id": 1,
                "name": "1.1.1.1_process_name_80",
                "labels": None,
                "bk_host_id": 1,
                "bk_supplier_account": "tencent",
                "service_template_id": 1,
            }
        ],
    }
    monkeypatch.setattr(ListServiceInstanceDetail, "perform_request", lambda *args, **kwargs: mock_return_value)
