import logging

from blueapps.utils import get_request as _get_request
from django.utils.deprecation import MiddlewareMixin

from apps.log_audit.instance import push_event
from apps.log_extract.handlers.local import local
from apps.utils.common import fetch_biz_id_from_request

logger = logging.getLogger(__name__)


class RequestProvider(MiddlewareMixin):
    """
    @summary: request事件接收者
    """

    def process_request(self, request):
        local.current_request = _get_request()
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        biz_id = fetch_biz_id_from_request(request, view_kwargs)
        request.biz_id = biz_id

    def process_response(self, request, response):
        push_event(request)
        local.clear()
        response["X-Content-Type-Options"] = "nosniff"
        return response
