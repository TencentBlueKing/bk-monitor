import json

import pytest

from bkmonitor.utils.user import get_admin_username
from core.drf_resource import api


@pytest.mark.parametrize("tenant", ["tenant-a", "tenant-b"])
def test_tenant_admin_lookup(tenant, settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.BK_ADMIN_USERNAME = "custom-login"
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user", return_value=[{"bk_username": tenant}])
    assert get_admin_username.__wrapped__(tenant) == tenant
    lookup.assert_called_once_with(bk_tenant_id=tenant, lookup_field="login_name", lookups="custom-login")


def test_single_tenant_admin(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.COMMON_USERNAME = "single-user"
    assert get_admin_username.__wrapped__("system") == "single-user"


@pytest.mark.parametrize("configured", [None, "", "   "])
def test_backend_without_login_keeps_original_identity(settings, mocker, configured):
    from bkmonitor.utils.user import get_backend_username

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = configured
    settings.COMMON_USERNAME = "legacy"
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user")
    assert get_backend_username(bk_tenant_id="system") == "legacy"
    lookup.assert_not_called()


def test_configured_single_tenant_datalink(settings, mocker):
    from api.bk_login.default import BatchLookupVirtualUserResource
    from api.bkdata.default import GetDataLink
    from bkmonitor.utils.user import _single_tenant_admin_username

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = "  service-login  "
    _single_tenant_admin_username.cache_clear()
    lookup = mocker.patch.object(
        api.bk_login, "batch_lookup_virtual_user", return_value=[{"bk_username": "virtual-id"}]
    )
    assert "/api/bk-user/" in BatchLookupVirtualUserResource().base_url or settings.BK_USER_API_BASE_URL
    resource = GetDataLink()
    mocker.patch.object(resource, "report_api_request_count_metric")
    response = mocker.Mock()
    response.json.return_value = {"code": 0, "data": {}}
    send = mocker.patch.object(resource.session, "get", return_value=response)
    resource.request(bk_tenant_id="system", namespace="sample", kind="resulttables", name="sample")
    lookup.assert_called_once_with(bk_tenant_id="default", lookups="service-login", lookup_field="login_name")
    args = send.call_args.kwargs
    assert "/v4/namespaces/" in args["url"]
    assert args["headers"]["X-Bk-Tenant-Id"] == "system"
    assert (
        json.loads(args["headers"]["x-bkapi-authorization"])["bk_username"]
        == args["params"]["bk_username"]
        == "virtual-id"
    )


@pytest.mark.parametrize("username", [None, "explicit-user"])
def test_lookup_sends_app_credentials_without_resolving_a_user(settings, mocker, username):
    from api.bk_login.default import BatchLookupVirtualUserResource

    resource = BatchLookupVirtualUserResource()
    mocker.patch("core.drf_resource.contrib.api.make_userinfo", side_effect=AssertionError("recursive user lookup"))
    mocker.patch.object(resource, "report_api_request_count_metric")
    response = mocker.Mock()
    response.json.return_value = {"code": 0, "data": [{"bk_username": "virtual-id"}]}
    send = mocker.patch.object(resource.session, "get", return_value=response)

    user = {"bk_username": username} if username else {}
    assert resource.request(bk_tenant_id="tenant-a", lookup_field="login_name", lookups="service-login", **user) == [
        {"bk_username": "virtual-id"}
    ]
    kwargs = send.call_args.kwargs
    assert json.loads(kwargs["headers"]["x-bkapi-authorization"]) == {
        "bk_app_code": settings.APP_CODE,
        "bk_app_secret": settings.SECRET_KEY,
        **user,
    }
    assert kwargs["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
    assert kwargs["params"] == {"lookup_field": "login_name", "lookups": "service-login"}


def test_query_token_does_not_require_admin_lookup(settings, mocker):
    from api.bkdata.default import QueryDataResource

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_ADMIN_USERNAME = "unavailable"
    settings.BKDATA_DATA_TOKEN = "test-token"
    settings.COMMON_USERNAME = "legacy"
    mocker.patch("api.bkdata.default.get_request_username", return_value=None)
    mocker.patch("api.bkdata.default.get_local_username", return_value=None)
    lookup = mocker.patch.object(api.bk_login, "batch_lookup_virtual_user")
    params = QueryDataResource().full_request_data({"sql": "SELECT 1"})
    assert params["bk_username"] == "legacy"
    assert params["bkdata_authentication_method"] == "token"
    assert params["bkdata_data_token"] == "test-token"
    lookup.assert_not_called()


@pytest.mark.parametrize(
    ("resource_name", "params", "request_user", "local_user", "multi", "token", "expected_user", "lookup_tenant"),
    [
        ("query_data", {}, None, None, True, "", "virtual-user", "query-tenant"),
        ("query_data", {"bk_username": ""}, None, None, True, "", "virtual-user", "query-tenant"),
        ("query_data", {"bk_username": "caller"}, "viewer", None, True, "", "caller", None),
        ("query_data", {}, None, "job-user", True, "", "job-user", None),
        ("query_profile_data", {"_user_request": True}, "viewer", None, True, "test-token", "viewer", None),
        ("query_data", {}, "viewer", None, True, "test-token", "viewer", None),
        ("query_data", {}, None, None, False, "", "virtual-user", "default"),
        ("query_data", {}, None, None, False, "test-token", "legacy", None),
    ],
)
def test_query_sync_outbound_identity(
    settings,
    mocker,
    monkeypatch,
    resource_name,
    params,
    request_user,
    local_user,
    multi,
    token,
    expected_user,
    lookup_tenant,
):
    from bkmonitor.utils.local import local
    from bkmonitor.utils.user import _single_tenant_admin_username
    from core.drf_resource.contrib.api import APIResource

    settings.ENABLE_MULTI_TENANT_MODE = multi
    settings.BK_ADMIN_USERNAME = "query-service-login"
    settings.BKDATA_DATA_TOKEN = token
    settings.COMMON_USERNAME = "legacy"
    settings.SAAS_APP_CODE = "query-app"
    settings.SAAS_SECRET_KEY = "test-key"
    get_admin_username.cache_clear()
    _single_tenant_admin_username.cache_clear()
    request = mocker.Mock(user=mocker.Mock(username=request_user)) if request_user else None
    monkeypatch.setattr(local, "current_request", request, raising=False)
    monkeypatch.setattr(local, "username", local_user, raising=False)
    mocker.patch.object(APIResource, "report_api_request_count_metric")

    lookup_response = mocker.Mock()
    lookup_response.json.return_value = {"code": 0, "data": [{"bk_username": "virtual-user"}]}
    lookup = mocker.patch("requests.sessions.Session.get", return_value=lookup_response)
    query_response = mocker.Mock()
    query_response.json.return_value = {"code": 0, "data": {"list": []}}
    query = mocker.patch("requests.sessions.Session.request", return_value=query_response)

    result = getattr(api.bkdata, resource_name)(sql="SELECT 1", bk_tenant_id="query-tenant", **params)

    assert result == {"list": []}
    query.assert_called_once()
    outbound = query.call_args.kwargs
    assert outbound["url"].endswith("/v3/queryengine/query_sync/")
    assert outbound["headers"]["X-Bk-Tenant-Id"] == "query-tenant"
    assert json.loads(outbound["headers"]["x-bkapi-authorization"]) == {
        "bk_app_code": "query-app",
        "bk_app_secret": "test-key",
        "bk_username": expected_user,
    }
    assert outbound["json"]["bk_username"] == expected_user
    token_auth = token and not params.get("_user_request")
    assert outbound["json"]["bkdata_authentication_method"] == ("token" if token_auth else "user")
    assert outbound["json"].get("bkdata_data_token") == (token if token_auth else None)
    if lookup_tenant:
        lookup.assert_called_once()
        assert lookup.call_args.kwargs["headers"]["X-Bk-Tenant-Id"] == lookup_tenant
        assert lookup.call_args.kwargs["params"] == {"lookup_field": "login_name", "lookups": "query-service-login"}
    else:
        lookup.assert_not_called()
