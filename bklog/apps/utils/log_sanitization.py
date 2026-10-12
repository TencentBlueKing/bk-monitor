import re

REDACTED_HEADER_VALUE = "[REDACTED]"
_SENSITIVE_HEADER_NAME = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|jwt|ticket|api[-_]?key|credential)", re.IGNORECASE
)


def sanitize_header_value(name, value):
    """Return a header value safe for diagnostic logging without mutating the request."""
    if _SENSITIVE_HEADER_NAME.search(str(name)):
        return REDACTED_HEADER_VALUE
    return value


def sanitize_headers(headers):
    """Copy request headers while redacting credentials by header name."""
    if not headers:
        return {}
    return {name: sanitize_header_value(name, value) for name, value in headers.items()}
