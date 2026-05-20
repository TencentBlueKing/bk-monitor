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

from bkmonitor.as_code.utils import create_function_expression


@pytest.mark.parametrize(
    "function",
    [
        {"id": "time_shift", "params": [{"id": "n"}]},
        {"id": "time_shift", "params": [{"id": "n", "value": ""}]},
        {"id": "time_shift", "params": [{"id": "n", "value": None}]},
    ],
)
def test_create_function_expression_ignores_empty_time_shift(function: dict) -> None:
    assert create_function_expression(function) is None
