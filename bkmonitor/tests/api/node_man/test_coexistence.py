"""NodeMan 共存路由：控制面可拆分，采集和插件开发保持 V2。"""

import inspect
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import requests
from django.test import override_settings

from api.node_man import default as nodeman
from core.drf_resource import api
from metadata.management.commands.deploy_official_plugin import Command
from bkmonitor.utils.nodeman import host_queries, official_plugins


CONTROL_RESOURCES = (
    nodeman.GetProxiesResource,
    nodeman.GetProxiesByBizResource,
    nodeman.IpchooserHostDetailResource,
    nodeman.OfficialPluginOperateResource,
)
V2_RESOURCES = tuple(
    resource
    for _, resource in inspect.getmembers(nodeman, inspect.isclass)
    if issubclass(resource, nodeman.NodeManAPIGWResource)
    and not inspect.isabstract(resource)
    and resource not in CONTROL_RESOURCES
    and resource is not nodeman.UploadResource
)


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("v2_url", ["", "https://v2.example.com/api/"])
@pytest.mark.parametrize("control_url", ["", "https://control.example.com/api"])
def test_control_route_and_legacy_fallback(multi_tenant, v2_url, control_url):
    with override_settings(
        ENABLE_MULTI_TENANT_MODE=multi_tenant,
        BKNODEMAN_API_BASE_URL=v2_url,
        BKNODEMAN_CONTROL_API_BASE_URL=control_url,
        BK_COMPONENT_API_URL="https://gateway.example.com",
    ):
        legacy_url = v2_url or (
            "https://gateway.example.com/api/bk-nodeman/prod/"
            if multi_tenant
            else "https://gateway.example.com/api/c/compapi/v2/nodeman/"
        )
        uses_apigw = bool(control_url or v2_url or multi_tenant)
        system_prefix = "system/" if uses_apigw and multi_tenant else ""
        paths = (
            system_prefix + "api/host/proxies/",
            system_prefix + "api/host/biz_proxies/",
            ("system/" if uses_apigw else "") + "core/api/ipchooser_host/details/",
            system_prefix + "api/plugin/operate/",
        )
        for resource_class, path in zip(CONTROL_RESOURCES, paths):
            resource = resource_class()
            assert resource.get_request_url({}) == (control_url or legacy_url).rstrip("/") + "/" + path
        for resource_class in V2_RESOURCES:
            assert resource_class().base_url == legacy_url
        assert nodeman.UploadResource().base_url == nodeman.UploadResource.base_url


def test_official_operation_registration_and_protocol():
    assert isinstance(api.node_man.official_plugin_operate, nodeman.OfficialPluginOperateResource)
    assert not isinstance(api.node_man.plugin_operate, nodeman.NodeManControlAPIGWResource)
    payload = {"job_type": "MAIN_INSTALL_PLUGIN", "plugin_params": {"name": "bkmonitorbeat"}, "bk_host_id": [1]}
    for resource_class in (nodeman.PluginOperate, nodeman.OfficialPluginOperateResource):
        serializer = resource_class.RequestSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        assert serializer.validated_data["plugin_params"] == {"name": "bkmonitorbeat", "version": "latest"}


@pytest.mark.parametrize("fails", [False, True])
@override_settings(
    ENABLE_MULTI_TENANT_MODE=True,
    BKNODEMAN_API_BASE_URL="https://v2.example.com/",
    BKNODEMAN_CONTROL_API_BASE_URL="https://control.example.com/",
)
def test_control_request_preserves_payload_tenant_and_never_falls_back(fails):
    resource = nodeman.OfficialPluginOperateResource()
    payload = {
        "bk_tenant_id": "tenant-a",
        "job_type": "MAIN_INSTALL_PLUGIN",
        "plugin_params": {"name": "bkmonitorbeat", "version": "1.0.0"},
        "bk_host_id": [1],
    }
    response = mock.Mock()
    response.json.return_value = {"result": True, "code": 0, "data": {"job_id": 42}}
    with (
        mock.patch.object(nodeman, "get_admin_username", return_value="tenant-admin"),
        mock.patch.object(nodeman, "get_request_username", return_value="operator"),
        mock.patch.object(resource.session, "request", return_value=response) as request,
    ):
        if fails:
            request.side_effect = requests.ConnectionError("unavailable")
            with pytest.raises(requests.ConnectionError):
                resource.perform_request(payload)
        else:
            assert resource.perform_request(payload) == {"job_id": 42}
        request.assert_called_once()
        sent = request.call_args.kwargs
        assert sent["url"] == "https://control.example.com/system/api/plugin/operate/"
        assert sent["json"]["plugin_params"] == payload["plugin_params"]
        assert sent["json"]["bk_host_id"] == [1]
        assert sent["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
        assert json.loads(sent["headers"]["x-bkapi-authorization"])["bk_username"] == "tenant-admin"


def test_auto_deploy_proxy_keeps_v2_package_query_and_install_chain():
    # web 测试环境没有后台 Redis 配置；只加载待测文件，避免 task/__init__ 注册全部后台任务。
    spec = importlib.util.spec_from_file_location(
        "nodeman_test_auto_deploy_proxy", Path(nodeman.__file__).parents[2] / "metadata/task/auto_deploy_proxy.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    auto_deploy_proxy = module.AutoDeployProxy
    with (
        mock.patch.object(api.node_man, "plugin_info", return_value=[{"version": "1.2.3"}]) as info,
        mock.patch.object(
            api.node_man, "plugin_search", return_value={"list": [{"bk_host_id": 1, "plugin_status": []}]}
        ) as search,
        mock.patch.object(api.node_man, "plugin_operate") as operate,
        mock.patch.object(api.node_man, "official_plugin_operate") as official,
    ):
        version = auto_deploy_proxy.find_latest_version("tenant-a", "bk-collector")
        auto_deploy_proxy.deploy_proxy("tenant-a", "bk-collector", version, 1, [1])
        info.assert_called_once_with(name="bk-collector", bk_tenant_id="tenant-a")
        search.assert_called_once()
        operate.assert_called_once_with(
            bk_tenant_id="tenant-a",
            plugin_params={"name": "bk-collector", "version": "1.2.3"},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=[1],
        )
        official.assert_not_called()


def test_official_deploy_command_submits_to_control_plane_only():
    with (
        mock.patch.object(api.cmdb, "get_host_by_ip", return_value=[SimpleNamespace(bk_host_id=1)]),
        mock.patch.object(api.node_man, "official_plugin_operate") as official,
        mock.patch.object(api.node_man, "plugin_operate") as v2_operate,
        mock.patch.object(api.node_man, "job_detail") as job_detail,
    ):
        Command().deploy_2_0(2, "bkmonitorbeat", "1.0.0", ["127.0.0.1"])
        official.assert_called_once_with(
            plugin_params={"name": "bkmonitorbeat", "version": "1.0.0"},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=[1],
        )
        v2_operate.assert_not_called()
        job_detail.assert_not_called()


def test_control_capabilities_preserve_intent_and_tenant():
    """能力入口保留业务安装意图和租户，不调用 V2 插件安装入口。"""
    with (
        mock.patch.object(api.node_man, "official_plugin_operate", return_value={"job_id": 7}) as control,
        mock.patch.object(api.node_man, "plugin_operate") as v2,
        mock.patch.object(api.node_man, "get_proxies_by_biz", return_value=[]) as query,
    ):
        assert official_plugins.install("bkmonitorbeat", "1.0", [1], "tenant-a") == {"job_id": 7}
        control.assert_called_once_with(
            bk_tenant_id="tenant-a",
            plugin_params={"name": "bkmonitorbeat", "version": "1.0"},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=[1],
        )
        v2.assert_not_called()
        assert host_queries.business_proxies(bk_biz_id=2, bk_tenant_id="tenant-a") == []
        query.assert_called_once_with(bk_biz_id=2, bk_tenant_id="tenant-a")
