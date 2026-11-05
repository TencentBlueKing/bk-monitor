"""MCP 失败响应：可公开的失败原因写进 message，未知异常只暴露类型和日志检索 ID。"""

import requests
from rest_framework.exceptions import APIException, ValidationError

from core.errors import Error
from core.errors.api import BKAPIError

MAX_MESSAGE_LENGTH = 1024
VALIDATION_MESSAGE = "MCP request validation failed"
REJECTED_MESSAGE = "MCP permission or execution rejected"
UNEXPECTED_MESSAGE = "MCP request failed; no data returned"


def _flatten_detail(detail, path=""):
    prefix = f"{path}: " if path else ""
    if isinstance(detail, dict):
        # result_too_large 等结构化错误自带完整说明，直接使用说明文本。
        if isinstance(detail.get("message"), str):
            return [f"{prefix}{detail['message']}"]
        parts = []
        for key, value in detail.items():
            parts.extend(_flatten_detail(value, f"{path}.{key}" if path else str(key)))
        return parts
    if isinstance(detail, list | tuple):
        parts = []
        for item in detail:
            parts.extend(_flatten_detail(item, path))
        return parts
    return [f"{prefix}{detail}"]


def _truncate(message):
    return message if len(message) <= MAX_MESSAGE_LENGTH else f"{message[:MAX_MESSAGE_LENGTH]}... [truncated]"


def _reference_text(refs):
    return " ".join(f"{key}={value}" for key, value in refs.items())


def _api_exception(exc):
    if isinstance(exc, ValidationError):
        status = "invalid_params"
        message = f"{VALIDATION_MESSAGE}: {'; '.join(_flatten_detail(exc.detail))}"
    else:
        status = "permission_denied" if exc.status_code == 403 else "error"
        # 权限拒绝的结构化状态保留在 data；字符串详情（如鉴权服务不可用）直接说明原因。
        message = f"{REJECTED_MESSAGE}: {exc.detail}" if isinstance(exc.detail, str) else REJECTED_MESSAGE
    return exc.status_code, status, _truncate(message), exc.detail


def _platform_error(exc, refs):
    # 部分历史异常沿用 200/204 + result=False 的 Web 约定，MCP 上必须仍是失败状态码。
    status_code = exc.status_code if exc.status_code >= 400 else 500
    status = {400: "invalid_params", 403: "permission_denied"}.get(status_code, "error")
    data = {"error_type": type(exc).__name__, "error_code": exc.code, **refs}
    # 只透传自有结构化字段；BKAPIError 等会把上游原始响应放进 data，不能整体返回。
    for source, keys in (
        (getattr(exc, "data", None), ("error_code", "next_actions", "apply_url")),
        (getattr(exc, "extra", None), ("permission",)),
    ):
        if isinstance(source, dict):
            data.update({key: source[key] for key in keys if key in source})
    message = str(exc.message)
    if isinstance(exc, BKAPIError):
        # 上游接口错误只保留“系统 + 上游消息”，去掉消息模板中的内部请求 URL。
        details = exc.error_details or {}
        message = f"{details.get('overview') or ''}{details.get('detail') or ''}" or message
    return status_code, status, _truncate(message), data


def _unexpected_error(exc, refs):
    error_type = type(exc).__name__
    data = {"error_type": error_type, **refs}
    reference = _reference_text(refs)
    if isinstance(exc, requests.Timeout):
        return 504, "error", f"MCP upstream request timed out ({error_type}); retry later. {reference}".strip(), data
    if isinstance(exc, requests.ConnectionError):
        return 502, "error", f"MCP upstream connection failed ({error_type}); retry later. {reference}".strip(), data
    # 未知异常文本可能包含上游原文或内部地址，只返回类型和可检索日志的 ID。
    message = f"{UNEXPECTED_MESSAGE} ({error_type}); contact the administrator with {reference or 'the request time'}"
    return 503, "error", message, data


def build_mcp_error(exc, trace_id="", request_id=""):
    """返回 (status_code, metric_status, message, data)，调用方负责渲染响应和记录指标。

    trace_id 对应 MCP_AUTH 日志，request_id 对应 API 网关请求；只返回非空值。
    """
    refs = {key: value for key, value in (("trace_id", trace_id), ("request_id", request_id)) if value}
    if isinstance(exc, APIException):
        return _api_exception(exc)
    if isinstance(exc, Error):
        return _platform_error(exc, refs)
    return _unexpected_error(exc, refs)
