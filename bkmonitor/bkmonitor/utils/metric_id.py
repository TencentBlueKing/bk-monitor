"""
Metric ID query helpers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy
from functools import lru_cache
from typing import Any

from django.db.models import Q

from constants.data_source import DataSourceLabel, DataTypeLabel

# 标准 metric_id 的首段是 data_source_label，与 PromQL 里的数据源前缀不同名，需要显式映射。
# 取值与 QueryConfigToPromql 使用的映射保持一致。
PROMQL_DATA_SOURCE_PREFIXES = {
    DataSourceLabel.BK_MONITOR_COLLECTOR: "bkmonitor",
    DataSourceLabel.CUSTOM: "custom",
    DataSourceLabel.BK_DATA: "bkdata",
    DataSourceLabel.BK_LOG_SEARCH: "bklog",
}

# PromQL 指标名由字母数字下划线分段、段间以冒号连接，至少两段
_PROMQL_METRIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+(:[A-Za-z0-9_]+)+$")


def build_promql_metric_names(metric_id: str) -> set[str]:
    """
    把标准 metric_id 换算成它在 PromQL 中可能出现的指标名。

    标准 metric_id 形如 bk_monitor.system.io.util，即
    <data_source_label>.<result_table_id>.<metric_field>；PromQL 指标名形如
    bkmonitor:system:io:util。换算无需区分 result_table_id 与 metric_field 的边界：
    首段按映射换成 PromQL 数据源前缀，其余各段的 "." 换成 ":" 即可，因此 data_label
    两段式写法同样覆盖。

    同时返回省略数据源前缀的写法（system:io:util），PromQL 允许该形式。
    无法换算时返回空集合，由调用方决定兜底行为。
    """
    if not metric_id:
        return set()

    data_source_label, _, rest = metric_id.partition(".")
    prefix = PROMQL_DATA_SOURCE_PREFIXES.get(data_source_label)
    if not prefix or not rest:
        return set()

    bare_name = rest.replace(".", ":")
    if not _PROMQL_METRIC_NAME_PATTERN.match(bare_name):
        return set()

    return {f"{prefix}:{bare_name}", bare_name}


@lru_cache(maxsize=512)
def _compile_promql_metric_patterns(metric_ids: tuple[str, ...]) -> tuple[re.Pattern, ...]:
    names: set[str] = set()
    for metric_id in metric_ids:
        names |= build_promql_metric_names(metric_id)

    # token 边界不允许指标名的合法字符（含冒号），否则省略前缀的候选会命中其它数据源的
    # 同名指标——bkdata:system:io:util 不应被 system:io:util 命中。
    return tuple(re.compile(rf"(?<![A-Za-z0-9_:]){re.escape(name)}(?![A-Za-z0-9_:])") for name in sorted(names))


def build_promql_metric_patterns(metric_ids: Iterable[str]) -> tuple[re.Pattern, ...]:
    """把标准 metric_id 编译成可在 PromQL 表达式中搜索的模式，结果按取值缓存。"""
    return _compile_promql_metric_patterns(tuple(sorted({str(metric_id) for metric_id in metric_ids if metric_id})))


def build_metric_check_key(bk_tenant_id: str, bk_biz_id: int, metric_id: str) -> tuple[str, int, str]:
    """Build the in-memory cache key for metric existence checks."""
    return bk_tenant_id, bk_biz_id, metric_id


def build_metric_id_filter_queries(metric_params: dict[str, Any]) -> list[Q]:
    """
    Build MetricListCache queries for a parsed metric_id.

    Time series metrics may be exposed by data_label in PromQL-style names, for
    example custom.system_base.xxx or bk_monitor.system_base.xxx. The canonical
    strategy metric_id still uses the physical result_table_id, but cache
    lookups should accept the data_label alias when exact result_table_id lookup
    misses.
    """
    if not metric_params:
        return []

    normalized_params = deepcopy(metric_params)
    if "index_set_id" in normalized_params:
        normalized_params["related_id"] = normalized_params.pop("index_set_id")

    queries = [Q(**normalized_params)]

    data_source_label = normalized_params.get("data_source_label")
    if (
        data_source_label in [DataSourceLabel.CUSTOM, DataSourceLabel.BK_MONITOR_COLLECTOR]
        and normalized_params.get("data_type_label") == DataTypeLabel.TIME_SERIES
        and normalized_params.get("result_table_id")
        and normalized_params.get("metric_field")
    ):
        queries.append(
            Q(
                data_source_label=data_source_label,
                data_type_label=DataTypeLabel.TIME_SERIES,
                data_label=normalized_params["result_table_id"],
                metric_field=normalized_params["metric_field"],
            )
        )

    return queries
