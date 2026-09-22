"""监控 V2 能力实现，V2 请求和结果仅在此处组装。"""

from typing import Any

from bk_monitor_base.infras.nodeman_control.contracts import HostQueries, OfficialPlugins, PluginOperation

from core.drf_resource import api


class V2HostQueries(HostQueries):
    """保留原有 V2 主机查询协议。"""

    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        return api.node_man.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)

    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        return api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    def details(self, bk_tenant_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return api.node_man.ipchooser_host_detail({**params, "bk_tenant_id": bk_tenant_id})


class V2OfficialPlugins(OfficialPlugins):
    """独立官方插件安装，与采集器的 V2 安装入口分开。"""

    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> PluginOperation:
        result = api.node_man.plugin_operate(
            bk_tenant_id=bk_tenant_id,
            plugin_params={"name": name, "version": version},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=host_ids,
        )
        return PluginOperation(operation_id=str(result["job_id"]))
