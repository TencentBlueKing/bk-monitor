from typing import Any

from django.db.models import Q
from opentelemetry.trace import StatusCode

from apm.core.handlers.query.origin_trace_query import OriginTraceQuery
from apm.core.handlers.query.trace_query import TraceQuery
from bkmonitor.data_source.utils.apm import LogicSupportOperator
from constants.apm import OtlpKey


def test_origin_trace_query_builds_error_logic_filter_from_span_status() -> None:
    filters: list[dict[str, Any]] = [{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}]

    query_filter: Q = OriginTraceQuery._build_filters(filters)

    assert query_filter == Q(**{OtlpKey.STATUS_CODE: StatusCode.ERROR.value})


def test_precalculation_trace_query_builds_error_logic_filter_from_error_count() -> None:
    filters: list[dict[str, Any]] = [{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}]

    query_filter: Q = TraceQuery._build_filters(filters)

    assert query_filter == Q(error_count__neq=0)
