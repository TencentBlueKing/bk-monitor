"""为 IAM 异常生成有长度限制且已脱敏的诊断摘要。"""

from __future__ import annotations

import re
from typing import Any


MAX_ERROR_SUMMARY_LENGTH = 256
_AUTH_HEADER_PATTERN = re.compile(
    r"(?i)(?:x-bkapi-authorization|authorization)\s*[:=]\s*(?:(?:bearer|basic)\s+)?[^,;\s]+"
)
_SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:bk_app_secret|app_secret|secret|token|password)\b[\"']?\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^,;\s}\]]+)"
)
_EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_LONG_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{11,}(?!\d)")
_OPAQUE_CREDENTIAL_PATTERN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9_+/=.~-]{32,}(?![A-Za-z0-9])")


def sanitize_error_summary(value: Any, *, max_length: int = MAX_ERROR_SUMMARY_LENGTH) -> str:
    """生成不包含凭证和常见个人标识的单行诊断摘要。"""

    summary = " ".join(str(value or "").split())
    summary = _AUTH_HEADER_PATTERN.sub("authorization=<redacted>", summary)
    summary = _SENSITIVE_ASSIGNMENT_PATTERN.sub("credential=<redacted>", summary)
    summary = _EMAIL_PATTERN.sub("<redacted-email>", summary)
    summary = _LONG_NUMBER_PATTERN.sub("<redacted-number>", summary)
    summary = _OPAQUE_CREDENTIAL_PATTERN.sub("<redacted-value>", summary)
    return summary[: max(0, max_length)]
