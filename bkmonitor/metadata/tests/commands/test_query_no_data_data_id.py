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

import json
from io import StringIO

from django.core.management import call_command


def test_input_params():
    out = StringIO()
    call_command("query_no_data_data_id", stderr=out)
    output = out.getvalue()
    assert "please input [bk_biz_id]" in output


def test_query_empty(mocker):
    mocker.patch("core.drf_resource.api.unify_query.query_data_by_promql", return_value={})
    out = StringIO()
    call_command("query_no_data_data_id", **{"bk_biz_id": 2}, stdout=out)
    output = out.getvalue()
    data = json.loads(output)
    assert data["count"] == 0
    assert isinstance(data["result"], list)


def test_query(mocker):
    data_id = 1002
    ret_data = {
        'series': [
            {
                'name': '_result0',
                'metric_name': '',
                'columns': ['_time', '_value'],
                'types': ['float', 'float'],
                'group_keys': ['topic'],
                'group_values': [f'0bkmonitor_{data_id}0'],
                'values': [
                    [1716192300000, 0],
                    [1716192360000, 0],
                    [1716192420000, 0],
                    [1716192480000, 0],
                    [1716192540000, 0],
                    [1716192600000, 0],
                ],
            }
        ]
    }
    mocker.patch("core.drf_resource.api.unify_query.query_data_by_promql", return_value=ret_data)

    out = StringIO()
    call_command("query_no_data_data_id", **{"bk_biz_id": 2}, stdout=out)
    output = out.getvalue()
    data = json.loads(output)
    assert data["count"] == 1
    assert data["result"][0] == data_id
