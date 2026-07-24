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

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet


class QueryExecutor:
    def __init__(self, start_time: int, end_time: int, bk_biz_id: int | None = None, time_align: bool = False):
        start_time, end_time = self._get_time_range(start_time, end_time)
        self.queryset = UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(time_align)
        if bk_biz_id is not None:
            self.queryset.scope(bk_biz_id)

    @classmethod
    def _to_milliseconds(cls, ts: int) -> int:
        return ts * 1000 if len(str(ts)) == 10 else ts

    @classmethod
    def _get_time_range(cls, start_time: int, end_time: int) -> tuple[int, int]:
        return cls._to_milliseconds(start_time), cls._to_milliseconds(end_time)

    def _add_query(self, q_list: list[QueryConfigBuilder]):
        for q in q_list:
            self.queryset.add_query(q)

    def query_list(self, q_list: list[QueryConfigBuilder], offset: int, limit: int = 20) -> list[dict[str, Any]]:
        self.queryset.offset(offset).limit(limit)
        self._add_query(q_list)
        return list(self.queryset)

    def query_total(self, q_list: list[QueryConfigBuilder], alias: str = "a"):
        self.queryset.expression(alias).time_agg(False).instant().limit(1)
        self._add_query(q_list)
        return list(self.queryset)[0]["_result_"]

    def query_field_distinct(self, q_list: list[QueryConfigBuilder], alias: str = "a"):
        self.queryset.expression(alias).time_agg(False).instant().limit(1)
        self._add_query(q_list)
        return list(self.queryset)[0]["_result_"]

    def query_field_topk(self, q_list: list[QueryConfigBuilder], alias: str = "a", limit: int = 5):
        self.queryset.expression(alias).time_agg(False).instant().limit(limit)
        self._add_query(q_list)
        return list(self.queryset)

    def query_graph_config(self, q_list: list[QueryConfigBuilder], limit: int = 20):
        self.queryset.time_agg(False).instant()
        self._add_query(q_list)
        return list(self.queryset.limit(limit))

    def query_field_aggregated_value(self, q_list: list[QueryConfigBuilder], method: str, alias: str = "a"):
        self.queryset.time_agg(False).instant().expression(
            f"{method}({alias})" if method in {"max", "min"} else alias
        ).limit(1)
        self._add_query(q_list)
        return self.queryset.original_data[0]["_result_"]
