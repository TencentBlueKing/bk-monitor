"""Regression coverage for V3 compatibility; no real IAM, broker or DB writes."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cachetools import TTLCache
from iam import IAM
from iam.exceptions import AuthAPIError
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum, drf
from bkmonitor.iam import permission as pm
from bkmonitor.iam.backends import config
from bkmonitor.iam.backends.v3.client import V3Client
from core.errors.iam import ActionNotExistError
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from monitor_web.iam.views import IAMViewSet


@pytest.fixture
def setup_v3(monkeypatch):
    config._v3_clients.clear()
    options = {
        "base_url": "https://iam.example.test/",
        "credentials": {"app_code": "offline", "app_secret": "offline-only"},
        "system": {"id": "bk_monitorv3", "name": "Monitor"},
        "bk_tenant_id": "system",
        "enable_v1_compat": False,
        "fallback_apply_url": "https://iam.example.test/saas/",
    }
    monkeypatch.setattr(config, "provider_options", lambda name, tenant: options)
    monkeypatch.setattr(pm, "get_mode_provider", lambda: Mock(get_mode=Mock(return_value=AuthMode.V3)))
    monkeypatch.setattr(pm, "get_request", lambda **kwargs: None)
    monkeypatch.setattr(drf, "get_request", lambda **kwargs: None)
    monkeypatch.setattr("django.conf.settings.SKIP_IAM_PERMISSION_CHECK", False)
    monkeypatch.setattr("bkmonitor.iam.handlers.resolver.MonitorResourceResolver.resolve", lambda self, r, **kw: r)
    monkeypatch.setattr(
        "monitor_web.iam.views.ApmApplicationProvider._get_app_simple_info_by_id_or_none",
        lambda application_id: {"application_id": application_id, "app_name": "offline-app", "bk_biz_id": 2},
    )
    yield options
    config._v3_clients.clear()


def permission():
    return Permission(username="offline-user", bk_tenant_id="system")


def test_read_cache_survives_permission_instances_and_expires(setup_v3, monkeypatch):
    calls = Mock(side_effect=[True, False])
    monkeypatch.setattr(IAM, "is_allowed", calls)
    first, second = permission(), permission()
    client = first.get_provider("v3").client
    now = [0]
    client._allowed_cache = TTLCache(maxsize=1024, ttl=10, timer=lambda: now[0])
    resource = ResourceInstance("space", "2")
    assert first.is_allowed(ActionEnum.VIEW_BUSINESS, [resource]) is True
    assert second.is_allowed(ActionEnum.VIEW_BUSINESS, [resource]) is True
    assert second.get_provider("v3").client is client
    assert calls.call_count == 1
    now[0] = 11
    assert permission().is_allowed(ActionEnum.VIEW_BUSINESS, [resource]) is False
    assert calls.call_count == 2


@pytest.mark.parametrize("change", ["tenant", "code", "secret", "gateway", "system", "codec", "compat"])
def test_shared_client_isolation(setup_v3, change):
    first = config.build_provider("v3").client
    options = deepcopy(setup_v3)
    tenant = "system"
    if change == "tenant":
        options["bk_tenant_id"] = tenant = "another-tenant"
    elif change in {"code", "secret"}:
        options["credentials"]["app_code" if change == "code" else "app_secret"] = "rotated"
    elif change == "gateway":
        options["base_url"] = "https://other.example.test/"
    elif change == "system":
        options["system"]["id"] = "another-system"
    elif change == "codec":
        options["codec_kwargs"] = {"action_id_map": {"view_business": "other-action"}}
    else:
        options["enable_v1_compat"] = True
    assert config.build_provider("v3", tenant, options=options).client is not first


def rows_and_actions():
    return [{"id": 7}, {"id": 8}], [ActionEnum.VIEW_APM_APPLICATION, ActionEnum.MANAGE_APM_APPLICATION]


def run_batch(entry, mode="insert"):
    rows, actions = rows_and_actions()
    if entry == "filter":
        return drf.filter_data_by_permission(
            "system", rows, actions, ResourceEnum.APM_APPLICATION, mode=mode, username="offline-user"
        )
    request = SimpleNamespace(
        token=None, skip_check=False, user=SimpleNamespace(username="offline-user", tenant_id="system")
    )
    decorate = drf.insert_permission_field(actions, ResourceEnum.APM_APPLICATION)
    return decorate(lambda req: SimpleNamespace(data=rows))(request).data


@pytest.mark.parametrize("entry", ["filter", "decorator"])
def test_drf_batches_all_actions_in_one_sdk_request(setup_v3, monkeypatch, entry):
    seen = []

    def sdk(self, request, groups):
        seen.append(request)
        return {group[0].id: {a.id: a.id.startswith("view_") for a in request.actions} for group in groups}

    monkeypatch.setattr(V3Client, "batch_resource_multi_actions_allowed", sdk)
    rows = run_batch(entry)
    assert len(seen) == 1
    assert {a.id for a in seen[0].actions} == {"view_apm_application_v2", "manage_apm_application_v2"}
    assert all(
        row["permission"] == {"view_apm_application_v2": True, "manage_apm_application_v2": False} for row in rows
    )


@pytest.mark.parametrize("entry", ["filter", "decorator"])
def test_drf_keeps_space_coverage_with_real_sdk_policy_evaluation(setup_v3, monkeypatch, entry):
    calls = []

    def policies(self, request, with_resources=True):
        calls.append(with_resources)
        return [
            {
                "action": {"id": action.id},
                "condition": (
                    {"op": "starts_with", "field": "apm_application._bk_iam_path_", "value": "/space,2/"}
                    if action.id.startswith("view_")
                    else {"op": "eq", "field": "apm_application.id", "value": "8"}
                ),
            }
            for action in request.actions
        ]

    monkeypatch.setattr(V3Client, "_do_policy_query_by_actions", policies)
    rows = run_batch(entry)
    assert calls == [False]
    assert [row["permission"] for row in rows] == [
        {"view_apm_application_v2": True, "manage_apm_application_v2": False},
        {"view_apm_application_v2": True, "manage_apm_application_v2": True},
    ]


@pytest.mark.parametrize(
    "entry,mode", [("filter", "insert"), ("filter", "any"), ("filter", "all"), ("decorator", "insert")]
)
def test_drf_preserves_original_sdk_failure(setup_v3, monkeypatch, entry, mode):
    failure = AuthAPIError("offline unavailable")
    monkeypatch.setattr(V3Client, "batch_resource_multi_actions_allowed", Mock(side_effect=failure))
    with pytest.raises(AuthAPIError) as error:
        run_batch(entry, mode)
    assert error.value is failure


@pytest.mark.parametrize("mode", [AuthMode.V4, AuthMode.UNION])
@pytest.mark.parametrize("entry", ["filter", "decorator"])
def test_drf_current_modes_use_one_snapshot_and_multi_action_batch(setup_v3, monkeypatch, mode, entry):
    from iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem

    p = permission()
    p.mode_provider.get_mode.return_value = mode
    providers = {}
    for name in ("v3", "v4"):
        provider = Mock()
        provider.name = name
        allowed = name == "v4"
        provider.batch_is_allowed.side_effect = lambda request, name=name, allowed=allowed: BatchAuthResult(
            tuple(
                BatchAuthResultItem(action, rid, AuthResult.allow(name) if allowed else AuthResult.deny(name))
                for action, rid in request.iter_keys()
            )
        )
        providers[name] = provider
    p._providers = providers
    monkeypatch.setattr(drf, "Permission", lambda **kwargs: p)
    rows = run_batch(entry)
    assert all(all(row["permission"].values()) for row in rows)
    p.mode_provider.get_mode.assert_called_once()
    for name in ["v4"] if mode is AuthMode.V4 else ["v3", "v4"]:
        providers[name].batch_is_allowed.assert_called_once()
        assert len(providers[name].batch_is_allowed.call_args.args[0].action_ids) == 2
    if mode is AuthMode.V4:
        providers["v3"].batch_is_allowed.assert_not_called()


@pytest.mark.parametrize("method", ["get_apply_data", "get_apply_url"])
@pytest.mark.parametrize("mode", list(AuthMode))
def test_unknown_apply_action_is_an_input_error(setup_v3, method, mode):
    p = permission()
    p.mode_provider.get_mode.return_value = mode
    with pytest.raises(ActionNotExistError):
        getattr(p, method)(["__unknown_action__"])
    p.mode_provider.get_mode.assert_not_called()


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("get_authority_detail", {"bk_biz_id": 2}),
        ("get_authority_apply_info", {"resources": [{"type": "space", "id": "2"}]}),
    ],
)
def test_apply_endpoints_keep_unknown_action_400(setup_v3, monkeypatch, endpoint, payload):
    request = SimpleNamespace(
        token=None, skip_check=False, user=SimpleNamespace(username="offline-user", tenant_id="system")
    )
    monkeypatch.setattr(pm, "get_request", lambda **kwargs: request)
    monkeypatch.setattr(Permission, "prepare_apply_for_saas", lambda self, resources: ([], []))
    monkeypatch.setattr(
        ResourceEnum.BUSINESS, "create_instance", lambda instance_id: ResourceInstance("space", str(instance_id))
    )
    monkeypatch.setattr(
        "monitor_web.iam.resources.SpaceApi.get_space_detail", lambda **kwargs: SimpleNamespace(bk_biz_id=2)
    )
    IAMViewSet.generate_endpoint()
    req = APIRequestFactory().post("/iam/", {**payload, "action_ids": ["__unknown_action__"]}, format="json")
    force_authenticate(req, user=SimpleNamespace(is_authenticated=True))
    response = IAMViewSet.as_view({"post": endpoint})(req)
    response.render()
    body = json.loads(response.content)
    assert response.status_code == 400 and body["result"] is False
    assert body["error_details"]["code"] == 3399001


def test_sdk_reported_apply_failure_gets_v3_fallback(setup_v3, monkeypatch, caplog):
    p = permission()
    monkeypatch.setattr("iam.api.client.http_post", Mock(return_value=(False, "offline HTTP failure", None)))
    data, url = p.get_apply_data(["view_business"])
    assert data and url == setup_v3["fallback_apply_url"]
    assert any(
        record.levelname == "ERROR" and record.getMessage() == "iam generate apply url fail: offline HTTP failure"
        for record in caplog.records
    )
    provider = p.get_provider("v3")
    provider.application_builder.get_apply_data = Mock(side_effect=ValueError("invalid local model"))
    with pytest.raises(ValueError, match="invalid local model"):
        p.get_apply_data(["view_business"])


@pytest.mark.parametrize("method", ["get_apply_data", "get_apply_url"])
@pytest.mark.parametrize("response", [{}, {"url": ""}, {"url": None}, {"url": "https://iam.example.test/apply/"}])
def test_v3_apply_keeps_successful_sdk_url_unchanged(setup_v3, monkeypatch, method, response):
    post = Mock(return_value=(True, "ok", {"code": 0, "data": response}))
    monkeypatch.setattr("iam.api.client.http_post", post)
    result = getattr(permission(), method)(["view_business"])
    assert (result[1] if method == "get_apply_data" else result) == response.get("url", "")
    post.assert_called_once()


@pytest.mark.parametrize("method", ["get_apply_data", "get_apply_url"])
def test_v3_apply_keeps_actual_sdk_json_error(setup_v3, monkeypatch, method):
    error = json.JSONDecodeError("invalid gateway response", "not json", 0)
    post = Mock(side_effect=error)
    monkeypatch.setattr("iam.api.client.http_post", post)
    with pytest.raises(json.JSONDecodeError) as caught:
        getattr(permission(), method)(["view_business"])
    assert caught.value is error
    post.assert_called_once()


@pytest.mark.parametrize("method", ["get_apply_data", "get_apply_url"])
def test_v3_apply_keeps_sdk_validation_error(setup_v3, monkeypatch, method):
    from iam.apply.models import Application

    error = ValueError("invalid application")
    validate = Mock(side_effect=error)
    monkeypatch.setattr(Application, "validate", validate)
    post = Mock()
    monkeypatch.setattr("iam.api.client.http_post", post)
    with pytest.raises(ValueError) as caught:
        getattr(permission(), method)(["view_business"])
    assert caught.value is error
    validate.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("ok,url", [(False, ""), (True, "https://iam.example.test/apply/")])
def test_mcp_v3_calls_sdk_once_and_keeps_success_flag(setup_v3, monkeypatch, ok, url):
    from iam.apply.models import Application, ActionWithoutResources

    sdk = Mock(return_value=(ok, "", url))
    monkeypatch.setattr(V3Client, "get_apply_url", sdk)
    client = permission().iam_client
    application = Application("bk_monitorv3", [ActionWithoutResources("view_business_v2")])
    assert client.get_apply_data(application) == application.to_dict()
    sdk.assert_not_called()
    assert client.get_apply_url(application) == (ok, "", url)
    sdk.assert_called_once_with(application)


@pytest.mark.parametrize("mode", [AuthMode.V4, AuthMode.UNION])
def test_mcp_current_application_pair_reuses_one_generation(setup_v3, mode):
    from iam.apply.models import Application, ActionWithoutResources

    p = permission()
    p.mode_provider.get_mode.return_value = mode
    p._application_data = Mock(return_value=({"actions": []}, "https://iam.example.test/v4-apply/"))
    application = Application("bk_monitorv3", [ActionWithoutResources("view_business_v2")])
    client = p.iam_client
    assert client.get_apply_data(application) == {"actions": []}
    assert client.get_apply_url(application) == (True, "", "https://iam.example.test/v4-apply/")
    p._application_data.assert_called_once()
    p.mode_provider.get_mode.return_value = AuthMode.V3
    assert client.get_apply_data(application) == application.to_dict()
    assert p._application_data.call_count == 1
