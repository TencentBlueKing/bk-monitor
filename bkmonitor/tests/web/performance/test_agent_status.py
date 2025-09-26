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
from core.drf_resource import resource
from tests.web.performance import mock_cache, mock_cc


class TestAgentStatus(object):
    def test_perform_request(self, mocker):
        params = {"host_id": "10.1.1.1|0", "bk_biz_id": 2}

        mock_cc(mocker)
        mock_cache(mocker)
        mocker.patch("utils.host_index_backend.HostIndexBackendBase.data_report_info", return_value={"10.1.1.1": True})

        assert resource.performance.agent_status.request(params) == {"status": 0}
