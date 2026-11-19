"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import Counter, defaultdict
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from rest_framework.exceptions import ValidationError

from bkmonitor.data_source.data_source import BkRumDataSource
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils.base import get_bar_interval_number
from bkmonitor.utils.time_tools import time_interval_align
from rum_web.virtual_fields import VirtualField

if TYPE_CHECKING:
    from rum_web.handlers.query.base import BaseRumQuery


BUCKET_PAGE_SIZE = 1000
Record = dict[str, Any]


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
        after: Record = {}
        while True:
            records: list[Record] = queryset.dsl_search_after(after, missing_bucket=True).raw_data
            if not records:
                break
            next_after: Record | None = records[-1].get("_after_key_")
            yield from records
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
        if cumulative <= lower_rank:
            continue
        if lower_value is None:
            lower_value = value
        if upper_rank < cumulative:
            return lower_value + (value - lower_value) * remainder / 100
    raise ValueError("百分位必须在 0 至 100 之间")


def _query_grouped_window(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int,
    end_time: int,
    field: str,
    method: str,
    dimensions: list[str],
) -> list[Record]:
    virtual_fields = owner.virtual_fields
    virtual = virtual_fields.get(field)
    if virtual and method not in {"count", "distinct"}:
        raise ValidationError("虚拟字段是离散维度，仅支持 count 和 distinct 聚合")
    percentile = int(method[2:]) if method.startswith("cp") else None
    raw_fields = list(dimensions)
    if virtual or method == "distinct" or percentile is not None:
        raw_fields.append(field)
        metrics = [{"field": "_index", "method": "COUNT", "alias": "_records"}]
    elif method == "avg":
        metrics = [{"field": field, "method": op, "alias": alias} for op, alias in (("SUM", "total"), ("COUNT", "n"))]
    else:
        metrics = [{"field": field, "method": method, "alias": "total"}]

    members = list(
        dict.fromkeys(
            member
            for name in raw_fields
            for member in (virtual_fields[name].field_names if name in virtual_fields else [name])
        )
    )
    # 每个最终分组仅维护本次指标所需的状态。均值按样本数加权，百分位按样本频数合并。
    totals: dict[tuple, int | float | None] = {}
    weights = defaultdict(int)
    frequencies = defaultdict(Counter)
    for row in iter_joint_buckets(owner, queries, start_time, end_time, members, metrics):
        key = tuple(virtual_fields[d].format(row) if d in virtual_fields else row.get(d) for d in dimensions)
        previous = totals.setdefault(key, None)
        if method == "distinct" or percentile is not None:
            value = virtual.format(row) if virtual else row.get(field)
            if value is not None:
                frequencies[key][value] += row["_records"]
        elif method in {"min", "max"}:
            value = row["total"]
            if value is not None:
                compare = min if method == "min" else max
                totals[key] = value if previous is None else compare(previous, value)
        elif virtual:
            if virtual.format(row) is not None:
                totals[key] = (previous or 0) + row["_records"]
        else:
            totals[key] = (previous or 0) + (row["total"] or 0)
            if method == "avg":
                weights[key] += row["n"] or 0

    result: list[Record] = []
    for key, total in totals.items():
        value = total or 0
        if method == "distinct":
            value = len(frequencies[key])
        elif percentile is not None:
            value = _weighted_percentile(frequencies[key], percentile)
        elif method == "avg" and weights[key]:
            value /= weights[key]
        result.append({**dict(zip(dimensions, key, strict=True)), "_result_": value})
    return result


def query_virtual_grouped_values(
    owner: "BaseRumQuery",
    queries: list[QueryConfigBuilder],
    start_time: int | None,
    end_time: int | None,
    field: str,
    method: str,
    group_by: list[str] | None = None,
    interval: int | None = None,
) -> list[Record]:
    """保留其他维度与时间桶，在最终虚拟值上计算统计指标。"""
    group_by = group_by or []
    dimensions: list[str] = [dim for dim in group_by if dim != owner.TIME_BUCKET_FIELD]
    result: list[Record] = []
    for start, end, bucket in _time_windows(owner, start_time, end_time, owner.TIME_BUCKET_FIELD in group_by, interval):
        records: list[Record] = _query_grouped_window(owner, queries, start, end, field, method.lower(), dimensions)
        if bucket is not None:
            records = [{**record, "_time_": bucket} for record in records]
        result.extend(records)
    return result
