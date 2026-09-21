"""CMDB 单页原生请求、应用 / Token 授权与响应完整性回归。"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings

from api.cmdb import client
from api.cmdb.client import ListBizHosts
from kernel_api.middlewares import authentication
from kernel_api.rpc.functions.bkm_cli.platform_catalog import cmdb
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import (
    ParamsGuardRejected,
    PlatformSourceCatalog,
)
from kernel_api.rpc.functions.bkm_cli.platform_source import query_platform_source


@pytest.fixture(autouse=True)
def catalog(mocker):
    snapshot = dict(PlatformSourceCatalog._domains)
    PlatformSourceCatalog.reset()
    cmdb.register()
    request = SimpleNamespace(
        user=SimpleNamespace(tenant_id="tenant-a", is_authenticated=True),
        biz_id=None,
        META={"HTTP_BK_APP_CODE": "test-app"},
    )
    mocker.patch.object(cmdb, "get_request", return_value=request)
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {"test-app": ["biz#2"]}})
    mocker.patch.object(authentication, "APP_CODE_UPDATE_TIME", {"tenant-a": time.time()})
    yield request
    PlatformSourceCatalog._domains = snapshot
    PlatformSourceCatalog._revision = None


def invoke(params, **outer):
    return query_platform_source(
        {"mode": "invoke", "domain": "cmdb", "operation": "list_biz_hosts", "params": params, **outer}
    )


def host(host_id=1):
    return {
        "bk_host_id": host_id,
        "bk_cloud_id": 0,
        "bk_host_innerip": "",
        "bk_host_innerip_v6": "",
        "bk_host_name": "",
    }


def handler():
    op = PlatformSourceCatalog.get_domain("cmdb").operations["list_biz_hosts"]
    op.handler = Mock(return_value={"count": 0, "info": []})
    return op.handler


def test_registration_binds_native_resource_and_fixed_contract():
    domain = PlatformSourceCatalog.get_domain("cmdb")
    assert set(domain.operations) == {"list_biz_hosts"}
    op = domain.operations["list_biz_hosts"]
    assert op.handler is cmdb.list_biz_hosts
    assert isinstance(op.handler, ListBizHosts)
    assert "perform_request" not in ListBizHosts.__dict__
    assert op.default_fields == op.allowed_fields == list(cmdb.HOST_FIELDS)
    described = query_platform_source({"mode": "describe", "domain": "cmdb", "operation": "list_biz_hosts"})
    assert set(described["params_schema"]["properties"]) == {"bk_biz_id", "page", "page_size"}
    assert described["params_schema"]["additionalProperties"] is False
    assert "快照" in described["notes"]


def test_second_page_is_single_native_request_and_preserves_total(catalog):
    call = handler()
    call.return_value = {"count": 3, "info": [host(3)], "secret": "omit"}
    result = invoke({"bk_biz_id": 2, "page": 2, "page_size": 2})
    call.assert_called_once_with(
        bk_biz_id=2,
        bk_tenant_id="tenant-a",
        fields=list(cmdb.HOST_FIELDS),
        page={"start": 2, "limit": 2, "sort": "bk_host_id"},
    )
    assert result["result"] == {
        "count": 3,
        "info": [host(3)],
        "page": 2,
        "page_size": 2,
        "has_more": False,
        "is_snapshot": False,
    }
    assert catalog.biz_id is None


def test_native_resource_forwards_one_page_and_verified_tenant_header(mocker):
    params = cmdb.guard_list_biz_hosts({"bk_biz_id": 2, "page": 3, "page_size": 50})
    mocker.patch.object(settings, "ENABLE_MULTI_TENANT_MODE", True)
    mocker.patch.object(settings, "CMDB_API_BASE_URL", "https://cmdb.example.test")
    mocker.patch.object(client, "get_backend_username", return_value="backend-user")
    mocker.patch.object(client, "validate_bk_biz_id", side_effect=lambda value: value)
    resource = ListBizHosts()
    resource.session = Mock()
    resource.session.request.return_value.json.return_value = {
        "result": True,
        "code": 0,
        "data": {"count": 100, "info": []},
    }
    mocker.patch.object(resource, "record_request_data_to_span")
    mocker.patch.object(resource, "report_api_request_count_metric")
    assert resource.perform_request(params) == {"count": 100, "info": []}
    resource.session.request.assert_called_once()
    sent = resource.session.request.call_args.kwargs
    assert sent["method"] == "POST"
    assert sent["url"] == "https://cmdb.example.test/api/v3/hosts/app/2/list_hosts"
    assert sent["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
    assert sent["json"]["page"] == {"start": 100, "limit": 50, "sort": "bk_host_id"}
    assert sent["json"]["fields"] == list(cmdb.HOST_FIELDS)


def test_empty_and_beyond_last_pages_remain_real_zero_or_original_count():
    call = handler()
    assert invoke({"bk_biz_id": 2})["result"]["count"] == 0
    call.return_value = {"count": 7, "info": []}
    result = invoke({"bk_biz_id": 2, "page": 2})["result"]
    assert result["count"] == 7 and result["info"] == [] and result["has_more"] is False


def test_default_limit_and_empty_ip_hosts_are_not_dropped():
    call = handler()
    call.return_value = {"count": 1, "info": [{**host(), "operator": "private", "custom": "private"}]}
    result = invoke({"bk_biz_id": 2})["result"]
    assert result["info"] == [host()]
    assert call.call_args.kwargs["page"] == {"start": 0, "limit": 50, "sort": "bk_host_id"}


def test_null_cmdb_text_fields_are_preserved():
    call = handler()
    item = {**host(), "bk_host_innerip": None, "bk_host_innerip_v6": None, "bk_host_name": None}
    call.return_value = {"count": 1, "info": [item]}
    assert invoke({"bk_biz_id": 2})["result"]["info"] == [item]


@pytest.mark.parametrize("field", cmdb.HOST_FIELDS[2:])
def test_nested_objects_cannot_escape_in_fixed_text_fields(field):
    call = handler()
    call.return_value = {"count": 1, "info": [{**host(), field: {"private": "value"}}]}
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "provider_unavailable"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"bk_biz_id": 0},
        {"bk_biz_id": -1},
        {"bk_biz_id": True},
        {"bk_biz_id": "2"},
        {"bk_biz_id": 2, "page": 0},
        {"bk_biz_id": 2, "page": []},
        {"bk_biz_id": 2, "page": True},
        {"bk_biz_id": 2, "page_size": 0},
        {"bk_biz_id": 2, "page_size": 501},
        {"bk_biz_id": 2, "page_size": 1.5},
        {"bk_biz_id": 2, "page_size": None},
    ],
)
def test_invalid_public_params_never_call_provider(params):
    call = handler()
    assert invoke(params)["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


@pytest.mark.parametrize(
    "key", ["fields", "sort", "host_property_filter", "bk_tenant_id", "bk_username", "_user_request"]
)
def test_hidden_or_unbounded_params_are_rejected(key):
    call = handler()
    assert invoke({"bk_biz_id": 2, key: "override"})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


@pytest.mark.parametrize("params", [None, [], "x", 1, True])
def test_guard_handles_arbitrary_input_types(params):
    with pytest.raises(ParamsGuardRejected):
        cmdb.guard_list_biz_hosts(params)


def test_page_limit_official_boundary():
    assert cmdb.guard_list_biz_hosts({"bk_biz_id": 2, "page_size": 500})["page"]["limit"] == 500


def test_real_app_token_namespace_check_denies_other_business():
    call = handler()
    # Same tenant, different business: tenant validation is not business authorization.
    assert invoke({"bk_biz_id": 3})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


def test_real_app_token_all_business_semantics(mocker):
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {"test-app": ["biz#all"]}})
    assert cmdb.guard_list_biz_hosts({"bk_biz_id": 3})["bk_biz_id"] == 3


def test_unconfigured_app_preserves_existing_app_token_semantics(mocker):
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {}})
    assert cmdb.guard_list_biz_hosts({"bk_biz_id": 2})["bk_biz_id"] == 2


def test_jwt_app_takes_priority_over_header(catalog):
    catalog.jwt = SimpleNamespace(app=SimpleNamespace(app_code="test-app"))
    catalog.META["HTTP_BK_APP_CODE"] = "unregistered-app"
    with pytest.raises(ParamsGuardRejected):
        cmdb.guard_list_biz_hosts({"bk_biz_id": 3})


@pytest.mark.parametrize("missing", ["request", "authenticated", "tenant", "app"])
def test_missing_trusted_context_is_rejected(mocker, catalog, missing):
    if missing == "request":
        mocker.patch.object(cmdb, "get_request", return_value=None)
    elif missing == "authenticated":
        catalog.user.is_authenticated = False
    elif missing == "tenant":
        catalog.user.tenant_id = None
    else:
        catalog.META.clear()
    call = handler()
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


def test_foreign_tenant_is_rejected_before_provider(mocker):
    mocker.patch.object(cmdb, "bk_biz_id_to_bk_tenant_id", return_value="tenant-b")
    call = handler()
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


def test_conflicting_request_business_is_rejected(catalog):
    catalog.biz_id = 3
    call = handler()
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


def test_outer_params_cannot_authorize_inner_business():
    call = handler()
    assert invoke({"bk_biz_id": 3}, bk_biz_id=2, bk_tenant_id="tenant-a")["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


@pytest.mark.parametrize(
    "namespaces,expired,expected",
    [(["biz#2"], False, True), (["biz#all"], False, True), (["biz#3"], False, False), (["biz#2"], True, False)],
)
def test_bearer_token_rechecks_namespace_and_expiration(mocker, catalog, namespaces, expired, expected):
    catalog.META["HTTP_AUTHORIZATION"] = "Bearer local-test-token"
    record = cmdb.ApiAuthToken(namespaces=namespaces)
    mocker.patch.object(record, "is_expired", return_value=expired)
    lookup = mocker.patch.object(cmdb.ApiAuthToken.objects, "filter")
    lookup.return_value.first.return_value = record
    call = handler()
    result = invoke({"bk_biz_id": 2})
    assert (result["status"] == "ok") == expected
    lookup.assert_called_once_with(token="local-test-token", bk_tenant_id="tenant-a")
    assert call.call_count == int(expected)


def test_foreign_or_missing_bearer_token_does_not_fall_back_to_app(mocker, catalog):
    catalog.META["HTTP_AUTHORIZATION"] = "Bearer local-test-token"
    lookup = mocker.patch.object(cmdb.ApiAuthToken.objects, "filter")
    lookup.return_value.first.return_value = None
    call = handler()
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


@pytest.mark.parametrize("prefix", ["bearer", "bEaReR"])
def test_nonstandard_bearer_cannot_change_the_middleware_auth_path(mocker, catalog, prefix):
    catalog.META["HTTP_AUTHORIZATION"] = f"{prefix} view-restricted-token"
    lookup = mocker.patch.object(cmdb.ApiAuthToken.objects, "filter")
    call = handler()
    # AuthenticationMiddleware ignores this header spelling, so the app's biz#2
    # restriction must still apply. No token lookup can replace that decision.
    assert invoke({"bk_biz_id": 3})["error"]["code"] == "unsafe_action_blocked"
    lookup.assert_not_called()
    call.assert_not_called()


def test_permission_storage_failure_fails_closed(mocker):
    mocker.patch.object(cmdb, "is_match_api_token", side_effect=RuntimeError("unavailable"))
    call = handler()
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "unsafe_action_blocked"
    call.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"info": []},
        {"count": True, "info": []},
        {"count": float("nan"), "info": []},
        {"count": -1, "info": []},
        {"count": 0},
        {"count": 2, "info": []},
        {"count": 1, "info": [{"bk_host_id": 1}]},
        {"count": 1, "info": [{**host(), "bk_host_id": True}]},
        {"count": 1, "info": [host()], "is_partial": True},
        {"count": 2, "info": [host(), host()]},
        {"count": 2, "info": [host(2), host(1)]},
    ],
)
def test_malformed_or_incomplete_response_is_not_empty_success(raw):
    call = handler()
    call.return_value = raw
    result = invoke({"bk_biz_id": 2})
    assert result["status"] == "error"
    assert result["error"]["code"] == "provider_unavailable"
    assert "result" not in result


def test_provider_exception_and_timeout_remain_errors():
    call = handler()
    call.side_effect = RuntimeError("failed")
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "provider_unavailable"
    call.side_effect = TimeoutError("timeout")
    assert invoke({"bk_biz_id": 2})["error"]["code"] == "domain_unreachable"
