import base64
import binascii
import json
import math
import re
import time
from datetime import datetime, timezone as datetime_timezone

import arrow
from django.conf import settings
from django.db.models import Q, Subquery
from django.utils import timezone

from apps.api.base import get_request_id
from apps.exceptions import ApiRequestError, ApiResultError, ValidationError
from apps.exceptions import PermissionError as BklogPermissionError
from apps.log_clustering.handlers.aiops.config import get_online_clustering_config
from apps.log_search.models import Space
from apps.utils.local import get_request_tenant_id


DEFAULT_SAMPLE_LIMIT = 10
MAX_SAMPLE_LIMIT = 20
MAX_SAMPLE_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 10
FORBIDDEN_IDENTITY_PARAMS = {
    "bk_username",
    "operator",
    "bk_tenant_id",
    "bkdata_authentication_method",
    "no_request",
}
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|secret|token|authorization|cookie|credential|access[_-]?key|api[_-]?key|app[_-]?key"
    r"|private[_-]?key|webhook|dsn|salt|cipher)",
    re.IGNORECASE,
)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<key_quote>[\"']?)(?P<key>\b(?:password|passwd|secret|token|authorization|cookie|credential"
    r"|(?:access|refresh|bearer|id)[_-]?token|access[_-]?key|api[_-]?key|app[_-]?secret"
    r"|private[_-]?key|webhook|dsn|broker|account|salt|cipher))(?P=key_quote)"
    r"(?P<separator>\s*[:=]\s*)(?:(?:bearer|basic)\s+)?"
    r"(?P<value>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;}]+)",
    re.IGNORECASE,
)
AUTH_SCHEME_PATTERN = re.compile(r"\b(bearer|basic)\s+[^\s,;]+", re.IGNORECASE)
CREDENTIAL_URL_PATTERN = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
MAX_UPSTREAM_MESSAGE_LENGTH = 1024
EVENT_TIME_PRIORITY = {
    "dteventtimestamp": 0,
    "dteventtime": 1,
    "eventtimestamp": 2,
    "eventtime": 3,
    "event_time": 4,
    "starttime": 5,
    "timestamp": 6,
    "utctime": 7,
    "localtime": 8,
    "time": 9,
}


def reject_identity_params(params):
    forbidden = sorted(FORBIDDEN_IDENTITY_PARAMS.intersection(params))
    if forbidden:
        raise ValidationError("identity parameters are managed by bklog: {}".format(", ".join(forbidden)))


def require_request_tenant_id():
    """Return the trusted request tenant or fail closed for Resource reads."""

    tenant_id = get_request_tenant_id()
    if not tenant_id:
        raise BklogPermissionError("Resource Call request tenant is required")
    return tenant_id


def request_tenant_spaces():
    """Build the canonical active-space scope for the trusted request tenant."""

    return Space.origin_objects.filter(bk_tenant_id=require_request_tenant_id())


def scope_biz_queryset(queryset, field_name="bk_biz_id", *, include_global=False):
    """Restrict a queryset business field to the current request tenant."""

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return queryset
    tenant_biz_ids = request_tenant_spaces().values("bk_biz_id")
    condition = Q(**{f"{field_name}__in": Subquery(tenant_biz_ids)})
    if include_global:
        condition |= Q(**{field_name: 0})
    return queryset.filter(condition)


def scope_space_queryset(queryset, field_name="space_uid"):
    """Restrict a queryset space field to the current request tenant."""

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return queryset
    tenant_space_uids = request_tenant_spaces().values("space_uid")
    return queryset.filter(**{f"{field_name}__in": Subquery(tenant_space_uids)})


def require_biz_in_request_tenant(bk_biz_id, *, allow_global=False):
    """Reject caller-selected businesses that are outside the request tenant."""

    try:
        normalized_biz_id = int(bk_biz_id)
    except (TypeError, ValueError) as error:
        raise ValidationError("bk_biz_id must be an integer") from error
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return normalized_biz_id
    if allow_global and normalized_biz_id == 0:
        return normalized_biz_id
    if not request_tenant_spaces().filter(bk_biz_id=normalized_biz_id).exists():
        raise BklogPermissionError("business does not belong to the current Resource Call tenant")
    return normalized_biz_id


def require_positive_int(params, key):
    value = params.get(key)
    if value in (None, ""):
        raise ValidationError(f"{key} is required")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer")
    if value < 1:
        raise ValidationError(f"{key} must be positive")
    return value


def require_nonzero_int(params, key):
    value = params.get(key)
    if value in (None, ""):
        raise ValidationError(f"{key} is required")
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer")
    if value == 0:
        raise ValidationError(f"{key} must not be zero")
    return value


def optional_positive_int(value, key, default=None, maximum=None):
    if value in (None, ""):
        return default
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be an integer")
    if value < 1:
        raise ValidationError(f"{key} must be positive")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{key} must be less than or equal to {maximum}")
    return value


def build_bkdata_context(bk_biz_id):
    require_biz_in_request_tenant(bk_biz_id)
    config = get_online_clustering_config(bk_biz_id)
    bk_username = config.get("bk_username")
    if not bk_username:
        raise ValidationError(f"bkdata username is not configured for bk_biz_id={bk_biz_id}")
    bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id, is_need_default=False)
    if not bk_tenant_id:
        raise ValidationError(f"bkdata tenant is not configured for bk_biz_id={bk_biz_id}")
    return {
        "bk_biz_id": bk_biz_id,
        "bk_username": bk_username,
        "operator": bk_username,
        "bkdata_authentication_method": "user",
        "no_request": True,
        "bk_tenant_id": bk_tenant_id,
    }


def call_bkdata(api, params, *, not_found_codes=None):
    started = time.monotonic()
    try:
        bk_tenant_id = params.pop("bk_tenant_id", "")
        data = api(
            params=params,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            request_cookies=False,
            bk_tenant_id=bk_tenant_id,
        )
        return probe_success(data, started)
    except (ApiResultError, ApiRequestError) as error:
        return probe_failure(error, started, not_found_codes=not_found_codes)
    except Exception as error:  # The probe must not make sibling evidence unavailable.
        return probe_failure(error, started, not_found_codes=not_found_codes)


def probe_success(data, started=None, warnings=None):
    empty = data in (None, [], {})
    return {
        "probe_status": "success",
        "exists": True,
        "empty": empty,
        "observed_at": timezone.now().isoformat(),
        "duration_ms": _duration_ms(started),
        "data": data,
        "error": None,
        "warnings": warnings or [],
    }


def probe_skipped(code, message):
    return {
        "probe_status": "skipped",
        "exists": None,
        "empty": None,
        "observed_at": timezone.now().isoformat(),
        "duration_ms": 0,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "upstream_code": None,
            "upstream_message": None,
            "request_id": get_request_id(),
            "retryable": False,
        },
        "warnings": [],
    }


def probe_failure(error, started=None, not_found_codes=None):
    upstream_code = getattr(error, "code", None)
    raw_upstream_message = getattr(error, "message", None) or str(error)
    normalized_code, retryable = _normalize_error(upstream_code, raw_upstream_message, not_found_codes or set())
    upstream_message = sanitize_sensitive_text(raw_upstream_message)
    exists = False if normalized_code == "RESOURCE_NOT_FOUND" else None
    return {
        "probe_status": "failed",
        "exists": exists,
        "empty": None,
        "observed_at": timezone.now().isoformat(),
        "duration_ms": _duration_ms(started),
        "data": None,
        "error": {
            "code": normalized_code,
            "message": _error_message(normalized_code),
            "upstream_code": str(upstream_code) if upstream_code is not None else None,
            "upstream_message": upstream_message,
            "request_id": getattr(error, "request_id", None) or get_request_id(),
            "retryable": retryable,
        },
        "warnings": [],
    }


def sanitize_sensitive_text(value, maximum=MAX_UPSTREAM_MESSAGE_LENGTH):
    message = CREDENTIAL_URL_PATTERN.sub("://***:***@", str(value))
    message = SENSITIVE_ASSIGNMENT_PATTERN.sub(_redact_assignment, message)
    message = AUTH_SCHEME_PATTERN.sub(lambda match: f"{match.group(1)} ***", message)
    return message if maximum is None else message[:maximum]


def _redact_assignment(match):
    key_quote = match.group("key_quote") or ""
    value = match.group("value")
    value_quote = value[0] if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" else ""
    return f"{key_quote}{match.group('key')}{key_quote}{match.group('separator')}{value_quote}***{value_quote}"


def sanitize_json(value, *, max_bytes=None, redact_text=False):
    sanitized = _sanitize(value, redact_text=redact_text)
    if max_bytes is None:
        return sanitized
    return limit_json_value(sanitized, max_bytes)


def limit_json_value(value, max_bytes=MAX_SAMPLE_BYTES):
    encoded = _json_bytes(value)
    if len(encoded) <= max_bytes:
        return {
            "value": value,
            "truncated": False,
            "original_size_bytes": len(encoded),
            "returned_size_bytes": len(encoded),
        }

    if isinstance(value, str):
        limited_value = _truncate_utf8(value, max(0, max_bytes - 64))
    else:
        limited_value = _truncate_utf8(encoded.decode("utf-8", errors="replace"), max(0, max_bytes - 64))
    return {
        "value": limited_value,
        "truncated": True,
        "original_size_bytes": len(encoded),
        "returned_size_bytes": len(limited_value.encode("utf-8")),
    }


def serialize_tail_rows(rows, sample_limit, *, decode_wrapped=False):
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        rows = [rows]
    selected_rows = rows[:sample_limit]
    samples = []
    time_rows = []
    for row in selected_rows:
        limited = limit_json_value(sanitize_json(row, redact_text=True))
        sample = {"raw": limited}
        time_row = row
        if decode_wrapped and isinstance(row, dict):
            decoded = decode_raw_data_row(row, max_bytes=max(0, MAX_SAMPLE_BYTES - limited["returned_size_bytes"]))
            decoded_for_time = decoded.pop("_decoded_for_time", None)
            sample.update(decoded)
            if decoded.get("decode_status") == "success" and decoded_for_time is not None:
                time_row = {**row, "_decoded": decoded_for_time}
        samples.append(sample)
        time_rows.append(time_row)

    time_evidence = extract_event_time_evidence(time_rows)
    warnings = []
    if any(sample["raw"]["truncated"] for sample in samples):
        warnings.append(
            {
                "code": "SAMPLE_TRUNCATED",
                "message": f"At least one sample exceeded the {MAX_SAMPLE_BYTES}-byte per-sample limit.",
            }
        )
    if any(sample.get("decode_status") == "failed" for sample in samples):
        warnings.append(
            {
                "code": "SAMPLE_DECODE_FAILED",
                "message": "At least one wrapped RawData sample could not be decoded; its raw value is preserved.",
            }
        )
    if selected_rows and not time_evidence["selected"]:
        warnings.append(
            {"code": "EVENT_TIME_NOT_FOUND", "message": "No supported event-time field was found in samples."}
        )
    return {
        "samples": samples,
        "sample_count": len(samples),
        "received_sample_count": len(rows),
        "sample_limit": sample_limit,
        "has_more": len(rows) > sample_limit,
        "time_evidence": time_evidence,
        "warnings": warnings,
    }


def decode_raw_data_row(row, max_bytes=MAX_SAMPLE_BYTES):
    candidates = []
    for field in ("value", "base64_data"):
        value = row.get(field)
        if isinstance(value, dict | list):
            return {
                "decode_status": "success",
                "decoded_from": field,
                "content_encoding": "json_object",
                "decoded": limit_json_value(sanitize_json(value, redact_text=True), max_bytes=max_bytes),
                "_decoded_for_time": sanitize_json(value, redact_text=True),
            }
        if isinstance(value, str) and value:
            candidates.append((field, value))
    if not candidates:
        return {"decode_status": "not_applicable", "decoded_from": None, "content_encoding": None, "decoded": None}

    errors = []
    for field, value in candidates:
        try:
            decoded_value = json.loads(value)
            return {
                "decode_status": "success",
                "decoded_from": field,
                "content_encoding": "json",
                "decoded": limit_json_value(
                    sanitize_json(decoded_value, redact_text=True),
                    max_bytes=max_bytes,
                ),
                "_decoded_for_time": sanitize_json(decoded_value, redact_text=True),
            }
        except (TypeError, ValueError):
            pass
        try:
            decoded_bytes = base64.b64decode(value, validate=True)
            decoded_text = decoded_bytes.decode("utf-8")
            try:
                decoded_value = json.loads(decoded_text)
                content_encoding = "base64+json"
            except (TypeError, ValueError):
                decoded_value = decoded_text
                content_encoding = "base64+utf-8"
            sanitized_value = sanitize_json(decoded_value, redact_text=True)
            return {
                "decode_status": "success",
                "decoded_from": field,
                "content_encoding": content_encoding,
                "decoded": limit_json_value(sanitized_value, max_bytes=max_bytes),
                "_decoded_for_time": sanitized_value,
            }
        except (binascii.Error, UnicodeDecodeError, ValueError) as error:
            errors.append(f"{field}: {error}")
    return {
        "decode_status": "failed",
        "decoded_from": None,
        "content_encoding": None,
        "decoded": None,
        "decode_error": "; ".join(errors),
    }


def extract_event_time_evidence(rows):
    candidates = []
    for row_index, row in enumerate(rows):
        _collect_time_candidates(row, f"$[{row_index}]", row_index, candidates)
    candidates.sort(key=lambda item: (item["priority"], item["row_index"], item["field_path"]))
    successful = [candidate for candidate in candidates if candidate["parse_status"] == "success"]
    selected = None
    if successful:
        selected_priority = min(candidate["priority"] for candidate in successful)
        selected = max(
            (candidate for candidate in successful if candidate["priority"] == selected_priority),
            key=lambda candidate: candidate["parsed_time"],
        )
    public_candidates = [
        {key: value for key, value in candidate.items() if key != "priority"} for candidate in candidates
    ]
    public_selected = None
    if selected:
        public_selected = {key: value for key, value in selected.items() if key != "priority"}
    return {
        "selected": public_selected,
        "selection_strategy": "highest_priority_field_latest_value",
        "candidates": public_candidates,
    }


def _collect_time_candidates(value, path, row_index, candidates):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            normalized_key = str(key).replace("*", "").replace("-", "").lower()
            if normalized_key in EVENT_TIME_PRIORITY and not isinstance(child, dict | list):
                candidate = _parse_time_candidate(key, child, child_path, row_index)
                candidate["priority"] = EVENT_TIME_PRIORITY[normalized_key]
                candidates.append(candidate)
            if isinstance(child, dict | list):
                _collect_time_candidates(child, child_path, row_index, candidates)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _collect_time_candidates(child, f"{path}[{index}]", row_index, candidates)


def _parse_time_candidate(field_name, raw_value, field_path, row_index):
    parsed_time = None
    unit = None
    timezone_assumption = None
    error = None
    try:
        if isinstance(raw_value, bool):
            raise ValueError("boolean is not an event time")
        compact_datetime = (
            isinstance(raw_value, str)
            and re.fullmatch(r"\d{14}", raw_value.strip())
            and "timestamp" not in str(field_name).replace("*", "").lower()
        )
        if compact_datetime:
            text = raw_value.strip()
            parsed = arrow.get(text, "YYYYMMDDHHmmss")
            timezone_assumption = (
                "UTC" if str(field_name).lower() == "utctime" else str(timezone.get_current_timezone())
            )
            parsed = parsed.replace(tzinfo=timezone_assumption)
            unit = "datetime"
            parsed_time = parsed.to("UTC").isoformat()
        elif isinstance(raw_value, int | float) or (
            isinstance(raw_value, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", raw_value.strip())
        ):
            numeric = float(raw_value)
            absolute = abs(numeric)
            if absolute >= 1e18:
                unit, seconds = "nanoseconds", numeric / 1e9
            elif absolute >= 1e15:
                unit, seconds = "microseconds", numeric / 1e6
            elif absolute >= 1e12:
                unit, seconds = "milliseconds", numeric / 1e3
            else:
                unit, seconds = "seconds", numeric
            if not math.isfinite(seconds):
                raise ValueError("numeric event time is not finite")
            parsed_time = datetime.fromtimestamp(seconds, tz=datetime_timezone.utc).isoformat()
            timezone_assumption = "epoch_utc"
        else:
            text = str(raw_value).strip()
            parsed = arrow.get(text)
            if not _string_has_timezone(text):
                timezone_assumption = (
                    "UTC" if str(field_name).lower() == "utctime" else str(timezone.get_current_timezone())
                )
                parsed = arrow.get(parsed.naive, tzinfo=timezone_assumption)
            else:
                timezone_assumption = "value_provided"
            unit = "datetime"
            parsed_time = parsed.to("UTC").isoformat()
    except (ValueError, TypeError, OverflowError, OSError, arrow.parser.ParserError) as exc:
        error = str(exc)
    return {
        "row_index": row_index,
        "field_path": field_path,
        "field_name": field_name,
        "raw_value": raw_value,
        "parse_status": "success" if parsed_time else "failed",
        "parsed_time": parsed_time,
        "time_unit": unit,
        "timezone_assumption": timezone_assumption,
        "parse_error": error,
    }


def _sanitize(value, *, redact_text=False):
    if isinstance(value, dict):
        return {
            str(key): "***" if SENSITIVE_KEY_PATTERN.search(str(key)) else _sanitize(child, redact_text=redact_text)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_sanitize(item, redact_text=redact_text) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item, redact_text=redact_text) for item in value]
    if isinstance(value, str):
        return sanitize_sensitive_text(value, maximum=None) if redact_text else value
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _string_has_timezone(value):
    return bool(re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", value, re.IGNORECASE))


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")


def _truncate_utf8(value, max_bytes):
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _duration_ms(started):
    if started is None:
        return 0
    return round((time.monotonic() - started) * 1000, 2)


def _normalize_error(upstream_code, message, not_found_codes):
    code = str(upstream_code or "")
    lower_message = str(message or "").lower()
    if (
        code == "404"
        or code in {str(item) for item in not_found_codes}
        or "not found" in lower_message
        or "does not exist" in lower_message
    ):
        return "RESOURCE_NOT_FOUND", False
    if code in {"401", "1511009"} or "no verified user" in lower_message or "authentication" in lower_message:
        return "UPSTREAM_AUTH_FAILED", False
    if "bkdata username is not configured" in lower_message:
        return "BKDATA_IDENTITY_NOT_CONFIGURED", False
    if "bkdata tenant is not configured" in lower_message:
        return "BKDATA_TENANT_NOT_CONFIGURED", False
    if code == "403" or "permission denied" in lower_message or "no permission" in lower_message:
        return "UPSTREAM_PERMISSION_DENIED", False
    if "timeout" in lower_message or "timed out" in lower_message:
        return "UPSTREAM_TIMEOUT", True
    if "invalid response" in lower_message or "malformed response" in lower_message:
        return "UPSTREAM_INVALID_RESPONSE", False
    if "decode" in lower_message:
        return "UPSTREAM_DECODE_FAILED", False
    if isinstance(message, dict | list):
        return "UPSTREAM_INVALID_RESPONSE", False
    return "UPSTREAM_REQUEST_FAILED", True


def _error_message(code):
    messages = {
        "RESOURCE_NOT_FOUND": "The requested upstream resource does not exist.",
        "UPSTREAM_AUTH_FAILED": "Upstream user authentication failed.",
        "BKDATA_IDENTITY_NOT_CONFIGURED": "BKLOG has no configured BKBase user for this business.",
        "BKDATA_TENANT_NOT_CONFIGURED": "BKLOG cannot resolve a BKBase tenant for this business.",
        "UPSTREAM_PERMISSION_DENIED": "The upstream service denied access to the requested resource.",
        "UPSTREAM_TIMEOUT": "The upstream request timed out.",
        "UPSTREAM_INVALID_RESPONSE": "The upstream response was invalid.",
        "UPSTREAM_DECODE_FAILED": "The upstream response could not be decoded.",
        "UPSTREAM_REQUEST_FAILED": "The upstream request failed.",
    }
    return messages[code]
