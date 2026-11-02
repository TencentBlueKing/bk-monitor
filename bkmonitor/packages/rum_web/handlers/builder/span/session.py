from collections.abc import Sequence
from typing import Any

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.format import flatten_dict_data
from rum_web.handlers.builder.base import NamedKeyValueItem
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, SpanTypeItem, named
from rum_web.handlers.builder.utils import get_safe_number
from semconv.rum.constants import RumSpanType, SessionPhase


class SessionSpanOverview(SpanOverview):
    ITEMS = (
        SpanTypeItem(),
        *named("app_name"),
        NamedKeyValueItem("enter_url_template", _("入口页面")),
        NamedKeyValueItem("exit_url_template", _("退出页面")),
        *named("start_time", "end_time", "attributes.user.id", "resource.deployment.environment.name"),
    )


def session_time_range(spans: Sequence[dict[str, Any]]) -> tuple[int | float | None, int | float | None]:
    """开始取 start/rotate 的最早起点，结束取 end 的最晚终点。"""
    starts: list[int | float] = []
    ends: list[int | float] = []
    for span in spans:
        phase = span.get("attributes.session.phase")
        if phase in (SessionPhase.START.value, SessionPhase.ROTATE.value):
            if (start := get_safe_number(span.get("start_time"), None)) is not None:
                starts.append(start)
        elif phase == SessionPhase.END.value:
            if (end := get_safe_number(span.get("end_time"), None)) is not None:
                ends.append(end)
    return min(starts, default=None), max(ends, default=None)


class SessionSpanBuilder(SpanBuilder):
    RECORD_ID_FIELD = "attributes.session.id"
    RELATED_SPAN_TYPES = (RumSpanType.SESSION.value, RumSpanType.VIEW.value)
    OVERVIEW = SessionSpanOverview

    @classmethod
    def _prepare_flatten_data(
        cls, span: dict[str, Any], related_spans: Sequence[dict[str, Any]] = ()
    ) -> dict[str, Any]:
        flat: dict[str, Any] = flatten_dict_data(span)
        related: list[dict[str, Any]] = [flat.copy(), *(flatten_dict_data(item) for item in related_spans)]
        sessions: list[dict[str, Any]] = [
            item for item in related if item.get("attributes.span_type") == RumSpanType.SESSION.value
        ]
        latest: dict[str, Any] = max(sessions, key=lambda item: get_safe_number(item.get("end_time")))
        flat.update(latest)
        flat["start_time"], flat["end_time"] = session_time_range(sessions)
        views: list[dict[str, Any]] = [
            item
            for item in related
            if item.get("attributes.span_type") == RumSpanType.VIEW.value
            and get_safe_number(item.get("start_time"), None) is not None
        ]
        if views:
            ordered_views: list[dict[str, Any]] = sorted(views, key=cls._view_start_time)
            flat["enter_url_template"] = ordered_views[0].get("attributes.view.url_template")
            flat["exit_url_template"] = ordered_views[-1].get("attributes.view.url_template")
        return flat

    @staticmethod
    def _view_start_time(view: dict[str, Any]) -> int | float:
        started_at: int | float | None = get_safe_number(view.get("attributes.view.started_at"), None)
        return started_at * 1000 if started_at is not None else get_safe_number(view.get("start_time"))
