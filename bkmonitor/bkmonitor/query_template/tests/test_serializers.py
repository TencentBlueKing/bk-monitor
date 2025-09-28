"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

import pytest

from .. import serializers, mock_data


class TestSerializers:
    @pytest.mark.parametrize(
        "template", [mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE, mock_data.CALLEE_P99_QUERY_TEMPLATE]
    )
    def test_query_template_serializers(self, template: dict[str, Any]):
        serializer = serializers.QueryTemplateSerializer(data=template)
        serializer.is_valid(raise_exception=True)
