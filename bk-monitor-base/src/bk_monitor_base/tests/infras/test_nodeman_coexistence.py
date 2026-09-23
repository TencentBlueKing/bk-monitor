"""V2/V3 原生 API 隔离及能力层选择，不依赖真实网关。"""

import inspect
import json
from unittest import mock

import pytest
import requests

from bk_monitor_base.config import Config
from bk_monitor_base.config.blueking import BkApiModuleConfig, BlueKingConfig
from bk_monitor_base.config.nodeman import NodeManConfig
from bk_monitor_base.infras import nodeman_control
from bk_monitor_base.infras.nodeman_control.contracts import PluginOperation
from bk_monitor_base.infras.nodeman_control.v2 import V2HostQueries, V2OfficialPlugins
from bk_monitor_base.infras.nodeman_control.v3 import V3HostQueries, V3OfficialPlugins
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.nodeman import api, client, v3


def make_config(multi_tenant=True, legacy_mode="apigw", enabled=False, override=""):
    api_configs = {
        "nodeman": BkApiModuleConfig.model_validate({"mode": legacy_mode, "custom_api_url": "https://v2.example.com/"})
    }
    return Config(
        blueking=BlueKingConfig(
            enable_multi_tenancy=multi_tenant,
            api_configs=api_configs,
            bk_component_api_url="https://gateway.example.com/",
        ),
        nodeman=NodeManConfig(v3_enabled=enabled, v3_api_base_url=override),
    )


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("legacy_mode", ["apigw", "esb"])
def test_v2_apis_never_change_destination(multi_tenant, enabled, legacy_mode):
    config = make_config(multi_tenant, legacy_mode, enabled=enabled)
    for _, cls in inspect.getmembers(client, inspect.isclass):
        if issubclass(cls, client.NodeManApiClient) and cls is not client.NodeManApiClient:
            assert cls(config=config)._get_api_url({"id": 1}).startswith("https://v2.example.com/")


@pytest.mark.parametrize("enabled", [False, True])
def test_capability_selection(enabled):
    with mock.patch.object(nodeman_control, "get_config", return_value=make_config(enabled=enabled)):
        assert isinstance(nodeman_control.get_host_queries(), V3HostQueries if enabled else V2HostQueries)
        assert isinstance(nodeman_control.get_official_plugins(), V3OfficialPlugins if enabled else V2OfficialPlugins)


def test_nodeman_settings_read_environment_once():
    with mock.patch.dict(
        "os.environ",
        {
            "BKAPP_ENABLE_NODEMAN_V3": "true",
            "BKAPP_BKNODEMAN_V3_API_BASE_URL": "https://nodeman-v3.example.com/custom/",
        },
    ):
        config = NodeManConfig()
    assert config.v3_enabled is True
    assert config.resolved_v3_api_base_url("https://gateway.example.com/") == "https://nodeman-v3.example.com/custom/"


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ("", "https://gateway.example.com/api/bk-nodemgr/prod/api/v3/plugin/install"),
        ("https://nodeman-v3.example.com/custom", "https://nodeman-v3.example.com/custom/api/v3/plugin/install"),
    ],
)
def test_v3_url_inferred_or_explicitly_overridden(override, expected):
    config = make_config(override=override)
    resource = v3.InstallPlugin(config=config)
    assert "nodeman_control" not in config.blueking.api_configs
    assert resource._get_api_url({}) == expected


@pytest.mark.parametrize("outcome", ["success", "api_error", "network_error"])
@pytest.mark.parametrize("multi_tenant", [False, True])
def test_native_request_response_and_no_fallback(outcome, multi_tenant):
    resource = v3.InstallPlugin(config=make_config(multi_tenant))
    payload = {"plugin": [{"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1.0"}]}
    response = mock.Mock()
    response.json.return_value = (
        {"code": 0, "data": {"workflow_id": "wf-1"}}
        if outcome == "success"
        else {"code": 40001, "message": "denied", "data": None}
    )
    with mock.patch.object(resource.session, "request", return_value=response) as request:
        if outcome == "network_error":
            request.side_effect = requests.ConnectionError("unavailable")
        if outcome == "success":
            assert resource.request(bk_tenant_id="t", user_params={"bk_username": "admin"}, params=payload) == {
                "workflow_id": "wf-1"
            }
        else:
            with pytest.raises(BkApiError if outcome == "api_error" else requests.ConnectionError):
                resource.request(bk_tenant_id="t", user_params={"bk_username": "admin"}, params=payload)
        request.assert_called_once()
        sent = request.call_args.kwargs
        assert sent["url"] == "https://gateway.example.com/api/bk-nodemgr/prod/api/v3/plugin/install"
        assert sent["json"] == payload
        assert sent["headers"]["X-Bk-Tenant-Id"] == ("t" if multi_tenant else "default")
        assert json.loads(sent["headers"]["X-Bkapi-Authorization"])["bk_username"] == "admin"


def test_v2_capabilities_keep_existing_protocol():
    with (
        mock.patch.object(api, "plugin_operate", return_value={"job_id": 7}) as operate,
        mock.patch.object(api, "get_proxies", return_value=[]) as query,
    ):
        assert V2OfficialPlugins().install("t", "bkmonitorbeat", "1.0", [1]) == PluginOperation("7")
        operate.assert_called_once_with(
            bk_tenant_id="t",
            params={
                "plugin_params": {"name": "bkmonitorbeat", "version": "1.0"},
                "job_type": "MAIN_INSTALL_PLUGIN",
                "bk_host_id": [1],
            },
        )
        assert V2HostQueries().proxies("t", 0) == []
        query.assert_called_once_with(bk_tenant_id="t", bk_cloud_id=0)


def test_base_facade_invokes_native_client():
    with (
        mock.patch.object(nodeman_control, "get_config", return_value=make_config(enabled=True)),
        mock.patch.object(v3, "install_plugin", return_value={"workflow_id": "wf-1"}) as install,
        mock.patch.object(api, "plugin_operate") as old_install,
    ):
        assert nodeman_control.official_plugins.install("t", "bkmonitorbeat", "1", [1]) == PluginOperation("wf-1")
        install.assert_called_once_with(
            bk_tenant_id="t", params={"plugin": [{"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1"}]}
        )
        old_install.assert_not_called()


def test_v2_latest_does_not_perform_v3_version_resolution():
    """关闭 V3 时 latest 的语义和调用协议均保持 V2。"""
    with (
        mock.patch.object(nodeman_control, "get_config", return_value=make_config(enabled=False)),
        mock.patch.object(api, "plugin_operate", return_value={"job_id": 7}) as install,
        mock.patch.object(v3, "list_plugins") as lookup,
    ):
        nodeman_control.official_plugins.install("t", "collector", "latest", [1])
        assert install.call_args.kwargs["params"]["plugin_params"]["version"] == "latest"
        lookup.assert_not_called()
