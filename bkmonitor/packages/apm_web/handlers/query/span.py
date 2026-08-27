"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import TYPE_CHECKING, Any

from bkm_space.utils import bk_biz_id_to_space_uid
from constants.otel_query import FIELD_OPERATIONS, OTEL_SPAN_COMMON_FIELD_ALIAS

from apm_web.handlers.query.base import BaseQuery
from apm_web.trace.constants import TRACE_FIELD_ALIAS

if TYPE_CHECKING:
    from apm_web.models import Application

logger = logging.getLogger("apm")


class SpanQuery(BaseQuery):
    """通过 unify-query 查询 APM Span 字段元数据。"""

    FIELD_ALIAS_MAP_LIST: list[dict[str, Any]] = [OTEL_SPAN_COMMON_FIELD_ALIAS, TRACE_FIELD_ALIAS]
    FIELD_OPERATIONS = FIELD_OPERATIONS

    @classmethod
    def query_fields_by_application(cls, application: "Application") -> dict[str, dict[str, Any]]:
        """按应用配置的数据保留期查询 Span 字段。"""

        query = cls.from_application(application)
        fields_info = query.query_fields(None, None)
        if not fields_info:
            data_source = query.data_sources[0]
            logger.warning(
                "[SpanQuery] query fields returned empty: bk_biz_id=%s, app_name=%s, table_id=%s, retention=%s",
                data_source.app.bk_biz_id,
                data_source.app.app_name,
                data_source.table_id,
                data_source.retention,
            )
        return fields_info

    def query_fields(self, start_time: int | None, end_time: int | None) -> dict[str, dict[str, Any]]:
        """查询 Span 字段，缺省时间范围由 Target 的数据保留期补齐。"""

        return super()._query_fields(
            [
                (data_source.table_id, bk_biz_id_to_space_uid(data_source.app.bk_biz_id))
                for data_source in self.data_sources
            ],
            start_time,
            end_time,
        )
