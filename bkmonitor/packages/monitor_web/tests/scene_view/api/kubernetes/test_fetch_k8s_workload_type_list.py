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
import pytest

from core.drf_resource import api


class TestFetchK8sWorkloadTypeListResource:
    @pytest.mark.django_db
    def test_fetch(self, add_bcs_pods):
        actual = api.kubernetes.fetch_k8s_workload_type_list(
            {
                "bk_biz_id": 2,
            }
        )
        expect = ['StatefulSet']
        assert actual == expect

    @pytest.mark.django_db
    def test_fetch__default_conf(self):
        actual = api.kubernetes.fetch_k8s_workload_type_list(
            {
                "bk_biz_id": 2,
            }
        )
        expect = ['CronJob', 'DaemonSet', 'Deployment', 'Job', 'StatefulSet']
        assert actual == expect
