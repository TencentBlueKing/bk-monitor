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
from unittest import mock

import pytest

from bkm_ipchooser.tools.gse_tool import fill_agent_status


@pytest.fixture
def cc_hosts():
    return [{"bk_host_id": 1, "name": "host1"}, {"bk_host_id": 2, "name": "host2"}, {"bk_host_id": 3, "name": "host3"}]


@pytest.fixture
def mock_host_info():
    return [{"host_id": 1, "alive": 1}, {"host_id": 2, "alive": 0}, {"host_id": 3, "alive": 1}]


def test_fill_agent_status(cc_hosts, mock_host_info):
    bk_biz_id = 2

    with mock.patch("core.drf_resource.api.node_man.ipchooser_host_detail") as mock_ipchooser:
        mock_ipchooser.return_value = mock_host_info
        result = fill_agent_status(cc_hosts, bk_biz_id)
    assert len(result) == 3
    assert result[0]["status"] == 1
    assert result[1]["status"] == 0
    assert result[2]["status"] == 1

    result_empty = fill_agent_status([], bk_biz_id)
    assert result_empty == []
