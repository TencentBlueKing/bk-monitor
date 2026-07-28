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

from bkmonitor.data_source.utils.query import BaseQuery
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet


class SpanQuery(BaseQuery):
    def __init__(self, bk_biz_id: int):
        self.bk_biz_id = bk_biz_id

    def time_range_queryset(self, start_time: int, end_time: int) -> UnifyQuerySet:
        return super().time_range_queryset(start_time, end_time).scope(bk_biz_id=self.bk_biz_id)

    def query_list(
        self,
        start_time: int,
        end_time: int,
        offset: int,
        limit: int,
        query_configs: list[dict[str, Any]],
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        processed_sort_fields = self.process_sort_fields(sort or self.DEFAULT_SORT)
        queries: list[QueryConfigBuilder] = [
            self.get_q_from_query_config(query_config).order_by(*processed_sort_fields)
            for query_config in query_configs
        ]
        return super()._query_list(queries, start_time, end_time, offset, limit)

    def query_total(
        self,
        start_time: int,
        end_time: int,
        query_configs: list[dict[str, Any]],
    ) -> int:
        alias: str = "a"
        # 构建查询列表
        queries = [
            self.get_q_from_query_config(query_config).alias(alias).metric(field="_index", method="COUNT", alias=alias)
            for query_config in query_configs
        ]
        return super()._query_total(queries, start_time, end_time)

    def query_field_topk(
        self,
        start_time: int,
        end_time: int,
        query_configs: list[dict[str, Any]],
        field: str,
        limit: int = 5,
        need_empty: bool = False,
    ):
        alias: str = "a"
        queries = [
            self.get_q_from_query_config(query_config)
            .metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
            .group_by(field)
            .order_by("_value desc")
            for query_config in query_configs
        ]
        return super()._query_field_topk(queries, start_time, end_time, limit)
