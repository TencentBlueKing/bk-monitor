"""仪表盘只读配置、受管应用授权、完整响应与凭据脱敏回归。"""

from __future__ import annotations

import copy
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from django.conf import settings

from api.grafana import default
from api.grafana.default import GetDashboardByUID, GetOrganizationByName
from core.drf_resource import api
from kernel_api.middlewares import authentication
from kernel_api.rpc.functions.bkm_cli.platform_catalog import _authorization, grafana
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import (
    ParamsGuardRejected,
    PlatformSourceCatalog,
    ProviderResponseRejected,
)
from kernel_api.rpc.functions.bkm_cli.platform_source import query_platform_source


@pytest.fixture(autouse=True)
def catalog(mocker):
    snapshot = dict(PlatformSourceCatalog._domains)
    PlatformSourceCatalog.reset()
    grafana.register()
    request = SimpleNamespace(
        user=SimpleNamespace(tenant_id="tenant-a", is_authenticated=True),
        biz_id=None,
        META={"HTTP_BK_APP_CODE": "test-app"},
    )
    mocker.patch.object(_authorization, "get_request", return_value=request)
    mocker.patch.object(_authorization, "bk_biz_id_to_bk_tenant_id", return_value="tenant-a")
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {"test-app": ["biz#2"]}})
    mocker.patch.object(authentication, "APP_CODE_UPDATE_TIME", {"tenant-a": time.time()})
    mocker.patch.object(settings, "GRAFANA_URL", "https://grafana.example.test")
    org = mocker.patch.object(grafana.Org.objects, "filter")
    org.return_value.values.return_value.first.return_value = {"id": 12}
    yield request, org
    PlatformSourceCatalog._domains = snapshot
    PlatformSourceCatalog._revision = None


def invoke(params=None, **outer):
    return query_platform_source(
        {
            "mode": "invoke",
            "domain": "grafana",
            "operation": "get_dashboard",
            "params": {"bk_biz_id": 2, "dashboard_uid": "example-dashboard"} if params is None else params,
            **outer,
        }
    )


def saved_dashboard():
    panel = {
        "id": 2,
        "targets": [{"refId": "A", "expr": 'up{job="$job"}', "hide": True}],
        "datasource": {"type": "prometheus", "uid": "example-source"},
        "transformations": [{"id": "limit", "options": {"limit": 10}}],
        "timeFrom": "1h",
        "fieldConfig": {"defaults": {"unit": "short"}},
    }
    return {
        "result": True,
        "code": 200,
        "message": "",
        "data": {
            "dashboard": {
                "uid": "example-dashboard",
                "id": 1,
                "version": 3,
                "title": "Example",
                "panels": [{"id": 1, "type": "row", "collapsed": True, "panels": [panel]}],
                "rows": [{"panels": [copy.deepcopy(panel)]}],
                "templating": {"list": [{"name": "job", "current": {"text": "All", "value": "$__all"}}]},
                "time": {"from": "now-1h", "to": "now"},
                "refresh": "30s",
                "timezone": "browser",
            },
            "meta": {"folderId": 0, "folderUid": "example-folder", "createdBy": "private-user", "url": "drop"},
        },
    }


def handler(raw=None):
    op = PlatformSourceCatalog.get_domain("grafana").operations["get_dashboard"]
    op.handler = Mock(return_value=saved_dashboard() if raw is None else raw)
    return op.handler


def test_catalog_discovery_schema_and_fixed_native_handler():
    op = PlatformSourceCatalog.get_domain("grafana").operations["get_dashboard"]
    assert op.handler is api.grafana.get_dashboard_by_uid
    assert isinstance(op.handler, GetDashboardByUID)
    domains = query_platform_source({"mode": "discover"})["domains"]
    assert domains[0]["id"] == "grafana" and domains[0]["operations_count"] == 1
    operations = query_platform_source({"mode": "discover", "domain": "grafana"})["operations"]
    assert operations[0]["id"] == "get_dashboard"
    schema = query_platform_source({"mode": "describe", "domain": "grafana", "operation": "get_dashboard"})
    assert set(schema["params_schema"]["properties"]) == {"bk_biz_id", "dashboard_uid"}
    assert schema["params_schema"]["additionalProperties"] is False
    assert schema["params_schema"]["properties"]["dashboard_uid"]["maxLength"] == 40
    assert "current_saved" in schema["notes"]
    assert grafana.MAX_CONFIG_BYTES == 10 * 1024 * 1024


def test_single_provider_call_and_complete_config_are_preserved(catalog):
    request, org = catalog
    raw = saved_dashboard()
    call = handler(raw)
    result = invoke()["result"]
    call.assert_called_once_with(uid="example-dashboard", org_id=12, bk_biz_id=2, bk_tenant_id="tenant-a")
    org.assert_called_once_with(name="2")
    org.return_value.values.assert_called_once_with("id")
    assert result["dashboard"] == raw["data"]["dashboard"]
    assert result["dashboard"]["panels"][0]["panels"][0]["transformations"][0]["options"]["limit"] == 10
    assert result["dashboard"]["panels"][0]["panels"][0]["targets"][0]["hide"] is True
    assert result["configuration_scope"] == "current_saved"
    assert result["meta"] == {"folderId": 0, "folderUid": "example-folder"}
    assert result["source"] == {
        "bk_biz_id": 2,
        "bk_tenant_id": "tenant-a",
        "org_id": 12,
        "dashboard_uid": "example-dashboard",
        "fetched_at": result["source"]["fetched_at"],
    }
    assert result["redacted"] is False and result["redacted_paths"] == []
    assert request.biz_id is None


def test_real_resource_get_uses_server_org_fixed_timeout_and_serializer(mocker):
    response = Mock(status_code=200)
    response.json.return_value = saved_dashboard()["data"]
    call = mocker.patch.object(default.requests, "request", return_value=response)
    resource = GetDashboardByUID()
    params = resource.validate_request_data(
        grafana.guard_get_dashboard({"bk_biz_id": 2, "dashboard_uid": "example-dashboard"})
    )
    assert params == {"org_id": 12, "uid": "example-dashboard"}
    assert resource.perform_request(params)["data"] == response.json.return_value
    call.assert_called_once_with(
        method="GET",
        url="https://grafana.example.test/api/dashboards/uid/example-dashboard",
        headers={"X-WEBAUTH-USER": "admin", "X-Grafana-Org-Id": "12"},
        timeout=(3, 10),
        params={"uid": "example-dashboard"},
    )


@pytest.mark.parametrize(
    "uid",
    [
        None,
        1,
        "",
        "x" * 41,
        "../x",
        "x/y",
        "x%2fy",
        "x?orgId=3",
        "x#test",
        " x",
        "x\n",
        "https://example.test/x",
        "测试",
    ],
)
def test_uid_path_injection_is_rejected_before_org_or_provider(catalog, uid):
    call = handler()
    assert invoke({"bk_biz_id": 2, "dashboard_uid": uid})["error"]["code"] == "unsafe_action_blocked"
    catalog[1].assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize("biz", [None, 0, -1, True, "2", 2.0, []])
def test_business_must_be_positive_integer(catalog, biz):
    call = handler()
    assert invoke({"bk_biz_id": biz, "dashboard_uid": "example-dashboard"})["error"]["code"] == "unsafe_action_blocked"
    catalog[1].assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize(
    "key", ["org_id", "url", "username", "headers", "bk_tenant_id", "fields", "uid", "timeout", "_user_request"]
)
def test_unknown_or_hidden_params_are_rejected(catalog, key):
    call = handler()
    assert (
        invoke({"bk_biz_id": 2, "dashboard_uid": "example-dashboard", key: "override"})["error"]["code"]
        == "unsafe_action_blocked"
    )
    catalog[1].assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize("params", [None, [], "x", 1, True])
def test_guard_is_total_for_non_objects(params):
    with pytest.raises(ParamsGuardRejected):
        grafana.guard_get_dashboard(params)


@pytest.mark.parametrize("missing", ["request", "authenticated", "tenant", "app"])
def test_missing_trusted_request_context_denies_before_org(mocker, catalog, missing):
    request, org = catalog
    if missing == "request":
        mocker.patch.object(_authorization, "get_request", return_value=None)
    elif missing == "authenticated":
        request.user.is_authenticated = False
    elif missing == "tenant":
        request.user.tenant_id = None
    else:
        request.META.clear()
    call = handler()
    assert invoke()["error"]["code"] == "unsafe_action_blocked"
    org.assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize("business,allowed", [(2, True), (3, False)])
def test_jwt_app_identity_takes_priority_over_header(catalog, business, allowed):
    request, org = catalog
    request.jwt = SimpleNamespace(app=SimpleNamespace(app_code="test-app"))
    request.META["HTTP_BK_APP_CODE"] = "unconfigured-app"
    call = handler()
    result = invoke({"bk_biz_id": business, "dashboard_uid": "example-dashboard"})
    assert (result["status"] == "ok") == allowed
    if not allowed:
        assert result["error"]["code"] == "unsafe_action_blocked"
    assert call.call_count == org.call_count == int(allowed)


def test_unconfigured_app_compatibility_and_all_business_semantics(mocker):
    call = handler()
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {}})
    assert invoke()["status"] == "ok"
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {"test-app": ["biz#all"]}})
    assert invoke({"bk_biz_id": 3, "dashboard_uid": "example-dashboard"})["status"] == "ok"
    assert call.call_count == 2


@pytest.mark.parametrize("mismatch", ["tenant", "outer-biz", "business-permission"])
def test_identity_scope_mismatch_denies_before_org(mocker, catalog, mismatch):
    request, org = catalog
    if mismatch == "tenant":
        mocker.patch.object(_authorization, "bk_biz_id_to_bk_tenant_id", return_value="tenant-b")
    elif mismatch == "outer-biz":
        request.biz_id = 3
    params = {"bk_biz_id": 3 if mismatch == "business-permission" else 2, "dashboard_uid": "example-dashboard"}
    call = handler()
    assert invoke(params, bk_biz_id=2)["error"]["code"] == "unsafe_action_blocked"
    org.assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize(
    "namespaces,expired,allowed",
    [(["biz#2"], False, True), (["biz#all"], False, True), (["biz#3"], False, False), (["biz#2"], True, False)],
)
def test_bearer_namespace_expiration_and_jwt_combination_keep_existing_contract(
    mocker, catalog, namespaces, expired, allowed
):
    request, org = catalog
    request.META["HTTP_AUTHORIZATION"] = "Bearer local-test-token"
    request.jwt = SimpleNamespace(app=SimpleNamespace(app_code="test-app"))
    record = _authorization.ApiAuthToken(namespaces=namespaces)
    mocker.patch.object(record, "is_expired", return_value=expired)
    lookup = mocker.patch.object(_authorization.ApiAuthToken.objects, "filter")
    lookup.return_value.first.return_value = record
    call = handler()
    result = invoke()
    assert (result["status"] == "ok") == allowed
    lookup.assert_called_once_with(token="local-test-token", bk_tenant_id="tenant-a")
    assert call.call_count == org.call_count == int(allowed)


def test_missing_bearer_record_never_falls_back_to_app(mocker, catalog):
    request, org = catalog
    request.META["HTTP_AUTHORIZATION"] = "Bearer local-test-token"
    lookup = mocker.patch.object(_authorization.ApiAuthToken.objects, "filter")
    lookup.return_value.first.return_value = None
    call = handler()
    assert invoke()["error"]["code"] == "unsafe_action_blocked"
    org.assert_not_called()
    call.assert_not_called()


def test_permission_lookup_failure_is_safe_error(mocker, catalog):
    mocker.patch.object(_authorization, "is_match_api_token", side_effect=RuntimeError("secret=never-return"))
    call = handler()
    result = invoke()
    assert result["error"]["code"] == "unsafe_action_blocked"
    assert "never-return" not in json.dumps(result)
    catalog[1].assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize(
    "org,code",
    [
        (None, "target_not_found"),
        ({}, "provider_unavailable"),
        ({"id": True}, "provider_unavailable"),
        ({"id": 0}, "provider_unavailable"),
    ],
)
def test_missing_or_invalid_org_never_calls_provider(catalog, org, code):
    catalog[1].return_value.values.return_value.first.return_value = org
    call = handler()
    assert invoke()["error"]["code"] == code
    call.assert_not_called()


def test_org_storage_failure_has_fixed_error(catalog):
    catalog[1].side_effect = RuntimeError("secret=never-return")
    call = handler()
    result = invoke()
    assert result["error"]["code"] == "provider_unavailable"
    assert "never-return" not in json.dumps(result)
    call.assert_not_called()


@pytest.mark.parametrize("url", [None, "", "relative/path", "ftp://example.test"])
def test_missing_service_configuration_is_not_empty_success(mocker, catalog, url):
    mocker.patch.object(settings, "GRAFANA_URL", url)
    call = handler()
    assert invoke()["error"]["code"] == "provider_unavailable"
    catalog[1].assert_not_called()
    call.assert_not_called()


@pytest.mark.parametrize(
    "code,expected",
    [
        (404, "target_not_found"),
        (401, "unauthorized"),
        (403, "unauthorized"),
        (500, "provider_unavailable"),
        (200, "provider_unavailable"),
    ],
)
def test_false_envelope_is_explicit_error_without_upstream_message(code, expected):
    call = handler({"result": False, "code": code, "message": "secret=never-return", "data": None})
    result = invoke()
    assert result["error"]["code"] == expected
    assert "never-return" not in json.dumps(result)
    assert "result" not in result
    call.assert_called_once()


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        {},
        {"result": True},
        {"result": True, "code": "200"},
        {"result": 1, "code": 200},
        {"result": True, "code": 200, "data": None},
    ],
)
def test_bad_envelope_never_succeeds(raw):
    call = handler()
    call.return_value = raw
    assert invoke()["error"]["code"] == "provider_unavailable"


@pytest.mark.parametrize(
    "key,value",
    [
        ("uid", None),
        ("uid", "other-dashboard"),
        ("id", None),
        ("id", True),
        ("id", 0),
        ("version", None),
        ("version", True),
        ("version", 0),
        ("panels", None),
        ("panels", {}),
        ("panels", [None]),
        ("panels", [{"panels": None}]),
    ],
)
def test_invalid_or_half_dashboard_is_rejected(key, value):
    raw = saved_dashboard()
    raw["data"]["dashboard"][key] = value
    handler(raw)
    assert invoke()["error"]["code"] == "provider_unavailable"


def test_oversized_response_is_rejected_whole(mocker):
    raw = saved_dashboard()
    raw["data"]["dashboard"]["description"] = "x" * 1024
    mocker.patch.object(grafana, "MAX_CONFIG_BYTES", 1024)
    handler(raw)
    result = invoke()
    assert result["error"]["code"] == "unsafe_action_blocked" and "result" not in result


def test_output_identity_and_redaction_paths_share_the_size_budget(mocker):
    raw = saved_dashboard()
    raw["data"]["dashboard"]["password"] = "test"
    raw_size = len(json.dumps(raw["data"], ensure_ascii=False, separators=(",", ":")).encode())
    mocker.patch.object(grafana, "MAX_CONFIG_BYTES", raw_size + 1)
    handler(raw)
    assert invoke()["error"]["code"] == "unsafe_action_blocked"


def test_credentials_keys_urls_text_and_name_value_headers_are_redacted_without_mutation():
    raw = saved_dashboard()
    raw["data"]["dashboard"]["annotations"] = {
        "password": "never-return-password",
        "url": "https://user:never-return-url@example.test/path",
        "text": "request Authorization: Bearer never-return-text",
        "headers": [
            {"name": "Authorization", "value": "never-return-header"},
            {"name": "X-Api-Key", "value": "never-return-key"},
            {"name": "Accept", "value": "application/json"},
        ],
        "enabled": True,
    }
    before = copy.deepcopy(raw)
    handler(raw)
    result = invoke()["result"]
    serialized = json.dumps(result)
    assert "never-return" not in serialized
    assert result["redacted"] is True
    assert set(result["redacted_paths"]) == {
        "/dashboard/annotations/password",
        "/dashboard/annotations/url",
        "/dashboard/annotations/text",
        "/dashboard/annotations/headers/0/value",
        "/dashboard/annotations/headers/1/value",
    }
    assert result["dashboard"]["annotations"]["headers"][2]["value"] == "application/json"
    assert result["dashboard"]["panels"] == raw["data"]["dashboard"]["panels"]
    assert raw == before


@pytest.mark.parametrize(
    "text",
    [
        '{"password": "never-return"}',
        "token=never-return",
        "https://never-return@example.test/path",
        "https://example.test/path?api_key=never-return",
        "Authorization: Basic bmV2ZXItcmV0dXJu",
    ],
)
def test_free_text_credentials_are_redacted(text):
    raw = saved_dashboard()
    raw["data"]["dashboard"]["description"] = text
    handler(raw)
    result = invoke()["result"]
    assert result["dashboard"]["description"] == grafana.REDACTED_VALUE
    assert result["redacted_paths"] == ["/dashboard/description"]


def test_sensitive_named_template_variable_masks_actual_values_and_keeps_structure():
    raw = saved_dashboard()
    variable = {
        "name": "api_key",
        "type": "constant",
        "query": "never-return",
        "current": {"text": "never-return", "value": "never-return", "selected": True},
        "options": [{"text": "never-return", "value": "never-return", "selected": True}],
        "hide": 2,
    }
    raw["data"]["dashboard"]["templating"]["list"].append(variable)
    original = copy.deepcopy(raw)
    handler(raw)
    result = invoke()["result"]
    redacted = result["dashboard"]["templating"]["list"][1]
    assert "never-return" not in json.dumps(result)
    assert redacted == {
        "name": "api_key",
        "type": "constant",
        "query": grafana.REDACTED_VALUE,
        "current": {"text": grafana.REDACTED_VALUE, "value": grafana.REDACTED_VALUE, "selected": True},
        "options": [{"text": grafana.REDACTED_VALUE, "value": grafana.REDACTED_VALUE, "selected": True}],
        "hide": 2,
    }
    assert set(result["redacted_paths"]) == {
        "/dashboard/templating/list/1/query",
        "/dashboard/templating/list/1/current/text",
        "/dashboard/templating/list/1/current/value",
        "/dashboard/templating/list/1/options/0/text",
        "/dashboard/templating/list/1/options/0/value",
    }
    assert result["dashboard"]["templating"]["list"][0] == original["data"]["dashboard"]["templating"]["list"][0]
    assert raw == original


@pytest.mark.parametrize("exception", [requests.ConnectTimeout, requests.ReadTimeout])
def test_fixed_timeout_maps_to_domain_unreachable_without_exception_value(mocker, exception):
    request = mocker.patch.object(default.requests, "request", side_effect=exception("secret=never-return"))
    handler().side_effect = lambda **params: GetDashboardByUID().perform_request(
        {"uid": params["uid"], "org_id": params["org_id"]}
    )
    result = invoke()
    assert result["error"] == {"code": "domain_unreachable", "message": "Grafana 仪表盘读取超时"}
    request.assert_called_once()


def native_handler():
    handler().side_effect = lambda **params: GetDashboardByUID().perform_request(
        {"uid": params["uid"], "org_id": params["org_id"]}
    )


@pytest.mark.parametrize("exception", [requests.ConnectionError, requests.exceptions.InvalidURL])
def test_non_timeout_provider_exception_has_fixed_message(mocker, exception):
    call = mocker.patch.object(default.requests, "request", side_effect=exception("secret=never-return"))
    native_handler()
    assert invoke()["error"] == {"code": "provider_unavailable", "message": "Grafana 仪表盘请求失败"}
    call.assert_called_once()


def test_non_json_success_has_fixed_message(mocker):
    response = Mock(status_code=200)
    response.json.side_effect = requests.JSONDecodeError("never-return", "secret=never-return", 0)
    mocker.patch.object(default.requests, "request", return_value=response)
    native_handler()
    assert invoke()["error"] == {"code": "provider_unavailable", "message": "Grafana 仪表盘响应不是有效 JSON"}


@pytest.mark.parametrize(
    "code,expected",
    [(404, "target_not_found"), (401, "unauthorized"), (403, "unauthorized"), (500, "provider_unavailable")],
)
@pytest.mark.parametrize("body", [{"secret": "never-return"}, None, ["never-return"]])
def test_failed_native_response_does_not_parse_or_expose_nonstandard_body(mocker, code, expected, body):
    response = Mock(status_code=code, content=b"secret=never-return")
    response.json.return_value = body
    mocker.patch.object(default.requests, "request", return_value=response)
    native_handler()
    result = invoke()
    assert result["error"]["code"] == expected
    assert "never-return" not in json.dumps(result)
    response.json.assert_not_called()


def test_other_grafana_resources_keep_original_timeout_behavior(mocker):
    call = mocker.patch.object(default.requests, "request", return_value=Mock(status_code=200))
    GetOrganizationByName().perform_request({"name": "2", "timeout": 99})
    assert "timeout" not in call.call_args.kwargs
    assert GetOrganizationByName.timeout is None


def test_other_grafana_resources_preserve_original_exception_and_error_body(mocker):
    call = mocker.patch.object(default.requests, "request", side_effect=requests.ConnectionError("original"))
    with pytest.raises(requests.ConnectionError, match="original"):
        GetOrganizationByName().perform_request({"name": "2"})
    call.side_effect = None
    call.return_value = Mock(status_code=404)
    call.return_value.json.return_value = {"message": "original"}
    assert GetOrganizationByName().perform_request({"name": "2"})["message"] == "original"
    assert GetOrganizationByName.redact_errors is False


def test_catalog_error_classes_keep_legacy_defaults_and_optional_codes():
    assert ParamsGuardRejected("blocked").code == "unsafe_action_blocked"
    assert ProviderResponseRejected("failed").code == "provider_unavailable"
    assert ParamsGuardRejected("denied", code="unauthorized").code == "unauthorized"
    assert ProviderResponseRejected("missing", code="target_not_found").code == "target_not_found"
