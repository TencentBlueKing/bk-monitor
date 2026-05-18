from apm_web.meta.views import ApplicationViewSet
from apm_web.service.views import ServiceViewSet
from apm_web.trace.views import TraceQueryViewSet
from apm_web.event.views import EventViewSet
from apm_web.metric.views import MetricViewSet
from apm_web.profile.views import ProfileQueryViewSet
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.apm import (
    GetApmSearchFiltersResource,
    GetProfileApplicationServiceResource,
    GetProfileLabelResource,
    GetProfileTypeResource,
    ListApmApplicationResource,
    ListApmSpanResource,
    QueryApmSpanDetailResource,
    QueryApmTraceDetailResource,
    QueryGraphProfileResource,
)


class ApmProfileQueryWebViewSet(ProfileQueryViewSet):
    """
    APM Profile 相关 API
    """


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


class ServiceWebViewSet(ServiceViewSet):
    """
    应用下服务相关API
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
        # ---- Profiling 子工作流 ----
        ResourceRoute("POST", GetProfileApplicationServiceResource, endpoint="get_profile_application_service"),
        ResourceRoute("POST", GetProfileTypeResource, endpoint="get_profile_type"),
        ResourceRoute("POST", GetProfileLabelResource, endpoint="get_profile_label"),
        ResourceRoute("POST", QueryGraphProfileResource, endpoint="query_graph_profile"),
    ]
