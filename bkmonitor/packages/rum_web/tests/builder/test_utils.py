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

from rum_web.handlers.builder.utils import get_safe_number


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "NaN", "inf", "-inf"])
def test_non_finite_numbers_use_default(value):
    assert get_safe_number(value) == 0
    assert get_safe_number(value, None) is None
    assert get_safe_number(value, -7.5) == -7.5


@pytest.mark.parametrize(
    "value,expected,expected_type",
    [
        (0, 0, int),
        (0.0, 0, int),
        (42, 42, int),
        (42.0, 42, int),
        (3.25, 3.25, float),
        (-3.25, -3.25, float),
        ("0", 0, int),
        ("42", 42, int),
        ("-3.25", -3.25, float),
        ("1e3", 1000, int),
    ],
)
def test_finite_numbers_preserve_value_and_numeric_type(value, expected, expected_type):
    result = get_safe_number(value, None)
    assert result == expected
    assert type(result) is expected_type


@pytest.mark.parametrize("value", [None, "", "invalid", {}, []])
def test_missing_or_invalid_values_use_default(value):
    assert get_safe_number(value) == 0
    assert get_safe_number(value, None) is None
    assert get_safe_number(value, -7.5) == -7.5
