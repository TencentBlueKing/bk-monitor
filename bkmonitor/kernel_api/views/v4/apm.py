from apm_web.meta.views import ApplicationViewSet
from apm_web.trace.views import TraceQueryViewSet


class ApplicationWebViewSet(ApplicationViewSet):
    """
    应用相关API
    """


class TraceQueryWebViewSet(TraceQueryViewSet):
    """
    trace 检索相关API
    """
