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

from core.drf_resource import api


class TestGetProcess:
    def test_perform_request(self, monkeypatch_list_service_instance_detail):
        processes = api.cmdb.get_process(bk_biz_id=2, bk_host_id=1)
        assert len(processes) == 1
        expect = {
            "bind_ip": "0.0.0.0",
            "bk_func_name": "process_name",
            "bk_host_id": 1,
            "bk_process_id": 1,
            "bk_process_name": "process_name",
            "port": "80",
            "process_template_id": 1,
            "protocol": "1",
            "service_instance_id": 1,
        }
        assert processes[0].__dict__ == expect

    def test_perform_request__include_multiple_bind_info(self, monkeypatch_list_service_instance_detail):
        processes = api.cmdb.get_process(bk_biz_id=2, bk_host_id=1, include_multiple_bind_info=True)
        assert len(processes) == 3
        actual = [process.__dict__ for process in processes]
        expect = [
            {
                "bind_ip": "0.0.0.0",
                "bk_func_name": "process_name",
                "bk_host_id": 1,
                "bk_process_id": 1,
                "bk_process_name": "process_name",
                "port": "80",
                "process_template_id": 1,
                "protocol": "1",
                "service_instance_id": 1,
            },
            {
                "bind_ip": "0.0.0.0",
                "bk_func_name": "process_name",
                "bk_host_id": 1,
                "bk_process_id": 1,
                "bk_process_name": "process_name",
                "port": "7000-8000",
                "process_template_id": 1,
                "protocol": "1",
                "service_instance_id": 1,
            },
            {
                "bind_ip": "0.0.0.0",
                "bk_func_name": "process_name",
                "bk_host_id": 1,
                "bk_process_id": 1,
                "bk_process_name": "process_name",
                "port": "8800",
                "process_template_id": 1,
                "protocol": "1",
                "service_instance_id": 1,
            },
        ]
        assert actual == expect
