# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicabl：qe law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from ..parse_yaml import SnippetRenderer


def test_snippet_render():
    # 测试基本渲染
    result, message, config = SnippetRenderer.render(
        {"snippet": "base.yaml", "name": "test"}, {"base.yaml": {"description": "test message"}}
    )

    assert config == {"name": "test", "description": "test message"}

    # 测试字典嵌套覆盖
    result, message, config = SnippetRenderer.render(
        {"snippet": "base.yaml", "a": 2, "c": {"d": 2}}, {"base.yaml": {"a": 1, "b": 1, "c": {"d": 1, "e": 1}}}
    )

    assert config == {"a": 2, "b": 1, "c": {"d": 2, "e": 1}}

    # 测试列表覆盖
    result, message, config = SnippetRenderer.render(
        {"snippet": "base.yaml", "a": 2, "b": [2, 1]}, {"base.yaml": {"a": 1, "b": [1, 2]}}
    )
    assert config == {"a": 2, "b": [2, 1]}
