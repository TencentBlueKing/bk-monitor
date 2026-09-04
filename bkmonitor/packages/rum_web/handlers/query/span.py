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
from bkmonitor.data_source.utils.base import sort_fields
from bkmonitor.data_source.utils.query import BaseQuery
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils.apm import APMQueryFilterMixin
from bkm_space.utils import bk_biz_id_to_space_uid
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.otel_query import FIELD_OPERATIONS, EnabledStatisticsDimension

from semconv.rum.field import FieldSpec
from semconv.rum.trace import SpanSpec
from semconv.constants import FieldDisplayType


class SpanQuery(APMQueryFilterMixin, BaseQuery):
    USING: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_RUM)
    DEFAULT_TIME_FIELD = "end_time"
    DEFAULT_SORT = ["-end_time"]
    FIELD_OPERATIONS = FIELD_OPERATIONS

    NON_DIMENSION_FIELDS = {
        "trace_id",
        "span_id",
        "parent_span_id",
    }

    @classmethod
    def build_query_q(cls, q: QueryConfigBuilder, filters: list[types.Filter] | None, query_string: str = ""):
        return q.filter(cls._build_filters(filters)).query_string(query_string)

    def get_queries(
        self, filters: list[types.Filter] | None = None, query_string: str = ""
    ) -> list[QueryConfigBuilder]:
        return [
            self.build_query_q(
                self._get_q().table(ds.table_id),
                filters,
                query_string,
            )
            for ds in self.data_sources
        ]

    def get_qs(self, start_time: int, end_time: int, using_scope: bool = True) -> UnifyQuerySet:
        qs = super().get_qs(start_time, end_time)
        if not using_scope:
            return qs

        bk_biz_ids = {ds.app.bk_biz_id for ds in self.data_sources}
        if len(bk_biz_ids) != 1:
            return qs
        return qs.scope(bk_biz_ids.pop())

    def query_list(
        self,
        start_time: int,
        end_time: int,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        processed_sort_fields = self.process_sort_fields(sort or self.DEFAULT_SORT)
        queries = [q.order_by(*processed_sort_fields) for q in self.get_queries(filters, query_string)]
        return sort_fields(super()._query_list(queries, start_time, end_time, offset, limit), processed_sort_fields)

    def query_total(
        self,
        start_time: int,
        end_time: int,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
    ) -> int:
        return super()._query_total(self.get_queries(filters, query_string), start_time, end_time)

    def query_field_topk(
        self,
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        need_empty: bool = False,
    ):
        return super()._query_field_topk(
            self.get_queries(filters, query_string), start_time, end_time, field, limit, need_empty
        )

    def query_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int,
        filters: list[types.Filter],
        query_string: str,
    ):
        return super()._query_option_values(
            self.get_queries(filters, query_string), start_time, end_time, fields, limit
        )

    def query_graph_config(
        self,
        start_time: int,
        end_time: int,
        field: str,
        filters: list[types.Filter],
        query_string: str,
    ):
        return super()._query_graph_config(self.get_queries(filters, query_string), start_time, end_time, field)

    def query_field_aggregated_value(
        self,
        start_time: int,
        end_time: int,
        field: str,
        method: str,
        filters: list[types.Filter],
        query_string: str,
    ):
        return super()._query_field_aggregated_value(
            self.get_queries(filters, query_string), start_time, end_time, field, method
        )

    @classmethod
    def _apply_field_spec(cls, field_dict: dict[str, Any], spec: FieldSpec) -> dict[str, Any]:
        """将 FieldSpec 中的数据（单位、展示类型、枚举候选值）填充到字段字典中。

        仅当 spec 显式提供对应值时才写入，避免覆盖 data_source 返回的原始值；
        枚举候选值统一转换为 ``{"value": ..., "alias": ...}`` 列表以便 JSON 序列化。
        """
        field_dict["field_alias"] = spec.field_alias or field_dict.get("field_alias") or spec.get_full_field_name()
        field_dict["is_real"] = spec.is_real
        if spec.field_unit is not None:
            field_dict["field_unit"] = spec.field_unit
        if spec.field_type is not None:
            field_dict["field_type"] = spec.field_type
        if spec.field_display_type is not None:
            field_dict["field_display_type"] = spec.field_display_type
        if spec.option_values is not None:
            field_dict["option_values"] = [
                {"value": value, "alias": alias} for value, alias in spec.option_values.choices()
            ]
        if spec.rating_config:
            field_dict["rating_config"] = []
            for config in spec.rating_config:
                item = {"rating": config.rating}
                if config.value is not None:
                    item["value"] = config.value
                field_dict["rating_config"].append(item)
        field_dict["is_agg"] = (
            field_dict["is_agg"]
            and field_dict["field_type"] in EnabledStatisticsDimension.values()
            and spec.field_display_type not in {FieldDisplayType.DATETIME.value}
            and field_dict["field_name"] not in cls.NON_DIMENSION_FIELDS
        )
        return field_dict

    def query_fields(self, start_time: int | None, end_time: int | None) -> dict[str, dict[str, Any]]:
        """查询字段元数据，并通过 SpanSpec 补充别名、单位和枚举候选值。"""
        field_map = super()._query_fields(
            [(target.table_id, bk_biz_id_to_space_uid(target.app.bk_biz_id)) for target in self.data_sources],
            start_time,
            end_time,
        )
        # 真实字段
        for field_name, field_dict in field_map.items():
            self._apply_field_spec(field_dict, SpanSpec.from_field(field_name))

        # 虚拟字段
        for spec in SpanSpec.fields():
            field_name = spec.get_full_field_name()
            if spec.is_real or field_name in field_map:
                continue
            field_dict = {
                "field_name": field_name,
                "is_searchable": True,
                "is_agg": True,
                "is_list": False,
                "origin_field": field_name.split(".", 1)[0],
                "supported_operations": self.FIELD_OPERATIONS.get(spec.field_type, []),
            }
            self._apply_field_spec(field_dict, spec)
            field_map[field_name] = field_dict
        return field_map
