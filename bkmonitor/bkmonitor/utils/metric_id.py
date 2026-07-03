"""
Metric ID query helpers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.db.models import Q

from constants.data_source import DataSourceLabel, DataTypeLabel


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
