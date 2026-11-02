"""Request validation and response limits for explicitly opted-in MCP facades."""

import gzip
import json
from contextlib import ExitStack

from django.conf import settings
from django.db import models
from django.http.response import HttpResponseBase
from requests.exceptions import ContentDecodingError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from bkmonitor.utils.common_utils import DatetimeEncoder
from bkmonitor.utils.request import get_request
from core.drf_resource import Resource

DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


def is_mcp_request():
    request = get_request(peaceful=True)
    if request is None:
        return False
    meta = request.META
    source = meta.get("HTTP_X_BK_REQUEST_SOURCE")
    return bool(
        meta.get("HTTP_X_BKAPI_MCP_SERVER_NAME")
        or (source and source == getattr(settings, "AIDEV_AGENT_MCP_REQUEST_HEADER_VALUE", "bkm-mcp-client"))
        or getattr(request, "native_mcp_tool", None)
        or getattr(request, "mcp_usage_tool", None)
        or getattr(request, "mcp_usage_event_id", None)
    )


def get_max_response_bytes():
    # Keep a static default AND an ADVANCED_OPTIONS entry: DynamicSettings first
    # reads the static attribute, then consults GlobalConfig. Never cache here.
    value = getattr(settings, "MCP_MAX_RESPONSE_BYTES", DEFAULT_MAX_RESPONSE_BYTES)
    if type(value) is not int or value <= 0:
        raise ValueError("MCP_MAX_RESPONSE_BYTES must be a positive integer")
    return value


def result_too_large(max_bytes):
    raise ValidationError(
        {
            "reason": "result_too_large",
            "max_response_bytes": max_bytes,
            "message": "查询结果过大，请缩短时间范围、增加筛选条件或减少返回字段；指标查询可增大 step。请勿原样重试。",
        },
        code="result_too_large",
    )


def check_json_size(data, max_bytes):
    size = 0
    # Use the actual API encoder's default separators / ASCII escaping.
    for chunk in DatetimeEncoder(ensure_ascii=True).iterencode(data):
        size += len(chunk.encode("utf-8"))
        if size > max_bytes:
            result_too_large(max_bytes)


class MCPResource(Resource):
    """Validation errors and output guard for explicitly opted-in MCP facades.

    validate_response_data runs inside the original Resource exception / metrics
    handling. Ordinary requests execute the original validation unchanged.
    """

    def validate_request_data(self, request_data):
        if (
            not is_mcp_request()
            or not self.RequestSerializer
            or isinstance(request_data, models.Model | models.QuerySet)
        ):
            return super().validate_request_data(request_data)
        # Resource wraps serializer errors in CustomException, which becomes an
        # unexpected 503 at the MCP boundary. Preserve DRF's structured 400 here.
        self._request_serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
        self._request_serializer.is_valid(raise_exception=True)
        return self._request_serializer.validated_data

    def validate_response_data(self, response_data):
        result = super().validate_response_data(response_data)
        if not is_mcp_request() or isinstance(result, HttpResponseBase):
            return result
        # Reuse (but never change) our API renderer's envelope and field conversion.
        from kernel_api.adapters import ApiRenderer

        request = get_request(peaceful=True)
        data = result.copy() if isinstance(result, dict) else result
        native_tool = getattr(request, "native_mcp_tool", None)
        if native_tool and getattr(request, "unified_mcp_operation", None) == "execute_tool":
            # The native Unified fast path adds this wrapper AFTER Resource
            # validation. Include it without modifying that original middleware.
            data = {"status": "success", "tool_name": native_tool, "data": data, "meta": {"truncated": False}}
        formatted = ApiRenderer().get_result(
            data,
            renderer_context={"request": request, "response": Response()},
        )
        check_json_size(formatted, get_max_response_bytes())
        return result


def read_bounded_json(response, max_bytes):
    """Read at most the decoded byte budget + one byte before JSON parsing.

    The caller must request stream=True and close the Response in all cases.
    gzip.GzipFile also bounds decompression allocations, unlike eager decoding.
    """
    encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
    if encoding in ("", "identity"):
        try:
            declared_size = int(response.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            declared_size = 0
        if declared_size > max_bytes:
            result_too_large(max_bytes)
    elif encoding not in ("gzip", "x-gzip"):
        raise ContentDecodingError("MCP upstream response must use gzip or identity Content-Encoding")

    response.raw.decode_content = False
    body = bytearray()
    with ExitStack() as stack:
        reader = response.raw
        if encoding in ("gzip", "x-gzip"):
            reader = stack.enter_context(gzip.GzipFile(fileobj=response.raw))
        while True:
            chunk = reader.read(min(64 * 1024, max_bytes - len(body) + 1))
            if not chunk:
                break
            if len(body) + len(chunk) > max_bytes:
                result_too_large(max_bytes)
            body.extend(chunk)
    if response.status_code not in (200, 204):
        return None, body.decode(response.encoding or "utf-8", errors="replace")
    return json.loads(body), None
