"""Actual product settings, provider/client construction and denial consumers, offline."""

import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from django.test import override_settings

from bkmonitor.iam import drf
from bkmonitor.iam.backends.config import build_providers
from bkmonitor.iam.permission import Permission
from core.errors.iam import PermissionDeniedError
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from iam_engine.core.types import AuthResult
from iam_engine.migration.policy import ApplicationProviderNotConfiguredError, MigrationPolicy
from iam_engine.provider.bundle import ProviderBundle
from iam_engine.settings import load_iam_settings, resolve_iam_gateway_url
from iam_engine.v4.exceptions import V4ResponseError
from monitor_web.iam import resources as iam_resources


def product_gateways(product, environ):
    source = Path(__file__).resolve().parents[2] / product / "config/default.py"
    nodes = []
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.ImportFrom) and node.module == "iam_engine.settings":
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in {"BK_IAM_APIGATEWAY_URL", "BK_IAM_V3_API_BASE_URL"}
            for target in node.targets
        ):
            nodes.append(node)
        elif isinstance(node, ast.Expr) and ast.unparse(node).startswith("globals().update(load_iam_settings("):
            nodes.append(node)
    namespace = {"os": os, "BK_COMPONENT_API_URL": environ.get("BK_COMPONENT_API_URL")}
    with patch.dict(os.environ, environ, clear=True):
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return namespace


@pytest.mark.parametrize(
    "root",
    ["https://components.example.test", "https://components.example.test/", " https://components.example.test/// "],
)
@pytest.mark.parametrize("override", [None, "", "  "])
def test_product_defaults_and_blank_overrides_use_independent_gateways(root, override):
    environ = {"BK_COMPONENT_API_URL": root}
    if override is not None:
        environ.update(BKAPP_IAM_API_BASE_URL=override, BKAPP_IAM_V4_API_BASE_URL=override)
    for product in ("bklog", "bkmonitor"):
        values = product_gateways(product, environ)
        assert values["BK_IAM_APIGATEWAY_URL"] == "https://components.example.test/api/bk-iam/prod/"
        assert values["BK_IAM_V4_APIGATEWAY_URL"] == "https://components.example.test/api/bkiam/prod/"


def test_product_override_priority_does_not_cross_versions():
    environ = {
        "BK_COMPONENT_API_URL": "https://components.example.test",
        "BKAPP_IAM_API_BASE_URL": " https://v3.example.test/stage ",
        "BK_IAM_V3_API_BASE_URL": " https://monitor-v3.example.test/dev/ ",
        "BKAPP_IAM_V4_API_BASE_URL": " https://v4.example.test/dev ",
    }
    for product in ("bklog", "bkmonitor"):
        values = product_gateways(product, environ)
        assert values["BK_IAM_APIGATEWAY_URL"] == "https://v3.example.test/stage/"
        assert values["BK_IAM_V4_APIGATEWAY_URL"] == "https://v4.example.test/dev/"
        if product == "bkmonitor":
            assert values["BK_IAM_V3_API_BASE_URL"] == "https://monitor-v3.example.test/dev/"
    environ["BK_IAM_V3_API_BASE_URL"] = "  "
    assert product_gateways("bkmonitor", environ)["BK_IAM_V3_API_BASE_URL"] == "https://v3.example.test/stage/"


@pytest.mark.parametrize("root", [None, "", "  "])
def test_missing_root_never_produces_none_url_or_uses_v3_for_v4(root):
    assert resolve_iam_gateway_url(root, "", version="v3") == ""
    assert load_iam_settings({}, component_api_url=root)["BK_IAM_V4_APIGATEWAY_URL"] == ""


@pytest.mark.parametrize(
    "v3_url,v4_url", [("", ""), (" https://v3.example.test/dev ", ""), ("", " https://v4.example.test/dev ")]
)
def test_monitor_default_provider_and_actual_request_urls(v3_url, v4_url):
    response = Mock(status_code=200, content=b"json", text="response")
    response.json.return_value = {"data": {"url": "https://v4-page.example.test/application/123/"}}
    with override_settings(
        BK_COMPONENT_API_URL="https://components.example.test/",
        BK_IAM_APIGATEWAY_URL=v3_url,
        BK_IAM_V3_API_BASE_URL="",
        BK_IAM_V4_APIGATEWAY_URL=v4_url,
    ):
        providers = build_providers("system", username="alice", mode=AuthMode.UNION)
        assert set(providers) == {"v3", "v4"}
        with patch("iam.api.client.http_post", return_value=(True, "", {"code": 0, "data": {}})) as post:
            providers["v3"].client._client.policy_query({})
        expected_v3 = resolve_iam_gateway_url("https://components.example.test/", v3_url, version="v3")
        assert post.call_args.args[0] == expected_v3 + "api/v1/policy/query"
        with patch.object(requests, "request", return_value=response) as send:
            data, url = providers["v4"].get_apply_data(["view_business"], [])
        expected_v4 = resolve_iam_gateway_url("https://components.example.test/", v4_url, version="v4")
        assert send.call_args.kwargs["url"] == expected_v4 + "api/v1/open/application/permission-apply-urls/"
        assert send.call_args.kwargs["json"]["permissions"][0]["action_id"] == "view_business"
        assert url == "https://v4-page.example.test/application/123/"
        assert data["system"] == providers["v4"].system_id


@pytest.mark.parametrize(
    "mode,target", [(AuthMode.V3, AuthMode.V3), (AuthMode.V4, AuthMode.V4), (AuthMode.UNION, AuthMode.V4)]
)
def test_application_selection_is_fixed_and_missing_capability_never_changes_version(mode, target):
    applications = {version: Mock() for version in (AuthMode.V3, AuthMode.V4)}
    bundles = {version: ProviderBundle(application=application) for version, application in applications.items()}
    assert MigrationPolicy.resolve_application(mode, bundles).provider is applications[target]
    del bundles[target]
    with pytest.raises(ApplicationProviderNotConfiguredError):
        MigrationPolicy.resolve_application(mode, bundles)


@pytest.mark.parametrize("mode", [AuthMode.V4, AuthMode.UNION])
@pytest.mark.parametrize("failure", [TimeoutError("offline"), RuntimeError("bad response"), "", "  ", None, "missing"])
def test_monitor_denial_and_page_api_keep_unavailable_application_without_v3(monkeypatch, mode, failure):
    p = Permission(username="alice", bk_tenant_id="system")
    v3, v4 = Mock(name="v3-provider"), Mock(name="v4-provider")
    v3.name, v4.name = "v3", "v4"
    v3.is_allowed.return_value, v4.is_allowed.return_value = AuthResult.deny("v3"), AuthResult.deny("v4")
    v3.get_apply_data.return_value = ({"actions": ["legacy"]}, "https://v3-page.example.test")
    if isinstance(failure, Exception):
        v4.get_apply_data.side_effect = failure
    else:
        v4.get_apply_data.return_value = ({"actions": ["v4"]}, failure)
    p._providers = {"v3": v3, **({"v4": v4} if failure != "missing" else {})}
    p.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    p.prepare_apply_for_saas = Mock(return_value=([], []))
    monkeypatch.setattr(drf, "check_iam_preflight", lambda *args: False)
    monkeypatch.setattr(drf, "Permission", lambda **kw: p)
    request = SimpleNamespace(user=SimpleNamespace(username="alice", tenant_id="system"))
    with pytest.raises(PermissionDeniedError) as denied:
        drf._fw_check_any(request, ["view_business"])
    assert denied.value.data == {"apply_url": ""}
    assert denied.value.extra["permission"] == {}
    monkeypatch.setattr(iam_resources, "Permission", lambda: p)
    monkeypatch.setattr(iam_resources.SpaceApi, "get_space_detail", lambda **kw: SimpleNamespace(bk_biz_id=2))
    monkeypatch.setattr(
        iam_resources.ResourceEnum.BUSINESS, "create_instance", lambda *args: ResourceInstance(type="space", id="2")
    )
    assert iam_resources.GetAuthorityDetailResource().perform_request(
        {"action_ids": ["view_business"], "bk_biz_id": 2}
    ) == {"authority_list": {}, "apply_url": ""}
    v3.get_apply_data.assert_not_called()


@pytest.mark.parametrize("url", ["", "  ", None, False, {}, []])
def test_v4_real_client_rejects_empty_or_non_page_url_values(url):
    p = build_providers("system", username="alice", mode=AuthMode.V4)["v4"]
    response = Mock(status_code=200, content=b"json")
    response.json.return_value = {"data": {"url": url}}
    with patch.object(requests, "request", return_value=response), pytest.raises(V4ResponseError):
        p.client.generate_perm_apply_url(permissions=[])
