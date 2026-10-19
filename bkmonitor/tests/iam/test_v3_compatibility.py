"""V3 product contracts and SDK semantics; no real IAM or database writes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from iam import make_expression

from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam import drf, permission as permission_module
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.backends.v3.client import V3Client
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from bkmonitor.iam.backends.v3.provider import V3PermissionProvider
from bkmonitor.iam.handlers.resolver import MonitorResourceResolver
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance, Subject
from core.errors.iam import PermissionDeniedError
from monitor_web.grafana import permissions as grafana
from bk_dataview.permissions import GrafanaRole


def v3_filter(policy, resource_type="space", ids=("1", "2"), ancestors=()):
    provider = object.__new__(V3PermissionProvider)
    provider.query_policy = lambda *args: policy
    candidates = tuple(ResourceInstance(type=resource_type, id=i, ancestor_chain=ancestors) for i in ids)
    return provider.filter_visible_resources(Subject(id="alice"), "action", candidates)


@pytest.mark.parametrize(
    "operator,value",
    [
        ("eq", "2"),
        ("not_eq", "2"),
        ("in", ["1", "2"]),
        ("not_in", ["2"]),
        ("starts_with", "2"),
        ("not_starts_with", "2"),
        ("ends_with", "2"),
        ("not_ends_with", "2"),
        ("string_contains", "2"),
        ("contains", "2"),
        ("not_contains", "2"),
        ("lt", "2"),
        ("lte", "2"),
        ("gt", "2"),
        ("gte", "2"),
        ("eq", ["2"]),
        ("in", "12"),
        ("starts_with", ["2"]),
        ("not_eq", ["2"]),
    ],
)
def test_v3_filter_reuses_sdk_operator_and_type_semantics(operator, value):
    policy = {"op": operator, "field": "space.id", "value": value}
    expected = tuple(i for i in ("1", "2") if make_expression(policy).eval({"space.id": i}))
    result = v3_filter(policy)
    assert result.visible_ids == expected
    assert result.all_granted is False


def test_and_negative_constraint_is_not_dropped():
    policy = {
        "op": "AND",
        "content": [
            {"op": "in", "field": "space.id", "value": ["1", "2"]},
            {"op": "not_starts_with", "field": "space.id", "value": "2"},
        ],
    }
    assert v3_filter(policy).visible_ids == ("1",)


@pytest.mark.parametrize("operator", ["AND", "OR"])
def test_unknown_or_empty_operand_is_never_silently_removed(operator):
    for child in [{"op": "unsupported", "field": "space.id", "value": "2"}, None]:
        with pytest.raises((ValueError, TypeError)):
            v3_filter(
                {
                    "op": operator,
                    "content": [
                        {"op": "in", "field": "space.id", "value": ["1", "2"]},
                        child,
                    ],
                }
            )


@pytest.mark.parametrize("operator,expected", [("AND", ("1", "2")), ("OR", ())])
def test_empty_logical_expression_matches_sdk(operator, expected):
    assert v3_filter({"op": operator, "content": []}).visible_ids == expected


def test_sdk_iam_path_wildcard_semantics_are_preserved():
    policy = {"op": "starts_with", "field": "grafana_dashboard._bk_iam_path_", "value": "/space,2/,*/"}
    # SDK strips the final ,*/ rather than treating it as a literal prefix.
    parent = (ResourceInstance(type="space", id="2"),)
    expected = make_expression(policy).eval({"grafana_dashboard._bk_iam_path_": "/space,2/"})
    result = v3_filter(policy, "grafana_dashboard", ("10|dash-a",), parent)
    assert result.all_granted is expected


@pytest.mark.parametrize("operator", ["eq", "in"])
def test_bare_dashboard_uid_is_a_v3_alias_only(operator):
    value = "dash-a" if operator == "eq" else ["dash-a", "20|dash-b"]
    result = v3_filter(
        {"op": operator, "field": "grafana_dashboard.id", "value": value},
        "grafana_dashboard",
        ("10|dash-a", "10|dash-b"),
    )
    assert result.visible_ids == ("10|dash-a",)


@pytest.mark.parametrize("operator", ["eq", "in"])
def test_nested_dashboard_uid_keeps_v3_scope_without_local_candidate(operator):
    value = "dash-a" if operator == "eq" else ["dash-a", "folder:10|7", "20|dash-b"]
    policy = {
        "op": "AND",
        "content": [
            {"op": operator, "field": "grafana_dashboard.id", "value": value},
            {"op": "starts_with", "field": "grafana_dashboard._bk_iam_path_", "value": "/space,2/"},
        ],
    }
    parent = (ResourceInstance("space", "2"),)
    result = v3_filter(policy, "grafana_dashboard", ("10|",), parent)
    expected = ("10|dash-a",) if operator == "eq" else ("10|dash-a", "folder:10|7")
    assert result.visible_ids == expected
    assert result.all_granted is False
    other = v3_filter(policy, "grafana_dashboard", ("10|",), (ResourceInstance("space", "3"),))
    assert other.visible_ids == ()


@pytest.mark.parametrize(
    "resource_meta",
    [ResourceEnum.BUSINESS, ResourceEnum.APM_APPLICATION, ResourceEnum.GRAFANA_DASHBOARD, ResourceEnum.RUM_APPLICATION],
)
def test_simple_resource_keeps_explicit_v3_attributes(resource_meta, monkeypatch):
    from monitor_web.iam.views import ApmApplicationProvider, RumApplicationProvider, Dashboard
    monkeypatch.setattr(ApmApplicationProvider, "_get_app_simple_info_by_id_or_none", lambda id: None)
    monkeypatch.setattr(RumApplicationProvider, "_get_app_simple_info_by_id_or_none", lambda id: None)
    monkeypatch.setattr(Dashboard, "objects", Mock(filter=Mock(return_value=Mock(only=Mock(return_value=Mock(first=Mock(return_value=None)))))))
    attributes = {"owner": "alice", "_bk_iam_path_": "/space,2/"}
    resource = resource_meta.create_simple_instance("7", attributes)
    client = V3Client("offline", "offline", "https://iam.example.test", "bk_monitorv3", MonitorV3Codec())
    sdk_resource = MonitorV3Codec().encode_resource(resource, client)
    assert sdk_resource.attribute["owner"] == "alice"
    assert sdk_resource.attribute["_bk_iam_path_"] == "/space,2/"


@pytest.mark.parametrize("is_superuser,skip_check", [(True, False), (False, True)])
def test_grafana_read_gate_keeps_request_bypass(is_superuser, skip_check):
    request = SimpleNamespace(
        biz_id=20, skip_check=skip_check, user=SimpleNamespace(username="alice", is_superuser=is_superuser)
    )
    assert grafana.GrafanaReadPermission().has_permission(request, None) is True


def test_grafana_gate_uses_current_business_not_global_policy(monkeypatch):
    check = Mock(return_value=(True, GrafanaRole.Anonymous, {}))
    monkeypatch.setattr(grafana.DashboardPermission, "has_permission", check)
    request = SimpleNamespace(biz_id=20, user=SimpleNamespace(username="alice"))
    fallback = Mock(has_permission=Mock(return_value=False))
    assert grafana.GrafanaReadPermission(fallback).has_permission(request, None) is False
    check.assert_called_once_with(request, None, 20)
    fallback.has_permission.assert_called_once_with(request, None)


def test_space_uid_normalizes_before_v3_sdk_encoding(monkeypatch):
    from bkm_space.utils import api as space_api

    space = SimpleNamespace(
        space_uid="bcs__cluster-a", id=42, space_type_id="bcs", space_name="cluster-a", bk_tenant_id="system"
    )
    monkeypatch.setattr(space_api.SpaceApi, "get_space_detail", lambda **kwargs: space)
    resource = ResourceEnum.BUSINESS.create_simple_instance("bcs__cluster-a")
    resolved = MonitorResourceResolver().resolve(resource, tenant_id="system")
    client = V3Client("offline", "offline", "https://iam.example.test", "bk_monitorv3", MonitorV3Codec())
    assert MonitorV3Codec().encode_resource(resolved, client).id == "-42"
    from bkmonitor.iam.backends.v4.codec import MonitorV4Codec

    assert MonitorV4Codec().encode_resource_for_auth(resolved)["id"] == "space|-42"


@pytest.mark.parametrize("mode", ["v3", "v4"])
def test_batch_normalized_space_uid_keeps_original_request_result_key(monkeypatch, mode):
    from bkm_space.utils import api as space_api
    from iam_engine.core.requests import BatchAuthRequest

    space = SimpleNamespace(
        space_uid="bcs__cluster-a", id=42, space_type_id="bcs", space_name="cluster-a", bk_tenant_id="system"
    )
    monkeypatch.setattr(space_api.SpaceApi, "get_space_detail", lambda **kwargs: space)
    provider = build_provider(mode, "system", username="alice")
    client = Mock()
    if mode == "v3":
        client.make_resource = lambda rt, rid, **kwargs: SimpleNamespace(id=rid)
        client.batch_resource_multi_actions_allowed.return_value = {"-42": {"view_business_v2": True}}
    else:
        client.direct_auth_by_resources.return_value = {"space|-42": True}
    provider.client_factory = lambda tid: client
    request = BatchAuthRequest(
        Subject(id="alice"), ("view_business",), ((ResourceInstance(type="space", id="bcs__cluster-a"),),)
    )
    result = provider.batch_is_allowed(request)
    assert result.items[0].resource_id == "bcs__cluster-a"
    assert result.items[0].result.allowed is True


def test_by_business_keeps_authenticated_share_token_preflight(monkeypatch):
    request = SimpleNamespace(
        token="valid-share",
        path="/rest/v2/iam/check_allowed_by_action_ids/",
        skip_check=False,
        user=SimpleNamespace(username="alice", tenant_id="system"),
    )
    monkeypatch.setattr(
        permission_module.ApiAuthToken, "objects", Mock(get=Mock(return_value=SimpleNamespace(type="host")))
    )
    permission = permission_module.Permission(request=request)
    permission._is_allowed_request = Mock(return_value=False)
    assert permission.is_allowed_by_biz(2, ActionEnum.VIEW_BUSINESS) is True
    permission._is_allowed_request.assert_not_called()


@pytest.mark.parametrize("mixed", [False, True])
@pytest.mark.parametrize("allowed", [False, True])
def test_v3_complete_resource_request_reaches_original_sdk(mixed, allowed):
    permission = permission_module.Permission(username="alice", bk_tenant_id="system")
    permission.skip_check = False
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode.V3)
    provider = build_provider("v3", "system", username="alice")
    provider.resolver = None
    client = V3Client("offline", "offline", "https://iam.example.test", "bk_monitorv3", MonitorV3Codec())
    client.is_allowed_with_cache = Mock(return_value=allowed)
    client.batch_resource_multi_actions_allowed = Mock(side_effect=AssertionError("V3 must keep one SDK request"))
    provider.client_factory = lambda tid: client
    permission._providers = {"v3": provider}
    resources = [ResourceInstance("space", "2"), ResourceInstance("apm_application" if mixed else "space", "3")]
    assert permission.is_allowed(ActionEnum.VIEW_BUSINESS, resources) is allowed
    sdk_request = client.is_allowed_with_cache.call_args.args[0]
    assert [(r.type, r.id) for r in sdk_request.resources] == [(r.type, r.id) for r in resources]
    assert sdk_request.action.id == "view_business_v2"


def test_default_v3_metadata_keeps_remote_response_verbatim():
    permission = permission_module.Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode.V3)
    rows = [{"id": "view_business_v2", "remote_field": "preserved"}]
    client = Mock()
    client._client.query.return_value = (True, "", {"actions": rows})
    permission._providers = {"v3": SimpleNamespace(name="v3", client=client, system_id="bk_monitorv3")}
    assert permission.list_actions() is rows
    client._client.query.assert_called_once_with("bk_monitorv3")


def test_default_v3_metadata_keeps_api_failure_contract():
    from core.errors.api import BKAPIError

    permission = permission_module.Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode.V3)
    client = Mock()
    client._client.query.return_value = (False, "offline", {})
    permission._providers = {"v3": SimpleNamespace(client=client, system_id="bk_monitorv3")}
    with pytest.raises(BKAPIError):
        permission.list_actions()


@pytest.mark.parametrize("mode", [AuthMode.V4, AuthMode.UNION])
def test_v4_metadata_keeps_product_legacy_ids_without_querying_v3(mode):
    permission = permission_module.Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    permission._providers = {"v4": Mock(name="v4")}
    rows = permission.list_actions()
    ids = {row["id"] for row in rows}
    assert "view_business_v2" in ids and "view_business" not in ids
    assert all(set(row["related_actions"]) <= ids for row in rows)
    related = next(row["related_resource_types"][0] for row in rows if row["related_resource_types"])
    assert related["selection_mode"] == "instance"
    assert related["related_instance_selections"]


def test_v3_application_registers_sdk_metadata_in_a_fresh_process(monkeypatch):
    from iam import meta

    monkeypatch.setattr(meta, "__meta_info__", {"system": {}, "resources": {}, "actions": {}})
    provider = build_provider("v3", "system", username="alice")
    client = V3Client(
        "offline", "offline", "https://iam.example.test", "bk_monitorv3", MonitorV3Codec(), enable_v1_compat=False
    )
    client.get_apply_url = Mock(return_value=(True, "", "https://iam.example.test/apply"))
    provider.client_factory = lambda tid: client
    monkeypatch.setattr(provider, "_resolve", lambda resource, **kwargs: resource)
    data, url = provider.get_apply_data(["view_business"], [ResourceInstance(type="space", id="2", name="space")])
    assert data["system_name"] == provider._cfg.system.name
    assert data["actions"][0]["name"] == "业务访问"
    assert data["actions"][0]["related_resource_types"][0]["type_name"] == "空间"
    assert url == "https://iam.example.test/apply"


@pytest.mark.parametrize("mode", [AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def test_drf_saas_denial_reuses_product_bundle_for_every_read_mode(monkeypatch, mode):
    permission = permission_module.Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): mode)
    permission._is_allowed_request = Mock(return_value=False)
    permission._apply_data_request = Mock(side_effect=lambda actions, *args: {"actions": actions})
    permission._apply_url_request = Mock(return_value="https://iam.example.test/apply")
    monkeypatch.setattr(permission_module, "bk_biz_id_to_space_uid", lambda value: "bkci__project-a")
    monkeypatch.setattr(permission_module, "is_bk_saas_space", lambda uid: True)
    monkeypatch.setattr(drf, "Permission", lambda **kwargs: permission)
    request = SimpleNamespace(token=None, skip_check=False, user=SimpleNamespace(username="alice", tenant_id="system"))
    with pytest.raises(PermissionDeniedError) as error:
        drf._fw_check_any(request, [ActionEnum.EXPLORE_METRIC], [ResourceInstance(type="space", id="-42")])
    internal_ids = [permission_module.canonicalize_action_id(a) for a in permission_module.MINI_ACTION_IDS]
    assert error.value.extra["permission"]["actions"] == internal_ids
    apply_request = permission._apply_url_request.call_args.args[0]
    assert apply_request.action_ids == tuple(internal_ids)
    assert apply_request.resources[0].id == "-42"
