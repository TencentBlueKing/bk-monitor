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
from typing import Any

from bkm_space.utils import bk_biz_id_to_space_uid

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import APMQueryFilterMixin, FilterOperator, TraceDatasourceTarget, TraceQueryGuard
from bkmonitor.data_source.utils.base import sort_fields
from bkmonitor.data_source.utils.query import BaseQuery
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.otel_query import FIELD_OPERATIONS, EnabledStatisticsDimension, FieldTypeEnum
from rum_web.constants import RumQueryMode
from semconv.constants import FieldDisplayType
from semconv.rum.field import FieldSpec
from semconv.rum.trace import SpanSpec


logger = logging.getLogger(__name__)


def equal_filter(field: str, values: list[Any]) -> types.Filter:
    return {"key": field, "value": values, "operator": FilterOperator.EQUAL}


class BaseRumQuery(APMQueryFilterMixin, BaseQuery):
    USING: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_RUM)
    DEFAULT_TIME_FIELD: str = "end_time"
    DEFAULT_SORT = ["-end_time"]
    RECORD_ID_FIELD = "span_id"
    FIELD_OPERATIONS = FIELD_OPERATIONS

    MODE = RumQueryMode.SPAN.value
    use_precomputed = False
    level_query: "BaseRumQuery | None" = None

    data_sources: list[TraceDatasourceTarget]

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__([*data_sources])
        self.data_sources = data_sources

    SPEC = SpanSpec

    NON_DIMENSION_FIELDS = {
        "trace_id",
        "span_id",
        "parent_span_id",
    }

    @property
    def raw_query(self) -> "BaseRumQuery":
        return self

    def query_detail(self, record_id: str) -> dict[str, Any]:
        """按层级记录 ID 查询原始 Span，未找到时返回空字典。"""
        filters: list[types.Filter] = [equal_filter(self.RECORD_ID_FIELD, [record_id])]
        if self.MODE != RumQueryMode.SPAN.value:
            filters.append(equal_filter("attributes.span_type", [self.MODE]))
        records = self.raw_query.query_list(
            start_time=None,
            end_time=None,
            offset=0,
            limit=1,
            filters=filters,
        )
        return records[0] if records else {}

    @classmethod
    def build_query_q(cls, q: QueryConfigBuilder, filters: list[types.Filter] | None, query_string: str = ""):
        return q.filter(cls._build_filters(filters)).query_string(query_string)

    def get_queries(
        self, filters: list[types.Filter] | None = None, query_string: str = ""
    ) -> list[QueryConfigBuilder]:
        return [
            self.build_query_q(
                TraceQueryGuard.apply_q(self._get_q().table(ds.table_id), [ds]),
                filters,
                query_string,
            )
            for ds in self.data_sources
        ]

    def get_qs(self, start_time: int | None, end_time: int | None, using_scope: bool = True) -> UnifyQuerySet:
        qs = super().get_qs(start_time, end_time)
        if not using_scope:
            return qs

        bk_biz_ids = {ds.app.bk_biz_id for ds in self.data_sources}
        if len(bk_biz_ids) != 1:
            return qs
        return qs.scope(bk_biz_ids.pop())

    def query_list(
        self,
        start_time: int | None,
        end_time: int | None,
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

    def query_group_list(
        self,
        start_time: int | None,
        end_time: int | None,
        group_field: str,
        offset: int = 0,
        limit: int = BaseQuery.QUERY_MAX_LIMIT,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """按字段折叠后分页，每组返回排序后的第一条完整记录。"""
        order_by: list[str] = self.process_sort_fields(sort or self.DEFAULT_SORT)
        queries = [q.order_by(*order_by) for q in self.get_queries(filters, query_string)]
        return self._query_group_list(queries, start_time, end_time, group_field, offset, limit)

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

    def statistics(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        cal_type: str,
        baseline: str,
        time_shifts: list[str],
        group_by: list[str] | None = None,
        interval: int | None = None,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
    ) -> dict[str, Any]:
        return self._statistics(
            queries=self.get_queries(filters, query_string),
            start_time=start_time,
            end_time=end_time,
            field=field,
            cal_type=cal_type,
            baseline=baseline,
            time_shifts=time_shifts,
            group_by=group_by,
            interval=interval,
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
            field_dict.get("is_agg", False)
            and field_dict.get("field_type") in EnabledStatisticsDimension.values()
            and spec.field_display_type != FieldDisplayType.DATETIME.value
            and field_dict.get("field_name") not in cls.NON_DIMENSION_FIELDS
        )
        return field_dict

    def query_fields(self, start_time: int | None, end_time: int | None) -> dict[str, dict[str, Any]]:
        """始终提供语义目录，存储元数据就绪时再合并实际字段能力。"""
        field_map: dict[str, dict[str, Any]] = {}
        if self.MODE == RumQueryMode.SPAN.value or self.use_precomputed:
            targets = self.level_query.data_sources if self.level_query is not None else self.data_sources
            try:
                field_map = self._query_fields(
                    [(target.table_id, bk_biz_id_to_space_uid(target.app.bk_biz_id)) for target in targets],
                    start_time,
                    end_time,
                )
            except Exception:
                logger.exception("RUM 字段元数据查询失败，使用 %s 语义目录", self.MODE)
        specs = {spec.get_full_field_name(): spec for spec in self.SPEC.fields()}
        if self.MODE != RumQueryMode.SPAN.value:
            field_map = {name: field for name, field in field_map.items() if name in specs}
        for name, spec in specs.items():
            available = self.MODE == RumQueryMode.SPAN.value or self.use_precomputed or spec.is_real
            field_type = spec.field_type or FieldTypeEnum.KEYWORD.value
            field_map.setdefault(
                name,
                {
                    "field_name": name,
                    "field_type": field_type,
                    "origin_field": name.split(".", 1)[0],
                    "is_searchable": available,
                    "is_agg": available,
                    "is_list": spec.is_real or self.MODE != RumQueryMode.SPAN.value,
                    "supported_operations": self.FIELD_OPERATIONS.get(field_type, []) if available else [],
                },
            )
        for name, field in field_map.items():
            self._apply_field_spec(field, specs.get(name) or self.SPEC.from_field(name))
        return field_map
