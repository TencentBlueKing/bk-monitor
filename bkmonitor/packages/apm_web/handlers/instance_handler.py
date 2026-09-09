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

from apm_web.constants import InstanceDiscoverKeys
from apm_web.handlers.query import get_query
from apm_web.models import Application
from constants.apm import OtlpKey


class InstanceHandler:
    BK_INSTANCE_ID_FIELD_NAME = OtlpKey.get_resource_key(OtlpKey.BK_INSTANCE_ID)

    @classmethod
    def get_span_fields(cls, app: Application) -> list[dict[str, Any]]:
        """获取所有 Resource 类型的 Span 字段。"""

        fields_info = get_query(app.build_data_sources()).query_fields(None, None)
        field_names: list[str] = [
            field_name
            for field_name, field_info in fields_info.items()
            if field_info["origin_field"] == OtlpKey.RESOURCE
            and field_info["is_searchable"]
            and field_name != cls.BK_INSTANCE_ID_FIELD_NAME
        ]

        return [
            {"id": field_name, "name": field_name, "alias": InstanceDiscoverKeys.get_label_by_key(field_name)}
            for field_name in field_names
        ]
