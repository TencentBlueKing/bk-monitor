# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


def assert_dict_contains(data: dict, expect: dict):
    """测试字典是否包含指定数据 ."""
    for key, value in expect.items():
        if isinstance(value, dict):
            assert_dict_contains(data.get(key), value)
        elif isinstance(value, list):
            assert_list_contains(data.get(key), value)
        else:
            assert data.get(key) == value


def assert_list_contains(data: list, expect: list):
    """测试数组是否包含指定数据 ."""
    assert len(data) == len(expect)
    for index, value in enumerate(expect):
        if isinstance(value, dict):
            assert_dict_contains(data[index], value)
        elif isinstance(value, list):
            assert_list_contains(data[index], value)
        else:
            assert data[index] == value
