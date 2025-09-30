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
from constants.data_source import LabelType

from .data import ALL_LABEL_MSG, HANDEL_LABEL_MSG


@pytest.mark.usefixtures("mock_cache")
class TestGetScenarioListResource(object):
    def test_get_all_label(self, mocker):
        request_data = {"label_type": LabelType.ResultTableLabel, "include_admin_only": True}

        # 获取所有的标签
        get_label_func = mocker.patch(
            "monitor_web.commons.data.resources.api.metadata.get_label",
            return_value={"result_table_label": ALL_LABEL_MSG},
        )
        assert resource.strategies.get_scenario_list() == HANDEL_LABEL_MSG
        get_label_func.assert_called_once_with(**request_data)
