"""原生 V3 API 与业务能力适配回归；V2 采集安装链保持不变。"""

import importlib.util
import inspect
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import requests
from django.test import override_settings

from api.node_man import default as v2
from api.node_man_v3 import default as v3
from bkmonitor.utils import nodeman
from core.drf_resource import api
from constants.common import DEFAULT_TENANT_ID
from core.errors.api import BKAPIError
from metadata.management.commands.deploy_official_plugin import Command


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("v2_url", ["", "https://v2.example.com/"])
@pytest.mark.parametrize("control_url", ["", "https://v3.example.com/"])
def test_v2_apis_keep_original_destination(multi_tenant, v2_url, control_url):
    with override_settings(
        ENABLE_MULTI_TENANT_MODE=multi_tenant,
        BKNODEMAN_API_BASE_URL=v2_url,
        BKNODEMAN_CONTROL_API_BASE_URL=control_url,
        BK_COMPONENT_API_URL="https://gateway.example.com",
    ):
        expected = v2_url or (
            "https://gateway.example.com/api/bk-nodeman/prod/"
            if multi_tenant
            else "https://gateway.example.com/api/c/compapi/v2/nodeman/"
        )
        for _, cls in inspect.getmembers(v2, inspect.isclass):
            if (
                issubclass(cls, v2.NodeManAPIGWResource)
                and not inspect.isabstract(cls)
                and cls is not v2.UploadResource
            ):
                assert cls().base_url == expected
        assert v2.UploadResource().base_url == v2.UploadResource.base_url


@pytest.mark.parametrize("configured", [False, True])
def test_capability_backend_selection(configured):
    with override_settings(BKNODEMAN_CONTROL_API_BASE_URL="https://v3.example.com/" if configured else ""):
        assert isinstance(nodeman.get_host_queries(), nodeman.V3HostQueries if configured else nodeman.V2HostQueries)
        assert isinstance(
            nodeman.get_official_plugins(), nodeman.V3OfficialPlugins if configured else nodeman.V2OfficialPlugins
        )


def test_v3_api_registration_and_serializer():
    assert isinstance(api.node_man_v3.install_plugin, v3.InstallPluginResource)
    payload = {"plugin": [{"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1.0"}]}
    serializer = v3.InstallPluginResource.RequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == payload
    assert not issubclass(v3.InstallPluginResource, v2.NodeManAPIGWResource)
    assert isinstance(api.node_man_v3.list_plugins, v3.ListPluginsResource)
    assert isinstance(api.node_man_v3.list_plugin_releases, v3.ListPluginReleasesResource)
    payload = {
        "page": {"offset": 0, "limit": 500},
        "generation": 2,
        "exact_include_conditions": {
            "name": ["collector-package"],
            "as_default": [True],
            "enabled": [True],
            "platform": [{"os_type": "linux", "cpu_arch": "x86_64"}],
        },
    }
    serializer = v3.ListPluginReleasesResource.RequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data == payload


@pytest.mark.parametrize("outcome", ["success", "api_error", "network_error"])
@override_settings(ENABLE_MULTI_TENANT_MODE=True, BKNODEMAN_CONTROL_API_BASE_URL="https://v3.example.com/gateway/")
def test_v3_native_request_and_no_fallback(outcome):
    resource = v3.InstallPluginResource()
    payload = {"bk_tenant_id": "t", "plugin": [{"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1.0"}]}
    response = mock.Mock()
    response.json.return_value = (
        {"code": 0, "data": {"workflow_id": "wf-1"}}
        if outcome == "success"
        else {"code": 40001, "message": "denied", "data": None}
    )
    with (
        mock.patch.object(v3, "get_admin_username", return_value="tenant-admin"),
        mock.patch.object(resource.session, "request", return_value=response) as request,
    ):
        if outcome == "network_error":
            request.side_effect = requests.ConnectionError("unavailable")
        if outcome == "success":
            assert resource.request(payload) == {"workflow_id": "wf-1"}
        else:
            with pytest.raises(BKAPIError if outcome == "api_error" else requests.ConnectionError):
                resource.request(payload)
        request.assert_called_once()
        sent = request.call_args.kwargs
        assert sent["url"] == "https://v3.example.com/gateway/api/v3/plugin/install"
        assert sent["json"] == {"plugin": payload["plugin"]}
        assert sent["headers"]["X-Bk-Tenant-Id"] == "t"
        assert json.loads(sent["headers"]["x-bkapi-authorization"])["bk_username"] == "tenant-admin"


@override_settings(BKNODEMAN_CONTROL_API_BASE_URL="https://v3.example.com/")
def test_auto_deploy_proxy_keeps_v2_package_query_and_install_chain():
    spec = importlib.util.spec_from_file_location(
        "nodeman_test_auto_deploy_proxy", Path(v2.__file__).parents[2] / "metadata/task/auto_deploy_proxy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (
        mock.patch.object(api.node_man, "plugin_info", return_value=[{"version": "1.2.3"}]) as info,
        mock.patch.object(
            api.node_man, "plugin_search", return_value={"list": [{"bk_host_id": 1, "plugin_status": []}]}
        ) as search,
        mock.patch.object(api.node_man, "plugin_operate") as operate,
        mock.patch.object(api.node_man_v3, "install_plugin") as official,
    ):
        version = module.AutoDeployProxy.find_latest_version("t", "bk-collector")
        module.AutoDeployProxy.deploy_proxy("t", "bk-collector", version, 1, [1])
        info.assert_called_once_with(name="bk-collector", bk_tenant_id="t")
        search.assert_called_once()
        operate.assert_called_once_with(
            bk_tenant_id="t",
            plugin_params={"name": "bk-collector", "version": "1.2.3"},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=[1],
        )
        official.assert_not_called()


@override_settings(BKNODEMAN_CONTROL_API_BASE_URL="https://v3.example.com/")
def test_official_command_uses_native_install_without_polling():
    with (
        mock.patch.object(api.cmdb, "get_host_by_ip", return_value=[SimpleNamespace(bk_host_id=1)]),
        mock.patch.object(api.node_man_v3, "install_plugin", return_value={"workflow_id": "wf-1"}) as install,
        mock.patch.object(api.node_man, "plugin_operate") as old_install,
        mock.patch.object(api.node_man, "job_detail") as old_poll,
    ):
        Command().deploy_2_0(2, "bkmonitorbeat", "1.0", ["127.0.0.1"])
        install.assert_called_once_with(
            bk_tenant_id=DEFAULT_TENANT_ID, plugin=[{"bk_host_id": 1, "plugin_name": "bkmonitorbeat", "version": "1.0"}]
        )
        old_install.assert_not_called()
        old_poll.assert_not_called()


def test_space_mapping_keeps_caller_input_unchanged():
    params = {
        "bk_tenant_id": "t",
        "agent_realtime_state": True,
        "host_list": [{"host_id": 1, "meta": {"bk_biz_id": -3, "scope_type": "biz", "scope_id": "-3"}}],
        "scope_list": [{"scope_type": "biz", "scope_id": "-3"}],
    }
    original = deepcopy(params)
    with (
        mock.patch.object(nodeman, "validate_bk_biz_id", return_value=2),
        mock.patch.object(nodeman, "get_host_queries") as factory,
    ):
        nodeman.host_queries.details(params)
        called = factory.return_value.details.call_args
        assert called.args[0] == "t"
        assert called.args[1]["host_list"][0]["meta"]["bk_biz_id"] == 2
        assert called.args[1]["scope_list"][0]["scope_id"] == "2"
        assert params == original


@override_settings(BKNODEMAN_CONTROL_API_BASE_URL="https://v3.example.com/")
def test_official_command_resolves_latest_without_new_user_parameter():
    """沿用命令的 latest 入参，由 V3 能力实现解析，不要求运维指定版本。"""
    with (
        mock.patch.object(api.cmdb, "get_host_by_ip", return_value=[SimpleNamespace(bk_host_id=1)]),
        mock.patch.object(
            api.node_man_v3,
            "list_plugins",
            return_value={
                "total": 1,
                "items": [{"name": "collector", "pkg_name": "collector-package"}],
            },
        ),
        mock.patch.object(
            api.node_man_v3,
            "list_hosts",
            return_value={
                "total": 1,
                "items": [
                    {
                        "bk_host_id": 1,
                        "info": {
                            "bk_biz_id": 2,
                            "os_type": "linux",
                            "cpu_arch": "x86_64",
                        },
                        "state": {"node_generation": 2},
                    }
                ],
            },
        ),
        mock.patch.object(
            api.node_man_v3,
            "list_plugin_releases",
            return_value={
                "total": 1,
                "items": [
                    {
                        "release": {
                            "name": "collector-package",
                            "generation": 2,
                            "os_type": "linux",
                            "cpu_arch": "x86_64",
                            "enabled": True,
                            "as_default": True,
                            "version": "1.2",
                        }
                    }
                ],
            },
        ) as packages,
        mock.patch.object(api.node_man_v3, "install_plugin", return_value={"workflow_id": "wf-1"}) as install,
        mock.patch.object(api.node_man, "plugin_operate") as old_install,
    ):
        Command().deploy_2_0(2, "collector", "latest", ["127.0.0.1"])
        assert packages.call_args.kwargs["generation"] == 2
        assert packages.call_args.kwargs["exact_include_conditions"]["name"] == ["collector-package"]
        install.assert_called_once_with(
            bk_tenant_id=DEFAULT_TENANT_ID,
            plugin=[
                {"bk_host_id": 1, "plugin_name": "collector", "version": "1.2"},
            ],
        )
        old_install.assert_not_called()
