"""NodeMan V3 原生 API；不继承 V2 客户端，不转换成 V2 请求或结果。"""

from abc import ABC
from typing import Any, ClassVar

import requests
from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient, BkApiMode
from bk_monitor_base.infras.third_party_api.errors import BkApiError


class NodeManV3Client(BkApiClient, ABC):
    """只读取 V3 服务入口；错误响应即使没有 result 字段也必须失败。"""

    abstract_class: ClassVar[bool] = True
    module_name: ClassVar[str] = "nodeman_control"
    method: ClassVar[str] = "POST"
    esb_base_url: ClassVar[str] = ""
    esb_path: ClassVar[str] = ""
    apigw_base_url: ClassVar[str] = ""

    @override
    def _get_api_mode(self) -> BkApiMode:
        """V3 使用网关鉴权，不存在 V2 ESB 回退。"""
        return BkApiMode.APIGW

    @override
    def _get_api_url(self, params: dict[str, Any]) -> str:
        """配置为 V3 服务根地址，路径在各 API 中完整定义。"""
        config = self.config.blueking.api_configs.get(self.module_name)
        if config is None or not config.custom_api_url:
            raise ValueError("nodeman_control.custom_api_url must be configured")
        return f"{str(config.custom_api_url).rstrip('/')}/{self.apigw_path}"

    @override
    def handle_response(self, response: requests.Response) -> Any:
        """按 V3 code/data 契约解析，不把错误包装成空成功。"""
        result = super().handle_response(response)
        if result.get("code") != 0:
            raise BkApiError(
                module=self.module_name,
                action=self.action,
                method=self.method,
                url=response.request.url or "",
                message=result.get("message") or str(result),
                third_api_error_code=str(result.get("code")),
            )
        return result["data"]


class ListHosts(NodeManV3Client):
    """分页查询 V3 主机。"""

    action: ClassVar[str] = "list_hosts"
    apigw_path: ClassVar[str] = "api/v3/topo/host/list"


class DistinctHosts(NodeManV3Client):
    """查询业务使用的网络区域等主机属性。"""

    action: ClassVar[str] = "distinct_hosts"
    apigw_path: ClassVar[str] = "api/v3/topo/host/distinct"


class ListBusinesses(NodeManV3Client):
    """查询业务名称。"""

    action: ClassVar[str] = "list_businesses"
    apigw_path: ClassVar[str] = "api/v3/topo/business/list"


class ListNetworkAreas(NodeManV3Client):
    """查询网络区域名称。"""

    action: ClassVar[str] = "list_network_areas"
    apigw_path: ClassVar[str] = "api/v3/topo/networkarea/list"


class ListPlugins(NodeManV3Client):
    """查询逻辑插件与包名映射。"""

    action: ClassVar[str] = "list_plugins"
    apigw_path: ClassVar[str] = "api/v3/plugin/list"


class ListPluginReleases(NodeManV3Client):
    """查询指定代际、平台的默认插件包。"""

    action: ClassVar[str] = "list_plugin_releases"
    apigw_path: ClassVar[str] = "api/v3/package/release/plugin/list"


class InstallPlugin(NodeManV3Client):
    """提交 V3 插件安装，原样返回 workflow_id。"""

    action: ClassVar[str] = "install_plugin"
    apigw_path: ClassVar[str] = "api/v3/plugin/install"


list_hosts = ListHosts()
distinct_hosts = DistinctHosts()
list_businesses = ListBusinesses()
list_network_areas = ListNetworkAreas()
install_plugin = InstallPlugin()
list_plugins = ListPlugins()
list_plugin_releases = ListPluginReleases()
