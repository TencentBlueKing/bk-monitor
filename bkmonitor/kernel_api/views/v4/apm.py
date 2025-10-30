from apm_web.meta.views import ApplicationViewSet
from apm_web.service.views import ServiceViewSet
from apm_web.trace.views import TraceQueryViewSet


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
