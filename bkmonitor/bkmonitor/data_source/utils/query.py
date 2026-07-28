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
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions


class BaseQuery:
    DEFAULT_TIME_FIELD = "time"
    DEFAULT_SORT = ["time"]

    @classmethod
    def get_q_from_query_config(cls, query_config: dict[str, Any]) -> QueryConfigBuilder:
        return (
            QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
            .table(query_config["table"])
            .time_field(cls.DEFAULT_TIME_FIELD)
            .group_by(*query_config.get("group_by", []))
            .conditions(query_config.get("where", []))
            .filter(conditions_to_q(filter_dict_to_conditions(query_config.get("filter_dict") or {}, [])))
            .query_string(query_config.get("query_string") or "")
        )

    @classmethod
    def process_sort_fields(cls, fields):
        """
        预处理排序字段列表，调整字段排序格式

        :param fields: 原始排序字段列表，如 ["-time", "name"]
        :return: 处理后的排序字段列表，如 ["time desc", "name"]
        """
        processed_fields = []
        for field in fields:
            # 提取字段名（去掉可能的 "-" 前缀）
            is_descending = field.startswith("-")
            field = field[1:] if is_descending else field

            # 保留原始排序方向
            if is_descending:
                processed_fields.append(f"{field} desc")
            else:
                processed_fields.append(field)
        return processed_fields

    @classmethod
    def _add_query(cls, qs: UnifyQuerySet, q_list: list[QueryConfigBuilder]) -> UnifyQuerySet:
        for q in q_list:
            qs = qs.add_query(q)
        return qs

    @classmethod
    def _to_milliseconds(cls, ts: int) -> int:
        return ts * 1000 if len(str(ts)) == 10 else ts

    def _get_time_range(self, start_time: int, end_time: int) -> tuple[int, int]:
        return self._to_milliseconds(start_time), self._to_milliseconds(end_time)

    def time_range_queryset(self, start_time: int, end_time: int) -> UnifyQuerySet:
        start_time, end_time = self._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False)

    def _query_list(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        qs = self.time_range_queryset(start_time, end_time).offset(offset).limit(limit)
        return list(self._add_query(qs, queries))

    def _query_total(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
    ) -> int:
        qs = self.time_range_queryset(start_time, end_time).time_agg(False).instant().limit(1)
        return list(self._add_query(qs, queries))[0]["_result_"]

    def _query_field_topk(
        self,
        queries: list[QueryConfigBuilder],
        start_time: int,
        end_time: int,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        alias: str = "a"
        qs = self.time_range_queryset(start_time, end_time).expression(alias).time_agg(False).instant().limit(limit)
        return list(self._add_query(qs, queries))
