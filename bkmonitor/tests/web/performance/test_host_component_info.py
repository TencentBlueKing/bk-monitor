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
#!/usr/bin/python
# -*- coding: utf-8 -*-

from core.drf_resource import resource


class TestHostComponentInfo(object):
    def test_instance(self, mocker):
        get_port_info = {
            "list": [
                {
                    "bk_biz_id": "2",
                    "proc_name": "consul",
                    "display_name": "consul-agent",
                    "port_health": 1,
                    "ip": "10.1.1.1",
                    "hostname": "beanstalk-1",
                    "param_regex": None,
                    "not_accurate_listen": "[]",
                    "bk_cloud_id": "0",
                    "proc_exists": 1,
                    "time": 1556106975000,
                    "protocol": "tcp",
                    "nonlisten": "[]",
                    "bk_supplier_id": "0",
                    "listen": "[8301,8500,53]",
                },
                {
                    "bk_biz_id": "2",
                    "proc_name": "consul",
                    "display_name": "consul-agent",
                    "port_health": 1,
                    "ip": "10.1.1.1",
                    "hostname": "beanstalk-1",
                    "param_regex": None,
                    "not_accurate_listen": "[]",
                    "bk_cloud_id": "0",
                    "proc_exists": 1,
                    "time": 1556107035000,
                    "protocol": "tcp",
                    "nonlisten": "[]",
                    "bk_supplier_id": "0",
                    "listen": "[53,8301,8500]",
                },
                {
                    "bk_biz_id": "2",
                    "proc_name": "consul",
                    "display_name": "consul-agent",
                    "port_health": 1,
                    "ip": "10.1.1.1",
                    "hostname": "beanstalk-1",
                    "param_regex": None,
                    "not_accurate_listen": "[]",
                    "bk_cloud_id": "0",
                    "proc_exists": 1,
                    "time": 1556107095000,
                    "protocol": "tcp",
                    "nonlisten": "[]",
                    "bk_supplier_id": "0",
                    "listen": "[8301,8500,53]",
                },
                {
                    "bk_biz_id": "2",
                    "proc_name": "consul",
                    "display_name": "consul-agent",
                    "port_health": 1,
                    "ip": "10.1.1.1",
                    "hostname": "beanstalk-1",
                    "param_regex": None,
                    "not_accurate_listen": "[]",
                    "bk_cloud_id": "0",
                    "proc_exists": 1,
                    "time": 1556107155000,
                    "protocol": "tcp",
                    "nonlisten": "[]",
                    "bk_supplier_id": "0",
                    "listen": "[8301,8500,53]",
                },
            ]
        }
        mocker.patch("utils.query_data.query", return_value=get_port_info)
        assert resource.performance.host_component_info.request(
            ip="10.0.2.24", bk_cloud_id="0", name="consul-agent", bk_biz_id="2"
        ) == {
            "ports": {
                "53": {"actual_ip": "", "config_ip": "", "status": 0},
                "8301": {"actual_ip": "", "config_ip": "", "status": 0},
                "8500": {"actual_ip": "", "config_ip": "", "status": 0},
            },
            "status": 0,
        }

    def test_not_data(self, mocker):
        mocker.patch("utils.query_data.query", return_value={"list": []})
        assert resource.performance.host_component_info.request(
            ip="10.0.2.24", bk_cloud_id="0", name="consul-agent", bk_biz_id="2"
        ) == {"status": -1, "ports": {}}
