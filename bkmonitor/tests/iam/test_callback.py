"""Monitor entry points use the shared SDK callback and authentication."""

import base64
import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import resolve
from iam.resource.provider import ListResult

from bkmonitor.iam.backends.v4.callback_client import build_callback_client
from bkmonitor.iam.views.resources_v4 import build_resource_dispatcher
from iam_engine.v4.callback import V4CallbackIAM, V4ResourceApiDispatcher
from iam_engine.v4.resource import V4ResourceProvider
from monitor_web.iam.views import ApmApplicationProvider, GrafanaDashboardProvider, RumApplicationProvider, SpaceProvider


def test_monitor_registers_native_providers_without_a_second_framework():
    dispatcher = build_resource_dispatcher()
    assert type(dispatcher) is V4ResourceApiDispatcher
    assert type(dispatcher.iam) is V4CallbackIAM
    assert set(dispatcher._provider) == {"space", "apm_application", "grafana_dashboard", "rum_application"}
    for kind, native_type in (
        ("space", SpaceProvider),
        ("apm_application", ApmApplicationProvider),
        ("grafana_dashboard", GrafanaDashboardProvider),
        ("rum_application", RumApplicationProvider),
    ):
        provider = dispatcher._provider[kind]
        assert type(provider) is V4ResourceProvider
        assert type(provider.provider) is native_type


def test_monitor_actual_url_routes_use_shared_sdk_dispatcher():
    kernel = resolve("/rest/v2/iam/v4/callback/", urlconf="kernel_api.urls")
    web = resolve("/iam/v4/callback/", urlconf="monitor_web.iam.urls")
    # Login exemption and csrf exemption decorate the SDK dispatcher function.
    assert callable(kernel.func) and callable(web.func)
    with override_settings(ENABLE_MULTI_TENANT_MODE=False, BK_IAM_PERMISSION_MODE="v3"):
        request = RequestFactory().post("/", "{}", content_type="application/json")
        assert kernel.func(request).status_code == 503
        assert web.func(request).status_code == 503


def test_monitor_callback_uses_request_tenant_saas_credentials_and_native_provider(monkeypatch):
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "union")
    cache.clear()
    with override_settings(
        BK_IAM_V4_SYSTEM_ID="bk_monitorv3",
        BK_IAM_V4_APIGATEWAY_URL="https://v4.example.test/",
        BK_APP_TENANT_ID="system",
        SAAS_APP_CODE="monitor-saas",
        SAAS_SECRET_KEY="dummy-saas-secret",
        ENABLE_MULTI_TENANT_MODE=True,
    ):
        dispatcher = build_resource_dispatcher()
        provider = dispatcher._provider["apm_application"].provider
        provider.fetch_instance_info = MagicMock(return_value=ListResult([
            {"id": "42", "display_name": "application", "name": "internal-name", "_bk_iam_path_": "/space,3/"}
        ], 1))
        request = RequestFactory().post("/", json.dumps({
            "method": "fetch_instance_info", "type": "apm_application",
            "filter": {"ids": ["42"]}, "requires": ["_bk_iam_path_"],
        }), content_type="application/json", HTTP_X_BK_TENANT_ID="tenant-a",
            HTTP_AUTHORIZATION="Basic " + base64.b64encode(b"bk_iam:test-token").decode())
        factory = MagicMock(wraps=dispatcher.iam.client_factory)
        dispatcher.iam.client_factory = factory
        with patch("iam_engine.v4.client.V4Client.retrieve_system_auth_token", return_value="test-token") as retrieve:
            response = dispatcher.as_view()(request)
        assert response.status_code == 200
        assert json.loads(response.content) == {"data": [{
            "id": "42", "display_name": "application", "_bk_iam_path_": "/space,space|3/"
        }]}
        retrieve.assert_called_once_with("bk_monitorv3")
        assert provider.fetch_instance_info.call_args.kwargs["bk_tenant_id"] == "tenant-a"
        options = factory.call_args.args[0]
        assert (options.app_code, options.app_secret) == ("monitor-saas", "dummy-saas-secret")
        assert factory.call_args.kwargs == {"bk_tenant_id": "tenant-a"}


def test_callback_disabled_before_any_options_or_token_lookup(monkeypatch):
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
    client = build_callback_client("system")
    client.options_loader = MagicMock(side_effect=AssertionError("disabled V4 must not load credentials"))
    assert client.get_token("bk_monitorv3")[0] is False
    client.options_loader.assert_not_called()
