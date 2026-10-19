"""Shared callback protocol/auth tests. No outbound IAM requests are allowed."""

import base64
import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from iam.resource.provider import ListResult, ResourceProvider

from iam_engine.core.config import AuthMode
from iam_engine.provider.codec import IdentityCodec
from iam_engine.v4.callback import V4CallbackIAM, V4ResourceApiDispatcher
from iam_engine.v4.config import V4Options
from iam_engine.v4.resource import V4ResourceProvider


class NativeProvider(ResourceProvider):
    def list_instance(self, filter, page, **options):
        self.received = (filter, page, options)
        return ListResult([{"id": "1", "display_name": "one"}], 1)

    def fetch_instance_info(self, filter, **options):
        self.received = (filter, options)
        return ListResult([{"id": "1", "display_name": "one", "_bk_iam_path_": "/space,2/"}], 1)

    def list_attr(self, **options):
        raise NotImplementedError

    def list_attr_value(self, filter, page, **options):
        raise NotImplementedError

    def list_instance_by_policy(self, filter, page, **options):
        raise NotImplementedError

    def search_instance(self, filter, page, **options):
        raise NotImplementedError


@pytest.fixture
def callback(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_APP_TENANT_ID = "system"
    cache.clear()
    state = {"mode": AuthMode.V4}
    options = V4Options.from_settings(global_credentials=("dummy-app", "dummy-secret"))
    state["options"] = replace(options, gateway_url="https://v4.example.test/", system_id="test", auth_token_cache_seconds=300)
    factory = MagicMock()
    factory.return_value.retrieve_system_auth_token.return_value = "test-token"
    auth = V4CallbackIAM(
        options_loader=lambda tenant: state["options"],
        mode_loader=lambda: state["mode"],
        bk_tenant_id="system",
        client_factory=factory,
    )
    provider = NativeProvider()
    dispatcher = V4ResourceApiDispatcher(auth, "test")
    dispatcher.register("child", V4ResourceProvider(provider, "child", IdentityCodec()))

    def request(body=None, **headers):
        defaults = {
            "HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"bk_iam:test-token").decode(),
            "HTTP_X_REQUEST_ID": "callback-test",
        }
        defaults.update(headers)
        data = body if body is not None else {
            "method": "list_instance", "type": "child", "page": {"page": 2, "page_size": 10}
        }
        response = dispatcher.as_view()(RequestFactory().post("/", json.dumps(data), content_type="application/json", **defaults))
        return response, json.loads(response.content)

    return state, auth, factory, provider, dispatcher, request


@pytest.mark.parametrize("mode,expected", [(AuthMode.V3, 503), (AuthMode.V4, 200), (AuthMode.UNION, 200)])
def test_callback_mode_isolation(callback, mode, expected):
    state, auth, factory, provider, _, request = callback
    state["mode"] = mode
    response, _ = request()
    assert response.status_code == expected
    if mode is AuthMode.V3:
        factory.assert_not_called()
        assert not hasattr(provider, "received")
        assert auth.get_token("test")[0] is False


def test_dynamic_switch_and_invalid_mode_do_not_use_cached_token(callback):
    state, _, factory, provider, _, request = callback
    assert request()[0].status_code == 200
    del provider.received
    state["mode"] = AuthMode.V3
    assert request()[0].status_code == 503
    state["mode"] = "invalid"
    assert request()[0].status_code == 400
    assert not hasattr(provider, "received")
    factory.assert_called_once()


def test_native_sdk_processor_receives_page_filter_and_tenant(callback):
    _, _, factory, provider, _, request = callback
    response, payload = request({
        "method": "list_instance", "type": "child", "filter": {"keyword": "name", "parent": {"type": "space", "id": "2"}},
        "page": {"page": 2, "page_size": 10},
    }, HTTP_X_BK_TENANT_ID="tenant-a")
    assert response.status_code == 200
    assert payload == {"data": {"count": 1, "results": [{"id": "1", "display_name": "one"}]}}
    assert response["X-Request-Id"] == "callback-test"
    filters, page, options = provider.received
    assert filters.parent == {"type": "space", "id": "2"}
    assert filters.search == {"child": ["name"]}
    assert (page.slice_from, page.slice_to) == (10, 20)
    assert options["bk_tenant_id"] == factory.call_args.kwargs["bk_tenant_id"] == "tenant-a"
    assert options["include_resource_metadata"] is True


@pytest.mark.parametrize("page", [None, {}, [], {"page": 0, "page_size": 1}, {"page": 1, "page_size": 1001}, {"page": True, "page_size": 1}, {"page": 1, "page_size": 1.5}, {"limit": 1, "offset": -1}])
def test_invalid_page_never_queries_resources(callback, page):
    *_, provider, _, request = callback
    response, payload = request({"method": "list_instance", "type": "child", "page": page})
    assert response.status_code == 400
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert not hasattr(provider, "received")


@pytest.mark.parametrize("body", [[], None, {"method": 3, "type": "child"}, {"method": "list_instance", "type": "child", "filter": [], "page": {}}, {"method": "fetch_instance_info", "type": "child", "filter": {"ids": [1]}}, {"method": "fetch_instance_info", "type": "child", "filter": {"ids": ["1"] * 1001}}, {"method": "fetch_instance_info", "type": "child", "filter": {"ids": ["1"]}, "requires": "name"}])
def test_invalid_arguments(callback, body):
    *_, provider, _, request = callback
    if body is None:
        body = "not-an-object"
    assert request(body)[0].status_code == 400
    assert not hasattr(provider, "received")


@pytest.mark.parametrize("method", ["unknown", "list_instance_by_policy", "search_instance", "fetch_instance_list"])
def test_unsupported_methods_are_not_empty_success(callback, method):
    *_, provider, _, request = callback
    response, _ = request({"method": method, "type": "child"})
    assert response.status_code == 404
    assert not hasattr(provider, "received")


def test_fetch_requires_and_empty_ids(callback):
    *_, provider, _, request = callback
    response, payload = request({"method": "fetch_instance_info", "type": "child", "filter": {"ids": ["1"]}, "requires": ["_bk_iam_path_"]})
    assert response.status_code == 200
    assert payload["data"][0]["_bk_iam_path_"] == "/space,2/"
    assert provider.received[0].attrs == ["_bk_iam_path_"]
    del provider.received
    assert request({"method": "fetch_instance_info", "type": "child", "filter": {"ids": []}})[1] == {"data": []}
    assert not hasattr(provider, "received")


@pytest.mark.parametrize("header", ["", "Bearer test-token", "Basic @@@", "Basic YWJj", "Basic " + base64.b64encode(b"wrong:test-token").decode(), "Basic " + base64.b64encode(b"bk_iam:wrong").decode()])
def test_basic_auth_fail_closed(callback, header):
    *_, provider, _, request = callback
    response, payload = request(HTTP_AUTHORIZATION=header)
    assert response.status_code == 401
    assert payload["error"]["code"] == "UNAUTHENTICATED"
    assert not hasattr(provider, "received")


def test_cache_isolated_by_tenant_gateway_system_and_credentials(callback):
    state, auth, factory, *_ = callback
    assert auth.get_token("test")[0]
    assert auth.get_token("test")[0]
    assert factory.call_count == 1
    assert auth.get_token("test", bk_tenant_id="tenant-b")[0]
    for changes in ({"gateway_url": "https://other.test/"}, {"app_secret": "rotated"}, {"app_code": "other-app"}, {"auth_token_path": "other-token-path/"}):
        state["options"] = replace(state["options"], **changes)
        assert auth.get_token("test")[0]
    assert factory.call_count == 6
    assert auth.get_token("other-system")[0] is False
    assert factory.call_count == 6
    state["options"] = replace(state["options"], system_id="other-system")
    assert auth.get_token("other-system")[0]
    assert factory.call_count == 7


def test_zero_ttl_bypasses_existing_cache(callback):
    state, auth, factory, *_ = callback
    assert auth.get_token("test")[0]
    state["options"] = replace(state["options"], auth_token_cache_seconds=0)
    factory.return_value.retrieve_system_auth_token.return_value = "new-token"
    assert auth.get_token("test")[2] == "new-token"
    assert auth.get_token("test")[2] == "new-token"
    assert factory.call_count == 3


def test_fetch_failure_not_cached_and_errors_do_not_leak(callback, caplog):
    _, auth, factory, *_ = callback
    factory.return_value.retrieve_system_auth_token.side_effect = [RuntimeError("secret upstream payload"), "test-token"]
    assert auth.get_token("test") == (False, "IAM V4 callback token unavailable", "")
    assert auth.get_token("test")[0]
    assert "secret upstream payload" not in caplog.text


@pytest.mark.parametrize("tenant", [None, "", "   "])
def test_missing_multitenant_header_before_token_and_query(callback, settings, tenant):
    settings.ENABLE_MULTI_TENANT_MODE = True
    _, _, factory, provider, _, request = callback
    headers = {} if tenant is None else {"HTTP_X_BK_TENANT_ID": tenant}
    assert request(**headers)[0].status_code == 400
    factory.assert_not_called()
    assert not hasattr(provider, "received")
