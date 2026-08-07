import json
import logging
import os
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

import audit as audit_module
import pytest
from bk_audit.contrib.django.formatters import DjangoFormatter
from blueapps.utils.local import request_local_injection
from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse
from django.http.multipartparser import MultiPartParserError
from django.test import RequestFactory

from audit.apps import AuditConfig
from audit.instance import DashboardInstance, push_event
from bkmonitor.middlewares.request_middlewares import RequestProvider
from core.errors.issue import IssueRenameConflictError
from monitor_adapter.home.views import dispatch_external_proxy


def make_dashboard_request(status_code=200):
    request = RequestFactory().get(
        "/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2",
        HTTP_X_REAL_IP="<ip>",
        HTTP_USER_AGENT="external-monitor-client",
    )
    request.user = SimpleNamespace(username="authorized-agent")
    request.biz_id = "2"
    request.org_name = "2"
    request.external_user = "external-user"
    request.request_id = "request-id"
    return request, HttpResponse(status=status_code)


@pytest.mark.parametrize(
    ("response_status", "target_status", "result_code"),
    [(200, None, 0), (403, None, 403), (200, 500, 500)],
)
def test_push_event_records_external_dashboard_context_and_result(response_status, target_status, result_code):
    request, response = make_dashboard_request(response_status)
    if target_status is not None:
        request._audit_response_status = target_status

    with (
        patch("audit.instance.bk_audit_client.add_event") as add_event,
        patch("audit.instance.bk_audit_client.export_events") as export_events,
    ):
        push_event(request, response)

    event = add_event.call_args.kwargs
    audit_event = DjangoFormatter().build_event(
        action=event["action"],
        resource_type=event["resource_type"],
        audit_context=event["audit_context"],
        instance=event["instance"],
        event_id=None,
        event_content="",
        start_time=0,
        end_time=0,
        result_code=event["result_code"],
        result_content=event["result_content"],
        extend_data=event["extend_data"],
    )
    assert audit_event.username == "external-user"
    assert audit_event.request_id == "request-id"
    assert audit_event.access_source_ip == "<ip>"
    assert audit_event.access_user_agent == "external-monitor-client"
    assert request.user.username == "authorized-agent"
    assert event["result_code"] == result_code
    assert event["result_content"] == (f"HTTP {result_code}" if result_code else "")
    assert event["extend_data"] == {
        "external_user": "external-user",
        "action_name": event["action"].name,
        "authorizer": "authorized-agent",
        "bk_biz_id": "2",
        "grafana_org_name": "2",
        "request_method": "GET",
        "response_status": target_status if target_status is not None else response_status,
    }
    export_events.assert_called_once_with()


def test_push_event_preserves_internal_user_as_operator():
    request = RequestFactory().get("/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2")
    request.user = SimpleNamespace(username="internal-user")
    request.biz_id = "2"

    with (
        patch("audit.instance.bk_audit_client.add_event") as add_event,
        patch("audit.instance.bk_audit_client.export_events"),
    ):
        push_event(request, HttpResponse())

    event = add_event.call_args.kwargs
    assert event["audit_context"].request is request
    assert event["audit_context"].request.user.username == "internal-user"
    assert event["extend_data"]["external_user"] == ""
    assert "authorizer" not in event["extend_data"]


@pytest.mark.parametrize(
    ("path", "instance_id"),
    [
        ("/grafana/api/dashboards/home", "home"),
        ("/grafana/api/dashboards/uid/dashboard-uid/", "dashboard-uid"),
    ],
)
def test_push_event_matches_supported_dashboard_view_routes(path, instance_id):
    request = RequestFactory().get(path)
    request.user = SimpleNamespace(username="internal-user")
    request.biz_id = "2"

    with (
        patch("audit.instance.bk_audit_client.add_event") as add_event,
        patch("audit.instance.bk_audit_client.export_events"),
    ):
        push_event(request, HttpResponse())

    assert add_event.call_args.kwargs["instance"].instance_id == instance_id


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/grafana/api/dashboards/uid/dashboard-uid"),
        ("get", "/grafana/api/dashboards/uid/dashboard-uid/permissions"),
        ("get", "/grafana/api/dashboards/home/preferences"),
        ("get", "/rest/v2/grafana/dashboards/"),
    ],
)
def test_push_event_ignores_non_view_dashboard_requests(method, path):
    request = getattr(RequestFactory(), method)(path)
    request.user = SimpleNamespace(username="internal-user")
    request.biz_id = "2"

    with (
        patch("audit.instance.bk_audit_client.add_event") as add_event,
        patch("audit.instance.bk_audit_client.export_events") as export_events,
    ):
        push_event(request, HttpResponse())

    add_event.assert_not_called()
    export_events.assert_not_called()


def test_push_event_supports_route_specific_non_get_methods():
    request = RequestFactory().post("/write/dashboard-uid")
    request.user = SimpleNamespace(username="internal-user")
    request.biz_id = "2"
    route_filters = (({"POST"}, re.compile(r"/write/(?P<uid>[^/]+)"), DashboardInstance),)

    with (
        patch("audit.instance.InstanceFilter", route_filters),
        patch("audit.instance.bk_audit_client.add_event") as add_event,
        patch("audit.instance.bk_audit_client.export_events") as export_events,
    ):
        push_event(request, HttpResponse())

    add_event.assert_called_once()
    export_events.assert_called_once_with()


def test_push_event_does_not_break_request_when_export_fails(caplog):
    request, response = make_dashboard_request()

    with (
        patch("audit.instance.bk_audit_client.add_event", side_effect=RuntimeError("export failed")),
        patch("audit.instance.bk_audit_client.export_events") as export_events,
        caplog.at_level(logging.ERROR, logger="audit.instance"),
    ):
        push_event(request, response)

    export_events.assert_not_called()
    assert "push audit event failed" in caplog.text


def test_dispatch_external_proxy_uses_target_request_for_response_audit():
    request = RequestFactory().post(
        "/dispatch_external_proxy/",
        data=json.dumps(
            {
                "url": "/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2",
                "method": "GET",
                "data": {},
            }
        ),
        content_type="application/json",
        HTTP_USER="external-user",
        HTTP_X_REAL_IP="<ip>",
        HTTP_X_REQUEST_ID="request-id",
        HTTP_USER_AGENT="external-monitor-client",
    )
    request.session = {}
    request.LANGUAGE_CODE = "zh-hans"
    assert not hasattr(request, "request_id")
    authorized_agent = SimpleNamespace(username="authorized-agent")
    target_response = HttpResponse(status=500)
    target_view = Mock(return_value=target_response)

    def login(proxy_request, user):
        proxy_request.user = user

    with (
        request_local_injection({"request_id": "request-id"}),
        patch("monitor_adapter.home.views.is_external_proxy_token_valid", return_value=True),
        patch(
            "monitor_adapter.home.views.GlobalConfig.objects.get_or_create",
            return_value=(SimpleNamespace(value={"2": "authorized-agent"}), False),
        ),
        patch("monitor_adapter.home.views.auth.authenticate", return_value=authorized_agent),
        patch("monitor_adapter.home.views.auth.login", side_effect=login),
        patch(
            "monitor_adapter.home.views.resolve",
            return_value=SimpleNamespace(func=target_view, kwargs={}),
        ),
    ):
        response = dispatch_external_proxy(request)

    target_request = target_view.call_args.args[0]
    assert target_request.user is authorized_agent
    assert target_request.external_user == "external-user"
    assert target_request.biz_id == "2"
    assert target_request.request_id == "request-id"
    assert target_request.META["HTTP_X_REAL_IP"] == "<ip>"
    assert target_request.META["HTTP_X_REQUEST_ID"] == "request-id"
    assert target_request.META["HTTP_USER_AGENT"] == "external-monitor-client"
    assert target_request._audit_response_status == 500

    # MonitorAPIMiddleware 会把 AJAX 5xx 归一化为 200，审计仍应使用代理目标的原始状态。
    target_response.status_code = 200

    with patch("bkmonitor.middlewares.request_middlewares.push_event") as audit_event:
        response = RequestProvider(lambda _: HttpResponse()).process_response(request, response)

    audit_event.assert_called_once_with(target_request, target_response)
    assert response is target_response


@pytest.mark.parametrize(
    ("exception", "status_code"),
    [
        (Http404(), 404),
        (PermissionDenied(), 403),
        (MultiPartParserError(), 400),
        (BadRequest(), 400),
        (SuspiciousOperation(), 400),
        (IssueRenameConflictError(message="conflict"), 409),
        (RuntimeError("failed"), 500),
    ],
)
def test_dispatch_external_proxy_preserves_django_exception_status(exception, status_code):
    request = RequestFactory().post(
        "/dispatch_external_proxy/",
        data=json.dumps(
            {
                "url": "/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2",
                "method": "GET",
                "data": {},
            }
        ),
        content_type="application/json",
        HTTP_USER="external-user",
    )
    request.session = {}
    request.LANGUAGE_CODE = "zh-hans"
    authorized_agent = SimpleNamespace(username="authorized-agent")

    def login(proxy_request, user):
        proxy_request.user = user

    with (
        patch("monitor_adapter.home.views.is_external_proxy_token_valid", return_value=True),
        patch(
            "monitor_adapter.home.views.GlobalConfig.objects.get_or_create",
            return_value=(SimpleNamespace(value={"2": "authorized-agent"}), False),
        ),
        patch("monitor_adapter.home.views.auth.authenticate", return_value=authorized_agent),
        patch("monitor_adapter.home.views.auth.login", side_effect=login),
        patch(
            "monitor_adapter.home.views.resolve",
            return_value=SimpleNamespace(func=Mock(side_effect=exception), kwargs={}),
        ),
        pytest.raises(type(exception)),
    ):
        dispatch_external_proxy(request)

    assert request._audit_request._audit_response_status == status_code


def test_dispatch_external_proxy_returns_403_when_authorizer_is_missing():
    request = RequestFactory().post(
        "/dispatch_external_proxy/",
        data=json.dumps(
            {
                "url": "/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2",
                "method": "GET",
                "data": {},
            }
        ),
        content_type="application/json",
        HTTP_USER="external-user",
    )
    request.session = {}
    request.LANGUAGE_CODE = "zh-hans"

    with (
        patch("monitor_adapter.home.views.is_external_proxy_token_valid", return_value=True),
        patch(
            "monitor_adapter.home.views.GlobalConfig.objects.get_or_create",
            return_value=(SimpleNamespace(value={}), False),
        ),
        patch("monitor_adapter.home.views.auth.authenticate") as authenticate,
    ):
        response = dispatch_external_proxy(request)

    assert response.status_code == 403
    assert json.loads(response.content) == {"result": False, "message": "业务2无对应授权人"}
    authenticate.assert_not_called()


def test_dispatch_external_proxy_returns_403_when_external_user_is_missing():
    request = RequestFactory().post(
        "/dispatch_external_proxy/",
        data=json.dumps(
            {
                "url": "/grafana/api/dashboards/uid/dashboard-uid?bk_biz_id=2",
                "method": "GET",
                "data": {},
            }
        ),
        content_type="application/json",
    )
    request.session = {}
    request.LANGUAGE_CODE = "zh-hans"
    authorized_agent = SimpleNamespace(username="authorized-agent")
    target_view = Mock(return_value=HttpResponse())

    def login(proxy_request, user):
        proxy_request.user = user

    with (
        patch("monitor_adapter.home.views.is_external_proxy_token_valid", return_value=True),
        patch(
            "monitor_adapter.home.views.GlobalConfig.objects.get_or_create",
            return_value=(SimpleNamespace(value={"2": "authorized-agent"}), False),
        ),
        patch("monitor_adapter.home.views.auth.authenticate", return_value=authorized_agent) as authenticate,
        patch("monitor_adapter.home.views.auth.login", side_effect=login),
        patch(
            "monitor_adapter.home.views.resolve",
            return_value=SimpleNamespace(func=target_view, kwargs={}),
        ),
    ):
        response = dispatch_external_proxy(request)

    assert response.status_code == 403
    assert json.loads(response.content) == {"result": False, "message": "external user is required"}
    authenticate.assert_not_called()
    target_view.assert_not_called()
    assert not hasattr(request, "_audit_request")


def test_audit_setup_requires_token():
    config = AuditConfig("audit", audit_module)
    env = {
        "BKAPP_OTEL_LOG_ENDPOINT": "https://example.invalid",
        "BKAPP_OTEL_LOG_BK_DATA_TOKEN": "",
    }

    with patch.dict(os.environ, env, clear=True), patch("audit.apps.setup") as setup:
        config.ready()

    setup.assert_not_called()


def test_audit_setup_failure_does_not_block_application_startup(caplog):
    config = AuditConfig("audit", audit_module)
    env = {
        "BKAPP_OTEL_LOG_ENDPOINT": "https://example.invalid",
        "BKAPP_OTEL_LOG_BK_DATA_TOKEN": "token",
    }

    with (
        patch.dict(os.environ, env, clear=True),
        patch("audit.apps.setup", side_effect=RuntimeError("setup failed")),
        caplog.at_level(logging.ERROR, logger="audit.apps"),
    ):
        config.ready()

    assert "initialize audit exporter failed" in caplog.text


def test_audit_setup_accepts_configuration_without_data_id():
    config = AuditConfig("audit", audit_module)
    env = {
        "BKAPP_OTEL_LOG_ENDPOINT": "https://example.invalid",
        "BKAPP_OTEL_LOG_BK_DATA_TOKEN": "token",
    }

    with patch.dict(os.environ, env, clear=True), patch("audit.apps.setup") as setup:
        config.ready()

    setup.assert_called_once()
