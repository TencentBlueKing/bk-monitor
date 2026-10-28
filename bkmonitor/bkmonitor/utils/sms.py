"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import re
import unicodedata
from contextlib import nullcontext
from datetime import datetime, timezone as datetime_timezone
from html import unescape
from zoneinfo import ZoneInfo

from django.conf import settings
from django.template.loader import get_template
from django.utils import timezone, translation
from django.utils.translation import gettext as _

logger = logging.getLogger("fta_action.run")

SMS_STANDARD_MAX_LENGTH = 70
SMS_TEMPLATE_KINDS = (
    "abnormal/action",
    "abnormal/converge",
    "recovered/action",
    "recovered/converge",
    "closed/action",
    "closed/converge",
    "ack/action",
    "ack/converge",
    "assign/action",
    "assign/converge",
    "fta_action",
    "incident",
    "shield",
)
_SMS_TEMPLATE_KINDS_BY_PATH = {f"notice/{kind}/sms_content.jinja": kind for kind in SMS_TEMPLATE_KINDS}
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(
    r"\b(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>()，。；、]+"
    r"|\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}(?::\d+)?(?:/[^\s<>()，。；、]*)?",
    re.IGNORECASE,
)


def get_sms_template_mode() -> str:
    """Read the dynamic mode once per notice, with the static environment default as fallback."""
    mode = settings.SMS_NOTICE_TEMPLATE_MODE
    if isinstance(mode, str) and mode in ("legacy", "standard"):
        return mode
    fallback = settings.SMS_NOTICE_TEMPLATE_MODE_DEFAULT
    logger.error("invalid SMS_NOTICE_TEMPLATE_MODE %r, using static default %s", mode, fallback)
    return fallback


def standard_sms_template_kind(template_path: str) -> str | None:
    """Only explicitly supported SMS content paths participate in mode switching."""
    return _SMS_TEMPLATE_KINDS_BY_PATH.get(template_path)


def sms_utf16_length(value: str) -> int:
    """Count SMS characters as UTF-16 code units, including two units for non-BMP characters."""
    return sum(2 if ord(character) > 0xFFFF else 1 for character in value)


def _truncate(value: str, budget: int) -> str:
    if sms_utf16_length(value) <= budget:
        return value
    if budget <= 0:
        return ""
    result = []
    remaining = budget - 1  # The ellipsis also consumes one UTF-16 unit.
    for character in value:
        width = 2 if ord(character) > 0xFFFF else 1
        if width > remaining:
            break
        result.append(character)
        remaining -= width
    return "".join(result) + "…"


def _plain_text(value) -> str:
    """Keep labels from links, remove URLs and normalize control characters without changing source data."""
    if value is None:
        return ""
    value = unescape(str(value))
    value = "".join(" " if character.isspace() else character for character in value)
    value = "".join(character for character in value if not unicodedata.category(character).startswith("C"))
    value = _MARKDOWN_LINK.sub(r"\1", value)
    value = re.sub(r"<[^>]*>", "", value)
    value = _URL.sub("", value)
    return " ".join(value.split())


def _is_english(language: str | None = None) -> bool:
    return (language or translation.get_language() or settings.LANGUAGE_CODE).lower().startswith("en")


def format_sms_time(event_time, tz=None, language: str | None = None) -> str:
    """Format an event datetime, epoch seconds or ISO string in the explicit/current business timezone.

    Naive datetimes and ISO strings use UTC, matching the existing UTC-to-business conversion.
    Missing or invalid event times never fall back to the task execution time.
    """
    with translation.override(language) if language else nullcontext():
        target_timezone = ZoneInfo(tz) if isinstance(tz, str) else tz or timezone.get_current_timezone()
        try:
            if event_time is None or isinstance(event_time, bool) or event_time == "":
                raise ValueError("missing event time")
            if isinstance(event_time, datetime):
                value = event_time
            else:
                try:
                    epoch = float(event_time)
                except (TypeError, ValueError):
                    value = datetime.fromisoformat(event_time)
                else:
                    value = datetime.fromtimestamp(epoch, tz=datetime_timezone.utc)
            if timezone.is_naive(value):
                value = value.replace(tzinfo=datetime_timezone.utc)
            value = timezone.localtime(value, timezone=target_timezone)
        except (TypeError, ValueError, OverflowError, OSError):
            return _("时间未知")
        if _is_english(language):
            return value.strftime("%Y-%m-%d %H:%M")
        return f"{value.year}年{value.month}月{value.day}日 {value:%H:%M}分"


def render_standard_sms(kind: str, values: dict, language: str | None = None) -> str:
    """Render one standard SMS; ``operator`` accepts a name or a list/tuple of names.

    All fields are already structured display values. Only names and operator names may be
    shortened; event time, count, severity, status, duration and the full guidance are retained.
    Values are passed to the template as data and never rendered as a second template.
    """
    if kind not in SMS_TEMPLATE_KINDS:
        raise ValueError(f"unsupported standard SMS kind: {kind}")
    with translation.override(language) if language else nullcontext():
        english = _is_english(language)
        suffix = "_en" if english else ""
        template = get_template(f"notice/standard/{kind}/sms_content{suffix}.jinja")
        context = {
            field: _plain_text(values.get(field))
            for field in ("time", "level", "count", "name", "status", "duration", "shield_action")
        }
        context["time"] = context["time"] or _("时间未知")
        operators = values.get("operator")
        if not isinstance(operators, (list, tuple)):
            operators = [operators]
        operators = [name for value in operators if (name := _plain_text(value))]
        context["operator"] = (", " if english else "、").join(operators)

        def render():
            return template.render(context).strip()

        content = render()
        overflow = sms_utf16_length(content) - SMS_STANDARD_MAX_LENGTH
        if overflow > 0 and context["name"]:
            context["name"] = _truncate(context["name"], sms_utf16_length(context["name"]) - overflow)
            content = render()
        if sms_utf16_length(content) > SMS_STANDARD_MAX_LENGTH and len(operators) > 1:
            suffix = f" +{len(operators) - 1}" if english else f"等{len(operators)}人"
            context["operator"] = operators[0] + suffix
            content = render()
            overflow = sms_utf16_length(content) - SMS_STANDARD_MAX_LENGTH
            if overflow > 0:
                context["operator"] = _truncate(operators[0], sms_utf16_length(operators[0]) - overflow) + suffix
                content = render()
        elif sms_utf16_length(content) > SMS_STANDARD_MAX_LENGTH and context["operator"]:
            overflow = sms_utf16_length(content) - SMS_STANDARD_MAX_LENGTH
            context["operator"] = _truncate(context["operator"], sms_utf16_length(context["operator"]) - overflow)
            content = render()
        if sms_utf16_length(content) > SMS_STANDARD_MAX_LENGTH:
            raise ValueError(f"standard SMS fixed fields exceed {SMS_STANDARD_MAX_LENGTH} UTF-16 units: {kind}")
        return content
