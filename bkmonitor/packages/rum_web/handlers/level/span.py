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
        "attributes.user.id",
    ]
    VIRTUAL_FIELDS = {
        "CLS": {
            "field_name": "CLS",
            "field_alias": "累积布局偏移",
            "field_type": "double",
            "origin_field": "CLS",
            "is_searchable": True,
            "is_agg": True,
            "is_list": False,
            "supported_operations": [],
        },
        "INP": {
            "field_name": "INP",
            "field_alias": "交互到下一次绘制",
            "field_type": "double",
            "field_unit": "ms",
            "origin_field": "INP",
            "is_searchable": True,
            "is_agg": True,
            "is_list": False,
            "supported_operations": [],
        },
        "LCP": {
            "field_name": "LCP",
            "field_alias": "最大内容绘制",
            "field_type": "double",
            "field_unit": "ms",
            "origin_field": "LCP",
            "is_searchable": True,
            "is_agg": True,
            "is_list": False,
            "supported_operations": [],
        },
        "FCP": {
            "field_name": "FCP",
            "field_alias": "首次内容绘制",
            "field_type": "double",
            "field_unit": "ms",
            "origin_field": "FCP",
            "is_searchable": True,
            "is_agg": True,
            "is_list": False,
            "supported_operations": [],
        },
        "TTFB": {
            "field_name": "TTFB",
            "field_alias": "首字节耗时",
            "field_type": "double",
            "field_unit": "ms",
            "origin_field": "TTFB",
            "is_searchable": True,
            "is_agg": True,
            "is_list": False,
            "supported_operations": [],
        },
    }
    VIEW_CONFIG_IGNORE_KEYS = ["is_case_sensitive", "is_analyzed", "wildcard_case_insensitive", "tokenize_on_chars"]

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
        field_map: dict[str, Any] = self.query.query_fields(start_time, end_time)

        # 丢弃查询层私有键，其余字段直接透传给接口层
        for field_name, field_dict in field_map.items():
            for key in self.VIEW_CONFIG_IGNORE_KEYS:
                field_dict.pop(key, None)
        # mapping 没有的虚拟字段，先补进 field_map，WEB_VITALS 才组得起来
        for name, meta in self.VIRTUAL_FIELDS.items():
            field_map.setdefault(name, meta)

        return {
            "default_sort": list(self.query.DEFAULT_SORT),
            "fields": list(field_map.values()),
            "groups": [
                {
                    "name": group["name"],
                    "alias": group["alias"],
                    "fields": [field_map[name] for name in group["field_names"] if name in field_map],
                }
                for group in RUM_SEARCH_PAGE_GROUPS.get("span", [])
            ],
            "display_fields": list(self.DISPLAY_FIELDS),
        }

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
