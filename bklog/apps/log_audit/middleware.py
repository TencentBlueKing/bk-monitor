import logging

from blueapps.utils import get_request as _get_request
from django.utils.deprecation import MiddlewareMixin

from apps.log_audit.instance import push_event
from apps.log_extract.handlers.local import local

logger = logging.getLogger(__name__)


class RequestProvider(MiddlewareMixin):
    """
    @summary: request事件接收者
    """

    def process_request(self, request):
        local.current_request = _get_request()
        return None

    def process_response(self, request, response):
        push_event(request)
        local.clear()
        response["X-Content-Type-Options"] = "nosniff"
        return response
