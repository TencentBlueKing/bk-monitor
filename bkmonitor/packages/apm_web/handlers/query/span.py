"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import TYPE_CHECKING, Any

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery
from constants.otel_query import FIELD_OPERATIONS, OTEL_SPAN_COMMON_FIELD_ALIAS

from apm_web.trace.constants import TRACE_FIELD_ALIAS

if TYPE_CHECKING:
    from apm_web.models import Application


class SpanQuery(BaseQuery):
    """通过 unify-query 查询 APM Span 字段元数据。"""

    FIELD_ALIAS_MAP_LIST = [OTEL_SPAN_COMMON_FIELD_ALIAS, TRACE_FIELD_ALIAS]
    FIELD_OPERATIONS = FIELD_OPERATIONS

    def __init__(self, data_sources: list[TraceDatasourceTarget]) -> None:
        self.data_sources: list[TraceDatasourceTarget] = data_sources

    @classmethod
    def query_fields_by_application(cls, application: "Application") -> dict[str, dict[str, Any]]:
        """按应用的 ES 保留期查询 Span 字段。"""

        start_time, end_time = application.list_retention_time_range()
        data_source = TraceDatasourceTarget.build(
            application.bk_biz_id,
            application.app_name,
            application.trace_result_table_id,
        )
        return cls([data_source]).query_fields(start_time, end_time)

    def query_fields(self, start_time: int, end_time: int) -> dict[str, dict[str, Any]]:
        """查询指定时间范围内的 Span 字段。"""

        return super()._query_fields(
            [
                (data_source.table_id, bk_biz_id_to_space_uid(data_source.app.bk_biz_id))
                for data_source in self.data_sources
            ],
            start_time,
            end_time,
        )
