from apm_web.meta.views import ApplicationViewSet
from apm_web.trace.views import TraceQueryViewSet
from apm_web.event.views import EventViewSet
from apm_web.metric.views import MetricViewSet
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.apm import (
    ListApmApplicationResource,
    GetApmSearchFiltersResource,
    ListApmSpanResource,
    QueryApmTraceDetailResource,
    QueryApmSpanDetailResource,
)


class ApmMetricWebViewSet(MetricViewSet):
    """
    APM 指标相关 API
    """


class ApmEventWebViewSet(EventViewSet):
    """
    APM 事件相关 API
    """


class ApplicationWebViewSet(ApplicationViewSet):
    """
    应用相关API
    """


class TraceQueryWebViewSet(TraceQueryViewSet):
    """
    trace 检索相关API
    """


class ApmMcpViewSet(ResourceViewSet):
    """
    APM MCP 相关API
    """

    resource_routes = [
        ResourceRoute("GET", ListApmApplicationResource, endpoint="list_apm_application"),
        ResourceRoute("GET", GetApmSearchFiltersResource, endpoint="get_apm_search_filters"),
        ResourceRoute("POST", ListApmSpanResource, endpoint="list_apm_span"),
        ResourceRoute("POST", QueryApmTraceDetailResource, endpoint="query_apm_trace_detail"),
        ResourceRoute("POST", QueryApmSpanDetailResource, endpoint="query_apm_span_detail"),
    ]
