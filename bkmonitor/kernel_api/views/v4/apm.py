from apm_web.meta.views import ApplicationViewSet
from apm_web.trace.views import TraceQueryViewSet
from apm_web.metric.views import MetricViewSet


class ApmMetricWebViewSet(MetricViewSet):
    """
    APM 指标相关 API
    """


class ApplicationWebViewSet(ApplicationViewSet):
    """
    应用相关API
    """


class TraceQueryWebViewSet(TraceQueryViewSet):
    """
    trace 检索相关API
    """
