"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from rest_framework.exceptions import ValidationError

from bkmonitor.data_source.data_source import BkRumDataSource
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils.base import get_bar_interval_number
from bkmonitor.utils.time_tools import time_interval_align
from rum_web.virtual_fields import VirtualField, normalize_filter

if TYPE_CHECKING:
    from rum_web.handlers.query.base import BaseRumQuery


BUCKET_PAGE_SIZE = 1000
Record = dict[str, Any]


def _raw_dimensions(fields: list[str], virtual_fields: dict[str, VirtualField]) -> list[str]:
    return list(
        dict.fromkeys(
            member
            for field in fields
            for member in (virtual_fields[field].field_names if field in virtual_fields else [field])
        )
    )


def iter_joint_buckets(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int | None,
    end_time: int | None,
    dimensions: list[str],
    metrics: list[Record],
) -> Iterator[Record]:
    """经已有 RUM ES 路由完整遍历联合桶，保留原查询的租户、应用和过滤约束。

    remote UnifyQuery 暂未暴露 composite 游标，不能用其有上限的 terms 结果
    计算虚拟 Top-K。本地路由复用当前 RUM 的 ES 存储，不获取原始日志。
    """
    prepared: list[QueryConfigBuilder] = []
    for query in queries:
        query = query.group_by(*dimensions)
        for metric in metrics:
            query = query.metric(**metric)
        prepared.append(query)
    config: Record = owner._add_query(owner.get_qs(start_time, end_time), prepared).config
    targets = owner.level_query.data_sources if owner.level_query is not None else owner.data_sources
    # get_queries 为每个目标生成一条带 TraceQueryGuard 的查询，顺序与目标一致。
    for target, query_config in zip(targets, config["query_configs"], strict=True):
        source: BkRumDataSource = BkRumDataSource.init_by_query_config(query_config, bk_biz_id=target.app.bk_biz_id)
        start, end = source._process_time_range(config["start_time"], config["end_time"])
        queryset = (
            source._get_queryset(
                bk_tenant_id=source.bk_tenant_id,
                metrics=query_config["metrics"],
                table=source.table,
                agg_condition=source.where,
                where=source.filter_dict,
                group_by=dimensions,
                query_string=source.query_string,
                nested_paths=source.nested_paths,
                time_field=source.time_field,
                start_time=start,
                end_time=end,
                time_align=False,
                use_full_index_names=True,
                limit=BUCKET_PAGE_SIZE,
            )
            .dsl_date_histogram(False)
            .dsl_group_hits(-1)
        )
        if not dimensions:
            yield from queryset.raw_data
            continue
        after: Record = {}
        while True:
            records: list[Record] = queryset.dsl_search_after(after, missing_bucket=True).raw_data
            if not records:
                break
            next_after: Record | None = records[-1].get("_after_key_")
            for record in records:
                yield {key: value for key, value in record.items() if key != "_after_key_"}
            if next_after is None:
                break
            if next_after == after:
                raise RuntimeError("ES 联合分组游标未前进，无法完整计算虚拟字段分析")
            after = next_after


def query_virtual_values(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int | None,
    end_time: int | None,
    field: str,
) -> dict[str | None, int]:
    """先完整合并最终值，再由调用方决定空值、比例和 Top-K。"""
    virtual: VirtualField = owner.virtual_fields[field]
    counts: dict[str | None, int] = defaultdict(int)
    for record in iter_joint_buckets(
        owner,
        queries,
        start_time,
        end_time,
        virtual.field_names,
        [{"field": "_index", "method": "COUNT", "alias": "_records"}],
    ):
        counts[virtual.format(record)] += int(record["_records"] or 0)
    return dict(counts)


def query_virtual_graph_configs(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int,
    end_time: int,
    field: str,
    values: list[str],
) -> list[tuple[str, Record]]:
    """每条曲线直接查询最终值的完整反解集合，避免原始成员缺失导致丢点。"""
    virtual: VirtualField = owner.virtual_fields[field]
    configs: list[tuple[str, Record]] = []
    for value in dict.fromkeys(values):
        filtered: list[QueryConfigBuilder] = [
            query.filter(normalize_filter(virtual.build_filter(value)))
            .alias("a")
            .interval(get_bar_interval_number(start_time, end_time))
            .metric(field="_index", method="COUNT", alias="a")
            for query in queries
        ]
        config: Record = owner._add_query(
            owner.get_qs(start_time, end_time).expression("a").time_agg(False).instant(), filtered
        ).config
        configs.append((value, config))
    return configs


def _time_windows(
    owner: "BaseRumQuery",
    start_time: int | None,
    end_time: int | None,
    time_group: bool,
    interval: int | None,
) -> Iterator[tuple[int, int, int | None]]:
    start, end = owner._get_time_range(start_time, end_time)
    if not time_group:
        yield start // 1000, end // 1000, None
        return
    interval = interval or get_bar_interval_number(start // 1000, end // 1000)
    step: int = interval * 1000
    bucket: int = time_interval_align(start // 1000, interval) * 1000
    while bucket < end:
        yield max(start, bucket) // 1000, min(end, bucket + step) // 1000, bucket
        bucket += step


def _final_dimensions(record: Record, dimensions: list[str], virtual_fields: dict[str, VirtualField]) -> Record:
    return {
        field: virtual_fields[field].format(record) if field in virtual_fields else record.get(field)
        for field in dimensions
    }


def _weighted_percentile(frequencies: dict[int | float, int], percentile: int) -> int | float:
    """按完整样本的 (N - 1) * p 秩线性插值，无需展开重复样本。

    先跨原始桶和来源合并频数，再取最终虚拟组的百分位，不能合并源百分位标量。
    """
    total: int = sum(frequencies.values())
    if not total:
        return 0
    lower_rank, remainder = divmod((total - 1) * percentile, 100)
    upper_rank: int = lower_rank + bool(remainder)
    cumulative: int = 0
    lower_value: int | float | None = None
    for value, count in sorted(frequencies.items()):
        cumulative += count
        if lower_value is None and lower_rank < cumulative:
            lower_value = value
        if upper_rank < cumulative:
            return lower_value + (value - lower_value) * remainder / 100
    raise ValueError("百分位必须在 0 至 100 之间")


def _query_grouped_window(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int,
    end_time: int,
    fields: list[str],
    method: str,
    dimensions: list[str],
) -> list[Record]:
    virtual_fields: dict[str, VirtualField] = owner.virtual_fields
    if any(field in virtual_fields for field in fields) and method not in {"count", "distinct"}:
        raise ValidationError("虚拟字段是离散维度，仅支持 count 和 distinct 聚合")
    percentile: int | None = int(method[2:]) if method.startswith("cp") else None
    raw_fields: list[str] = [*dimensions]
    metrics: list[Record] = [{"field": "_index", "method": "COUNT", "alias": "_records"}]
    for index, field in enumerate(fields):
        if field in virtual_fields or method == "distinct" or percentile is not None:
            raw_fields.append(field)
        elif method == "avg":
            metrics.extend(
                [
                    {"field": field, "method": "SUM", "alias": f"m{index}"},
                    {"field": field, "method": "COUNT", "alias": f"n{index}"},
                ]
            )
        else:
            metrics.append({"field": field, "method": method, "alias": f"m{index}"})
    states: dict[tuple, list[Record]] = {}
    for record in iter_joint_buckets(
        owner, queries, start_time, end_time, _raw_dimensions(raw_fields, virtual_fields), metrics
    ):
        group: Record = _final_dimensions(record, dimensions, virtual_fields)
        key: tuple = tuple(group.items())
        if key not in states:
            states[key] = [
                {"value": None, "sum": 0, "count": 0, "distinct": set(), "frequencies": defaultdict(int)}
                for _ in fields
            ]
        accumulators: list[Record] = states[key]
        for index, (field, accumulator) in enumerate(zip(fields, accumulators, strict=True)):
            if method == "distinct":
                value = virtual_fields[field].format(record) if field in virtual_fields else record.get(field)
                if value is not None:
                    accumulator["distinct"].add(value)
            elif percentile is not None:
                value = record.get(field)
                if value is not None:
                    accumulator["frequencies"][value] += int(record["_records"] or 0)
            elif field in virtual_fields:
                if virtual_fields[field].format(record) is not None:
                    accumulator["sum"] += record["_records"] or 0
            elif method == "avg":
                accumulator["sum"] += record[f"m{index}"] or 0
                accumulator["count"] += record[f"n{index}"] or 0
            elif method in {"min", "max"}:
                value = record[f"m{index}"]
                if value is not None:
                    previous = accumulator["value"]
                    accumulator["value"] = (
                        value
                        if previous is None
                        else (min(previous, value) if method == "min" else max(previous, value))
                    )
            else:
                accumulator["sum"] += record[f"m{index}"] or 0
    result: list[Record] = []
    for key, accumulators in states.items():
        values: list[int | float] = []
        for accumulator in accumulators:
            if method == "distinct":
                values.append(len(accumulator["distinct"]))
            elif percentile is not None:
                values.append(_weighted_percentile(accumulator["frequencies"], percentile))
            elif method == "avg":
                values.append(accumulator["sum"] / accumulator["count"] if accumulator["count"] else 0)
            elif method in {"min", "max"}:
                values.append(accumulator["value"] or 0)
            else:
                values.append(accumulator["sum"])
        result.append({**dict(key), "_result_": sum(values)})
    return result


def query_virtual_grouped_values(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int | None,
    end_time: int | None,
    fields: list[str],
    method: str,
    group_by: list[str] | None = None,
    interval: int | None = None,
) -> list[Record]:
    """保留其他维度与时间桶，在最终虚拟值上计算统计指标。"""
    group_by = group_by or []
    dimensions: list[str] = [field for field in group_by if field != owner.TIME_BUCKET_FIELD]
    result: list[Record] = []
    for start, end, bucket in _time_windows(owner, start_time, end_time, owner.TIME_BUCKET_FIELD in group_by, interval):
        records: list[Record] = _query_grouped_window(owner, queries, start, end, fields, method.lower(), dimensions)
        if bucket is not None:
            records = [{**record, "_time_": bucket} for record in records]
        result.extend(records)
    return result
