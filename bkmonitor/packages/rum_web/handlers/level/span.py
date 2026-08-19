"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from typing import Any

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator
from constants.apm import OperatorGroupRelation
from constants.otel_query import OperatorEnum
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.span import SpanQuery
from rum_web.constants import RUM_SEARCH_PAGE_GROUPS


class SpanLevelHandler(BaseRumLevelHandler):
    """Span 层级处理器

    以 SpanQuery 作为主查询，实现 BaseRumLevelHandler 的全部接口能力。
    """

    DEFAULT_SORT = ["-end_time"]
    DISPLAY_FIELDS = [
        "span_name",
        "attributes.span_type",
        "end_time",
        "elapsed_time",
        "status.code",
        "attributes.view.url_template",
        "user.id",
    ]

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
    ) -> list[dict[str, Any]]:
        return self.query.query_list(start_time, end_time, offset, limit, filters, query_string, sort)

    def view_config(
        self,
        start_time: int,
        end_time: int,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        all_fields: dict[str, Any] = self.query.query_fields(start_time, end_time)
        config_dict = {
            "default_sort": copy.deepcopy(self.query.DEFAULT_SORT),
            "fields": [
                {
                    "name": field_name,
                    "alias": field_dict.get("alias_name"),
                    "type": field_dict.get("field_type"),
                    "is_searchable": field_dict.get("is_searchable", False),
                    "is_agg": field_dict.get("is_agg", False),
                    "is_list": field_dict.get("is_list", True),
                    "supported_operations": field_dict.get("supported_operations", []),
                }
                for field_name, field_dict in all_fields.items()
            ],
            "groups": [],
            "display_fields": copy.deepcopy(self.DISPLAY_FIELDS),
        }

        field_map: dict[str, dict[str, Any]] = {}
        for field_name, field_dict in all_fields.items():
            _field_dict = {
                "name": field_name,
                "alias": field_dict["alias_name"],
                "type": field_dict["field_type"],
                "is_searchable": field_dict["is_searchable"],
                "is_agg": field_dict["is_agg"],
                "is_list": field_dict["is_list"],
                "supported_operations": field_dict["supported_operations"],
            }
            if "unit" in field_dict:
                _field_dict["unit"] = field_dict["unit"]
            if "option_values" in field_dict:
                _field_dict["option_values"] = field_dict["option_values"]
            field_map[field_name] = _field_dict
            config_dict["fields"].append(_field_dict)
        # 构建分组关系
        for group in RUM_SEARCH_PAGE_GROUPS.get("span", []):
            config_dict["groups"].append(
                {
                    "name": group["name"],
                    "alias": group["alias"],
                    "fields": [field_map[field_name] for field_name in group["field_names"] if field_name in field_map],
                }
            )
        return config_dict

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

    def generate_query_string(
        self,
        filters: list[types.Filter],
        extra_config: dict[str, Any] | None = None,
    ) -> str:
        generator = QueryStringGenerator(OperatorEnum.QueryStringOperatorMapping)
        for f in filters:
            generator.add_filter(
                f["key"],
                f["operator"],
                f["value"],
                f.get("options", {}).get("is_wildcard", False),
                f.get("options", {}).get("group_relation", OperatorGroupRelation.OR),
            )
        return generator.to_query_string()
