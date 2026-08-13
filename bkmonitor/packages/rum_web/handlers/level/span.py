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

from django.utils.translation import gettext_lazy as _


from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.span import SpanQuery
from rum_web.constants import RUM_SEARCH_PAGE_GROUPS, RUM_LEVEL_FIELD_GROUP_MAP


class SpanLevelHandler(BaseRumLevelHandler):
    """Span 层级处理器

    以 SpanQuery 作为主查询，实现 BaseRumLevelHandler 的全部接口能力。
    """

    RUM_FIELD_GROUP_MAP = RUM_LEVEL_FIELD_GROUP_MAP.get("span", {})

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__(data_sources)
        self.query = SpanQuery(data_sources)

    def list_records(
        self,
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 10,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "total": self.query.query_total(start_time, end_time, filters, query_string),
            "data": self.query.query_list(start_time, end_time, offset, limit, filters, query_string, sort),
        }

    def view_config(
        self,
        start_time: int,
        end_time: int,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        configs: list[dict[str, Any]] = []

        for field_name, field_dict in self.query.query_fields(start_time, end_time).items():
            configs.append(
                {
                    "name": field_name,
                    "alias": field_dict.get("alias_name"),
                    "type": field_dict.get("field_type"),
                    "is_searched": field_dict.get("is_searchable", False),
                    "is_dimensions": field_dict.get("is_agg", False),
                    "can_displayed": True,
                    "supported_operations": field_dict.get("supported_operations", []),
                    "group_name": self.RUM_FIELD_GROUP_MAP.get(field_name, _("其他")),
                }
            )
        return {"fields": configs, "groups": RUM_SEARCH_PAGE_GROUPS.get("span", [])}

    def get_fields_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int = 10,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, list[str]]:
        return self.query.query_option_values(start_time, end_time, fields, limit, filters or [], query_string)

    def field_topk(
        self,
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def field_statistics_info(
        self,
        start_time: int,
        end_time: int,
        field: dict[str, Any],
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def field_statistics_graph(
        self,
        start_time: int,
        end_time: int,
        field: dict[str, Any],
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def download_topk(
        self,
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> bytes:
        raise NotImplementedError

    def record_detail(
        self,
        record_id: str,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError
