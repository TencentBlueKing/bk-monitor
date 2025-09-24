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


class TestFetchNodeUsage:
    def test_fetch(self, monkeypatch_kubernetes_fetch_node_cpu_usage):
        bk_biz_id = 2
        bulk_params = [
            {
                "bk_biz_id": bk_biz_id,
            }
        ]
        actual = api.kubernetes.fetch_node_cpu_usage.bulk_request(bulk_params)
        expect = [
            {
                "1.1.1.1": 0.10566185611882578,
                "2.2.2.2": 0.06742554365994677,
            }
        ]
        assert actual == expect
