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


class TestFetchK8sNodePerformanceResource:
    def test_fetch(self, monkeypatch_request_performance_data):
        bk_biz_id = 2
        actual = api.kubernetes.fetch_k8s_node_performance({"bk_biz_id": bk_biz_id, "overview": True})
        expect = {
            'data': {
                '1.1.1.1': {
                    'system_cpu_summary_usage': 9.075679523575623,
                    'system_disk_in_use': 15.570738330489176,
                    'system_io_util': 4.120283131298449,
                    'system_load_load15': 1.38,
                    'system_mem_pct_used': 52.49868644464842,
                },
                '2.2.2.2': {'system_disk_in_use': 15.570854758048107, 'system_mem_pct_used': 52.502145105798235},
            },
            'overview': {
                'system_cpu_summary_usage': 10.545429644132964,
                'system_disk_in_use': 16.898492020154194,
                'system_io_util': 4.79581937143171,
                'system_load_load15': 1.19,
                'system_mem_pct_used': 48.81595433782338,
            },
        }
        assert actual == expect
