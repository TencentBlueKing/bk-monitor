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

from django.http import QueryDict

from apm_web.profile.serializers import ProfileQueryExportSerializer


def test_profile_export_serializer_parse_filter_labels_from_query_string():
    """Profile 下载接口需要兼容前端拼在 GET query string 中的 JSON 过滤条件。"""
    query_params = QueryDict(mutable=True)
    query_params.update(
        {
            "bk_biz_id": "2",
            "app_name": "demo",
            "service_name": "demo_service",
            "start": "1710000000000000",
            "end": "1710000300000000",
            "data_type": "CPU",
            "export_format": "pprof",
            "filter_labels": json.dumps({"region": "ap-guangzhou", "env": "prod"}),
            "diff_filter_labels": json.dumps({"region": "ap-shanghai"}),
        }
    )

    serializer = ProfileQueryExportSerializer(data=query_params)

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["filter_labels"] == {"region": "ap-guangzhou", "env": "prod"}
    assert serializer.validated_data["diff_filter_labels"] == {"region": "ap-shanghai"}
