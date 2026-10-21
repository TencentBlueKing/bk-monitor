"""Verify response-time session writes with Django's actual cache backend."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.utils import timezone

from bkmonitor.middlewares.request_middlewares import RequestProvider
from common.middlewares import TimeZoneMiddleware


@pytest.mark.parametrize(
    "previous,current,time_zone,other_change,save_every_request,expected_saves",
    [
        ("42", "42", "Asia/Shanghai", False, False, 0),
        ("42", "43", "Asia/Shanghai", False, False, 1),
        (None, "42", "Asia/Shanghai", False, False, 1),
        ("42", "42", "UTC", False, False, 1),
        ("42", "42", "Asia/Shanghai", True, False, 1),
        ("42", "42", "Asia/Shanghai", False, True, 1),
    ],
)
def test_business_selection_only_saves_modified_session(
    previous, current, time_zone, other_change, save_every_request, expected_saves
):
    with override_settings(SESSION_SAVE_EVERY_REQUEST=save_every_request):
        session = SessionStore()
        if previous is not None:
            session["bk_biz_id"] = previous
        session[settings.TIMEZONE_SESSION_KEY] = "Asia/Shanghai"
        session["other"] = "initial"
        session.save()
        request = RequestFactory().get("/")
        request.session = SessionStore(session.session_key)
        request.resolver_match = SimpleNamespace(namespace="monitor_web")
        if other_change:
            request.session["other"] = "changed"
        with (
            patch("bkmonitor.middlewares.request_middlewares.fetch_biz_id_from_request", return_value=current),
            patch("common.middlewares.fetch_biz_id_from_request", return_value=current),
            patch("common.middlewares.SpaceApi.get_space_detail", return_value=SimpleNamespace(time_zone=time_zone)),
        ):
            RequestProvider(lambda request: HttpResponse()).process_view(request, None, (), {})
            TimeZoneMiddleware(lambda request: HttpResponse()).process_view(request, lambda: None, (), {})
        timezone.deactivate()
        with patch.object(request.session, "save", wraps=request.session.save) as save:
            response = SessionMiddleware(lambda request: HttpResponse()).process_response(request, HttpResponse())
        assert save.call_count == expected_saves
        assert request.biz_id == current
        assert request.session["bk_biz_id"] == current
        assert (settings.SESSION_COOKIE_NAME in response.cookies) == bool(expected_saves)
        stored = SessionStore(session.session_key)
        assert stored["bk_biz_id"] == current
        assert stored[settings.TIMEZONE_SESSION_KEY] == time_zone


def test_adapter_still_clears_business_selection():
    request = RequestFactory().get("/")
    request.session = SessionStore()
    request.session["bk_biz_id"] = "42"
    request.resolver_match = SimpleNamespace(namespace="monitor_adapter")
    with patch("bkmonitor.middlewares.request_middlewares.fetch_biz_id_from_request", return_value=None):
        RequestProvider(lambda request: HttpResponse()).process_view(request, None, (), {})
    assert request.session["bk_biz_id"] is None
    assert request.session.modified
