"""验证共存路由的地址、请求与失败隔离，无需数据库或真实网关。"""

import inspect
import json
from unittest import mock

import pytest
import requests

from bk_monitor_base.config import Config
from bk_monitor_base.config.blueking import BkApiModuleConfig, BlueKingConfig
from bk_monitor_base.infras.third_party_api.api_client import BkApiMode
from bk_monitor_base.infras.third_party_api.nodeman import api as nodeman_api
from bk_monitor_base.infras.third_party_api.nodeman import client as nodeman

CONTROL_CLIENTS = (
    nodeman.GetProxies,
    nodeman.GetProxiesByBiz,
    nodeman.IpchooserHostDetails,
    nodeman.OfficialPluginOperate,
)


def make_config(multi_tenant: bool, control: bool, legacy_mode: str = "apigw") -> Config:
    """构造测试配置，只使用虚构地址，不加载本机 YAML 或凭证。"""
    api_configs = {
        "nodeman": BkApiModuleConfig.model_validate({"mode": legacy_mode, "custom_api_url": "https://v2.example.com/"})
    }
    if control:
        api_configs["nodeman_control"] = BkApiModuleConfig.model_validate(
            {"custom_api_url": "https://control.example.com/api/"}
        )
    return Config(blueking=BlueKingConfig(enable_multi_tenancy=multi_tenant, api_configs=api_configs))


@pytest.mark.parametrize("multi_tenant", [False, True])
@pytest.mark.parametrize("control", [False, True])
@pytest.mark.parametrize("legacy_mode", ["apigw", "esb"])
def test_control_routes_and_v2_isolation(multi_tenant: bool, control: bool, legacy_mode: str) -> None:
    """只有四个控制入口使用新地址，所有其他 V2 API 均保持原配置。"""
    config = make_config(multi_tenant, control, legacy_mode)
    for client_class in CONTROL_CLIENTS:
        client = client_class(config=config)
        mode = BkApiMode.APIGW if multi_tenant or control else BkApiMode(legacy_mode)
        path = client.apigw_path if mode == BkApiMode.APIGW else client.esb_path
        if control and not multi_tenant and path.startswith("system/api/"):
            path = path.removeprefix("system/")
        root = "https://control.example.com/api/" if control else "https://v2.example.com/"
        assert client.get_api_mode() == mode
        assert client._get_api_url({}) == root + path

    for _, client_class in inspect.getmembers(nodeman, inspect.isclass):
        if (
            issubclass(client_class, nodeman.NodeManApiClient)
            and not issubclass(client_class, nodeman.NodeManControlApiClient)
            and client_class is not nodeman.NodeManApiClient
        ):
            client = client_class(config=config)
            assert client._get_api_url({"id": 1}).startswith("https://v2.example.com/")


def test_missing_control_url_does_not_fall_back() -> None:
    """配置项已存在但地址缺失时显式失败，不能误发 V2 写请求。"""
    config = make_config(False, True)
    config.blueking.api_configs["nodeman_control"] = BkApiModuleConfig(mode="apigw")
    client = nodeman.OfficialPluginOperate(config=config)
    with mock.patch.object(client.session, "request") as request:
        with pytest.raises(ValueError, match="custom_api_url"):
            client.request(bk_tenant_id="tenant-a", user_params={"bk_username": "admin"}, params={})
        request.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("multi_tenant", [False, True])
def test_control_request_and_no_retry(fails: bool, multi_tenant: bool) -> None:
    """通过真实 request 验证协议和租户头；网络失败只向控制面发送一次。"""
    client = nodeman.OfficialPluginOperate(config=make_config(multi_tenant, True))
    payload = {
        "plugin_params": {"name": "bkmonitorbeat", "version": "1.0.0"},
        "job_type": "MAIN_INSTALL_PLUGIN",
        "bk_host_id": [1],
    }
    response = mock.Mock()
    response.json.return_value = {"result": True, "data": {"job_id": 42}}
    with mock.patch.object(client.session, "request", return_value=response) as request:
        if fails:
            request.side_effect = requests.ConnectionError("unavailable")
            with pytest.raises(requests.ConnectionError):
                client.request(bk_tenant_id="tenant-a", user_params={"bk_username": "admin"}, params=payload)
        else:
            assert client.request(bk_tenant_id="tenant-a", user_params={"bk_username": "admin"}, params=payload) == {
                "job_id": 42
            }
        request.assert_called_once()
        sent = request.call_args.kwargs
        path = "system/api/plugin/operate/" if multi_tenant else "api/plugin/operate/"
        assert sent["url"] == "https://control.example.com/api/" + path
        assert sent["json"] == payload
        assert sent["headers"]["X-Bk-Tenant-Id"] == ("tenant-a" if multi_tenant else "default")
        assert json.loads(sent["headers"]["X-Bkapi-Authorization"])["bk_username"] == "admin"


def test_proxy_query_uses_get_params() -> None:
    """Proxy 兼容协议为 GET，不可将查询参数放入 POST JSON。"""
    client = nodeman.GetProxies(config=make_config(True, True))
    with mock.patch.object(client.session, "request") as request:
        client.request(bk_tenant_id="tenant-a", user_params={"bk_username": "admin"}, params={"bk_cloud_id": 1})
        assert request.call_args.kwargs["method"] == "get"
        assert request.call_args.kwargs["params"] == {"bk_cloud_id": 1}
        assert "json" not in request.call_args.kwargs


def test_plugin_operation_entry_points_remain_separate() -> None:
    """两个公开操作入口复用旧参数，只在最终目标客户端上分流。"""
    with (
        mock.patch.object(nodeman_api, "official_plugin_operate_client", return_value={"job_id": 42}) as control,
        mock.patch.object(nodeman_api, "plugin_operate_client", return_value={"job_id": 24}) as v2,
    ):
        for function, client, job_id in (
            (nodeman_api.official_plugin_operate, control, 42),
            (nodeman_api.plugin_operate, v2, 24),
        ):
            params = nodeman_api.PluginOperateParams(
                plugin_params={"name": "bkmonitorbeat"}, job_type="MAIN_INSTALL_PLUGIN", bk_host_id=[1]
            )
            assert function("tenant-a", params) == {"job_id": job_id}
            client.assert_called_once_with(bk_tenant_id="tenant-a", params=params)
            assert client.call_args.kwargs["params"]["plugin_params"]["version"] == "latest"
