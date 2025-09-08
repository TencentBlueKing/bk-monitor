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

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from tests.web.performance import mock_cache, mock_cc


class TestProcessStatus(object):
    def test_process_status_no_host(self, mocker):
        mock_cache(mocker)
        mock_cc(mocker)
        with pytest.raises(CustomException):
            resource.performance.host_performance_detail.request(ip="10.1.1.1", bk_cloud_id=0)
