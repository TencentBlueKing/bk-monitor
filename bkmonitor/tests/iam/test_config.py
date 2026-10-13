"""Product assembly consumes the common mode and HTTP options contracts."""

import pytest
from bkmonitor.iam.backends.config import build_provider
from bkmonitor.iam.permission import Permission
from iam_engine.v4.config import V4Options
from dataclasses import replace


def test_v4_uses_shared_options_without_model_configuration():
    options = replace(V4Options.from_settings(), batch_chunk_size=8, batch_max_workers=2)
    provider = build_provider("v4", options=options)
    assert provider.system_id == options.system_id
    assert (provider.batch_chunk_size, provider.batch_max_workers) == (8, 2)
    assert not hasattr(provider, "_cfg")
    assert not hasattr(provider, "ctx")
    with pytest.raises(TypeError, match="shared V4Options"):
        build_provider("v4", options={"base_url": "https://example.test"})


class TestProductAssembly:
    @pytest.mark.parametrize("mode", ["v3", "v4", "union"])
    def test_mode_selects_loaded_backends(self, settings, monkeypatch, mode):
        from bkmonitor.iam.backends.config import build_providers

        monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", mode)
        settings.BK_IAM_V4_APIGATEWAY_URL = "https://iam.example.test/dev"
        assert set(build_providers("tenant-a")) == ({"v3", "v4"} if mode == "union" else {mode})

    def test_default_v3_does_not_load_v4_even_with_derived_gateway(self, settings, monkeypatch):
        from bkmonitor.iam.backends.config import build_providers

        monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
        settings.BK_IAM_V4_APIGATEWAY_URL = ""
        settings.BK_COMPONENT_API_URL = "https://components.example.test/"
        assert set(build_providers("tenant-a")) == {"v3"}

    def test_permission_uses_shared_router_directly(self):
        from iam_engine.provider.router import ModeRouter

        permission = Permission(username="offline", bk_tenant_id="system")
        assert isinstance(permission.mode_router, ModeRouter)
        assert not hasattr(permission, "_fw")

    def test_metadata_is_immutable_and_shared(self):
        from bkmonitor.iam import definitions

        assert Permission(username="offline", bk_tenant_id="system").schema is definitions
        assert len(definitions.actions) == 55


def test_monitor_and_common_use_identical_subject_and_resource_objects():
    from iam_engine.core.requests import Subject, ResourceInstance
    from iam_engine.provider import requests

    assert requests.Subject is Subject
    assert requests.ResourceInstance is ResourceInstance
