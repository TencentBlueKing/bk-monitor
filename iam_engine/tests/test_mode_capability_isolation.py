"""Lazy product capabilities and one mode snapshot per complete operation."""

from unittest.mock import Mock

import pytest
from iam import Resource

from bkmonitor.iam.permission import Permission
from core.errors.iam import PermissionDeniedError
from iam_engine.core.config import AuthMode
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.core.requests import AuthRequest, Subject, ResourceInstance
from iam_engine.core.types import AuthResult, BatchAuthResult, BatchAuthResultItem
from iam_engine.provider.bundle import LazyProviderBundles, ProviderBundle
from iam_engine.provider.router import ModeRouter


@pytest.mark.parametrize(
    "mode,targets",
    [(AuthMode.V3, (AuthMode.V3,)), (AuthMode.V4, (AuthMode.V4,)), (AuthMode.UNION, (AuthMode.V3, AuthMode.V4))],
)
def test_monitor_lazy_auth_and_writer_assembly_follows_mode_then_dynamic_switch(mode, targets):
    permission = Permission(username="alice", bk_tenant_id="system")
    selector = Mock(get_mode=Mock(return_value=mode))
    permission.mode_provider = selector
    providers = {version: Mock() for version in (AuthMode.V3, AuthMode.V4)}
    writers = {version: Mock() for version in providers}
    for version, provider in providers.items():
        provider.name = version.value
        provider.is_allowed.return_value = AuthResult.allow(version.value)
    factories = {
        version: Mock(return_value=ProviderBundle(auth=provider, writer=writers[version]))
        for version, provider in providers.items()
    }
    permission._provider_bundles = LazyProviderBundles(factories)
    assert permission.is_allowed("view_business")
    permission.grant_creator_action(Resource("bk_monitorv3", "space", "2", {}), raise_exception=True)
    assert selector.get_mode.call_count == 2
    for version in providers:
        assert factories[version].call_count == (version in targets)
        assert providers[version].is_allowed.call_count == (version in targets)
        assert writers[version].grant_resource_creator_actions.call_count == (version in targets)
    selector.get_mode.return_value = AuthMode.V4 if mode is AuthMode.V3 else AuthMode.V3
    assert permission.is_allowed("view_business")
    assert selector.get_mode.call_count == 3


def test_default_v3_never_constructs_v4_even_with_derived_url(settings, monkeypatch):
    settings.BK_COMPONENT_API_URL = "https://components.example.test/"
    settings.BK_IAM_V4_APIGATEWAY_URL = ""
    settings.BK_IAM_PERMISSION_MODE = "v3"
    monkeypatch.delenv("BKAPP_IAM_PERMISSION_MODE", raising=False)
    permission = Permission(username="alice", bk_tenant_id="system")
    v3 = Mock(name="v3")
    v3.is_allowed.return_value = AuthResult.allow("v3")
    constructor = Mock(side_effect=lambda name, *args, **kw: v3 if name == "v3" else pytest.fail("V3 assembled V4"))
    monkeypatch.setattr("bkmonitor.iam.permission.build_provider", constructor)
    assert permission.is_allowed("view_business")
    assert list(permission.providers) == ["v3"]
    constructor.assert_called_once()


@pytest.mark.parametrize(
    "resources", [[], [Resource("bk_monitorv3", "space", "1", {}), Resource("bk_monitorv3", "space", "2", {})]]
)
def test_denial_and_application_keep_v3_mode_snapshot_during_configuration_change(resources):
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = Mock(get_mode=Mock(side_effect=[AuthMode.V3, AuthMode.V4]))
    v3, v4 = Mock(), Mock()
    v3.is_allowed.return_value = AuthResult.deny("v3")
    v3.get_apply_data.return_value = ({"system": "v3"}, "https://v3-page.example.test/")
    permission._provider_bundles = {
        AuthMode.V3: ProviderBundle(auth=v3, application=v3),
        AuthMode.V4: ProviderBundle(auth=v4, application=v4),
    }
    permission.prepare_apply_for_saas = Mock(return_value=([], []))
    with pytest.raises(PermissionDeniedError) as denied:
        permission.is_allowed("view_business", resources, raise_exception=True)
    assert denied.value.data == {"apply_url": "https://v3-page.example.test/"}
    permission.mode_provider.get_mode.assert_called_once()
    v4.is_allowed.assert_not_called()
    v4.get_apply_data.assert_not_called()


def test_invalid_snapshot_cannot_be_corrected_during_authentication_or_application():
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = Mock(
        get_mode=Mock(side_effect=[InvalidAuthModeError("bad", "invalid mode"), AuthMode.V3])
    )
    factories = {version: Mock() for version in (AuthMode.V3, AuthMode.V4)}
    permission._provider_bundles = LazyProviderBundles(factories)
    permission.prepare_apply_for_saas = Mock(return_value=([], []))
    with pytest.raises(PermissionDeniedError) as denied:
        permission.is_allowed("view_business", raise_exception=True)
    assert denied.value.data == {"apply_url": ""}
    permission.mode_provider.get_mode.assert_called_once()
    for factory in factories.values():
        factory.assert_not_called()


def test_common_snapshot_reuses_same_lazy_capabilities_without_reloading_mode():
    selector = Mock()
    provider = Mock(is_allowed=Mock(return_value=AuthResult.allow("v3")))
    factory = Mock(return_value=ProviderBundle(auth=provider))
    router = ModeRouter(selector, LazyProviderBundles({AuthMode.V3: factory}), pair_executor=lambda a, b: (a(), b()))
    snapshot = router.with_mode(AuthMode.V3)
    for _ in range(2):
        assert snapshot.is_allowed(AuthRequest(Subject(id="alice"), "view")).allowed
    selector.get_mode.assert_not_called()
    factory.assert_called_once()


@pytest.mark.parametrize("mode", [AuthMode.V3, AuthMode.V4, AuthMode.UNION])
def test_public_batch_snapshots_mode_and_keeps_complete_resource_groups(mode):
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = Mock(get_mode=Mock(side_effect=[mode, AuthMode.V4]))
    providers = {version: Mock() for version in (AuthMode.V3, AuthMode.V4)}
    for version, provider in providers.items():
        provider.batch_is_allowed.side_effect = lambda request, version=version: BatchAuthResult(
            tuple(BatchAuthResultItem(a, r, AuthResult.allow(version.value)) for a, r in request.iter_keys())
        )
    raw = {"1": {"view_event_v2": True, "manage_event_v2": False}}
    providers[AuthMode.V3].batch_product_is_allowed.return_value = raw
    permission._providers = {version.value: provider for version, provider in providers.items()}
    permission._provider_bundles = {version: ProviderBundle(auth=provider) for version, provider in providers.items()}
    groups = [[ResourceInstance("space", "1"), ResourceInstance("space", "2")]]
    result = permission.batch_is_allowed(["view_event", "manage_event"], groups)
    permission.mode_provider.get_mode.assert_called_once()
    if mode is AuthMode.V3:
        assert result is raw
        request = providers[AuthMode.V3].batch_product_is_allowed.call_args.args[0]
        providers[AuthMode.V4].batch_is_allowed.assert_not_called()
    else:
        assert result == {"1": {"view_event_v2": True, "manage_event_v2": True}}
        request = providers[AuthMode.V4].batch_is_allowed.call_args.args[0]
        assert providers[AuthMode.V3].batch_is_allowed.call_count == (mode is AuthMode.UNION)
    assert request.resource_groups == tuple(tuple(group) for group in groups)
    assert request.action_ids == ("view_event", "manage_event")


@pytest.mark.parametrize("error", [None, RuntimeError("original SDK failure")])
def test_v3_product_batch_preserves_sdk_request_result_and_exception(error):
    from bkmonitor.iam.backends.config import build_provider
    from bkmonitor.iam.backends.v3.client import V3Client
    from bkmonitor.iam.backends.v3.codec import MonitorV3Codec

    permission = Permission(username="alice", bk_tenant_id="system")
    permission.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
    provider = build_provider("v3", options={
        "base_url": "https://iam.example.test/",
        "credentials": {"app_code": "offline", "app_secret": "offline"},
        "system": {"id": "bk_monitorv3", "name": "Monitor"},
    })
    client = V3Client("offline", "offline", "https://iam.example.test/", "bk_monitorv3", MonitorV3Codec())
    raw = {"1": {"view_event_v2": True}}
    client.batch_resource_multi_actions_allowed = Mock(return_value=raw, side_effect=error)
    provider._get_client = Mock(return_value=client)
    provider.resolver = Mock(resolve=Mock(side_effect=AssertionError("original V3 batch does not reload resources")))
    permission._providers = {"v3": provider}
    resources = [[Resource("bk_monitorv3", "space", "1", {"name": "first"}),
                  Resource("bk_monitorv3", "space", "2", {"name": "second"})]]
    if error is not None:
        with pytest.raises(RuntimeError) as raised:
            permission.batch_is_allowed(["view_event"], resources)
        assert raised.value is error
    else:
        assert permission.batch_is_allowed(["view_event"], resources) is raw
    request, encoded_groups = client.batch_resource_multi_actions_allowed.call_args.args
    assert request.to_dict()["actions"] == [{"id": "view_event_v2"}]
    assert [[r.id for r in group] for group in encoded_groups] == [["1", "2"]]
    assert [r.attribute["name"] for r in encoded_groups[0]] == ["first", "second"]
    provider.resolver.resolve.assert_not_called()
