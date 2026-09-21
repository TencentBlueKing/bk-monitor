"""Base 的主机查询和官方插件控制能力，独立于采集安装器及其后端。"""

from typing import Any

from bk_monitor_base.infras.third_party_api.nodeman import api


class CompatibleHostQueries:
    """NodeMan 基础设施查询的兼容实现。"""

    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        """查询云区域 Proxy。"""
        return api.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)

    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """查询业务 Proxy。"""
        return api.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    def details(self, bk_tenant_id: str, params: api.IpchooserHostDetailsParams) -> list[api.IpchooserHostDetail]:
        """查询主机身份和 Agent 状态，保留既有选择器返回契约。"""
        return api.get_ipchooser_host_details(bk_tenant_id=bk_tenant_id, params=params)


class CompatibleOfficialPlugins:
    """官方插件控制的兼容实现，任务提交与安装完成是不同状态。"""

    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> Any:
        """提交官方插件安装或升级，不操作 V2 采集器实例。"""
        params: api.PluginOperateParams = {
            "plugin_params": {"name": name, "version": version},
            "job_type": "MAIN_INSTALL_PLUGIN",
            "bk_host_id": host_ids,
        }
        return api.official_plugin_operate(bk_tenant_id=bk_tenant_id, params=params)


host_queries = CompatibleHostQueries()
official_plugins = CompatibleOfficialPlugins()
