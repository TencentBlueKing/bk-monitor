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

from bkmonitor.data_source.data_source import BkRumDataSource
from bkmonitor.data_source.format import flatten_dict_data
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils.base import sort_fields

if TYPE_CHECKING:
    from rum_web.handlers.query.base import BaseRumQuery


class VirtualSortDataSource(BkRumDataSource):
    """复用 RUM 数据源，在存储分页前应用统一的空值排序。"""

    sort_config: list[dict[str, Any]]

    def _process_log_queryset(self, queryset):
        return super()._process_log_queryset(queryset).dsl_sort(self.sort_config)


def build_virtual_sort(owner: "BaseRumQuery", order_by: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    member_names = {name for virtual in owner.virtual_fields.values() for name in virtual.field_names}
    for ordering in order_by:
        field, *direction = ordering.split()
        order: str = direction[0] if direction else "asc"
        spec = owner.SPEC.from_field(field)
        field_type: str = spec.field_type or ("long" if spec.field_display_type == "datetime" else "keyword")
        if field in member_names and field_type == "keyword":
            # 单独比较空值标记，再把 null/缺失/空串统一成同一排序值。
            # 这样下一成员仍可打破平局，且降序也不会把空值移到前面。
            value_source = (
                "if (!doc.containsKey(params.field) || doc[params.field].size() == 0) { return ''; } "
                "return doc[params.field].value;"
            )
            empty_source = (
                "if (!doc.containsKey(params.field) || doc[params.field].size() == 0) { return 1; } "
                "return doc[params.field].value == '' ? 1 : 0;"
            )
            for source, value_type, sort_order in [(empty_source, "number", "asc"), (value_source, "string", order)]:
                result.append(
                    {
                        "_script": {
                            "type": value_type,
                            "order": sort_order,
                            "script": {"lang": "painless", "source": source, "params": {"field": field}},
                        }
                    }
                )
        else:
            result.append({field: {"order": order, "missing": "_last", "unmapped_type": field_type}})
    return result


def query_virtual_sorted_records(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int | None,
    end_time: int | None,
    offset: int,
    limit: int,
    group_field: str | None = None,
) -> list[dict[str, Any]]:
    """每个来源先取排序前缀，跨来源归并后统一分页。"""
    config = owner._add_query(owner.get_qs(start_time, end_time), queries).config
    order_by: list[str] = config["query_configs"][0]["order_by"]
    sort_config = build_virtual_sort(owner, order_by)
    records: list[dict[str, Any]] = []
    for target, query_config in zip(owner.data_sources, config["query_configs"]):
        source = VirtualSortDataSource.init_by_query_config(query_config, bk_biz_id=target.app.bk_biz_id)
        source.sort_config = sort_config
        rows, _ = source.query_log(config["start_time"], config["end_time"], limit=offset + limit, offset=0)
        records.extend(rows)

    def values(record: dict[str, Any]) -> dict[str, Any]:
        return {field: None if value == "" else value for field, value in flatten_dict_data(record).items()}

    ordered = sort_fields(records, order_by, extractor=values)
    if group_field:
        seen: set[Any] = set()
        unique: list[dict[str, Any]] = []
        for record in ordered:
            key = flatten_dict_data(record).get(group_field)
            if key not in seen:
                seen.add(key)
                unique.append(record)
        ordered = unique
    return ordered[offset : offset + limit]
