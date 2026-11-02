"""MCP-only bounded PromQL adapter; the original UQ / Grafana APIs stay intact."""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source import PrometheusTimeSeriesDataSource
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation, time_interval_align
from kernel_api.resource.mcp_response import get_max_response_bytes
from kernel_api.resource.mcp_uq import query_uq
from monitor_web.grafana.resources.unify_query import (
    AddNullDataProcessor,
    GraphPromqlQueryResource,
    GraphUnifyQueryResource,
    HeatMapProcessor,
    QueryTypeProcessor,
)
from monitor_web.grafana.utils import get_cookies_filter


def query_promql(params, max_bytes):
    """Use the shared MCP-only reader for the existing range-query adapter."""
    return query_uq("query_data_by_promql", params, max_bytes=max_bytes)


def execute_range_query(params):
    """Use original Grafana validation and processors, replacing only MCP I/O."""
    graph = GraphPromqlQueryResource()
    params = graph.validate_request_data(dict(params))
    interval = -parse_time_compare_abbreviation(params["step"])
    if interval <= 0:
        raise ValidationError({"step": "step must be greater than zero"})
    if params["type"] == "instant":
        params["start_time"] = params["end_time"] - 5 * interval
    if not params["promql"]:
        return {"metrics": [], "series": []}
    params["promql"] = graph.remove_all_conditions(params["promql"])
    start_time, end_time = params["start_time"], params["end_time"]
    if params["time_alignment"]:
        start_time = time_interval_align(start_time, interval)
        end_time = time_interval_align(end_time, interval)
    request_params = dict(
        promql=params["promql"],
        match=PrometheusTimeSeriesDataSource.filter_dict_to_promql_match(get_cookies_filter()),
        start=start_time,
        end=end_time,
        step=params["step"],
        bk_biz_ids=[params["bk_biz_id"]],
        timezone=timezone.get_current_timezone_name(),
        down_sample_range=params["down_sample_range"],
        reference=not params["time_alignment"],
    )
    result = query_promql(request_params, get_max_response_bytes())["series"] or []
    series = graph.format_data(result)
    series = HeatMapProcessor.process_formatted_data(params, series)
    series = QueryTypeProcessor.process_formatted_data(params, series)
    series = AddNullDataProcessor.process_formatted_data(params, series)
    series = GraphUnifyQueryResource.translate_dimensions(params, series)
    return {"metrics": [], "series": series}
