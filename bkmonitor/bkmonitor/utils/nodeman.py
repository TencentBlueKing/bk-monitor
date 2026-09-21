"""主机查询与官方插件控制的能力入口，兼容协议仅存在于此实现和 API 层。"""

from typing import Any

from core.drf_resource import api


class CompatibleHostQueries:
    """通过兼容协议查询基础设施，不参与 V2 采集插件实例查询。"""

    def proxies(self, bk_cloud_id: int, bk_tenant_id: str | None = None) -> list[dict]:
        """查询云区域 Proxy，租户省略时沿用框架上下文。"""
        params = {"bk_cloud_id": bk_cloud_id}
        if bk_tenant_id is not None:
            params["bk_tenant_id"] = bk_tenant_id
        return api.node_man.get_proxies(**params)

    def business_proxies(self, bk_biz_id: int, bk_tenant_id: str | None = None) -> list[dict]:
        """查询业务 Proxy。"""
        params = {"bk_biz_id": bk_biz_id}
        if bk_tenant_id is not None:
            params["bk_tenant_id"] = bk_tenant_id
        return api.node_man.get_proxies_by_biz(**params)

    def details(self, params: dict | None = None, **kwargs: Any) -> list[dict]:
        """保持选择器字段契约，后续原生实现负责映射目标身份和 Agent 状态。"""
        return api.node_man.ipchooser_host_detail({**(params or {}), **kwargs})


class CompatibleOfficialPlugins:
    """独立官方插件实例控制；不能用于 V2 采集器 Ensure 或自动部署。"""

    def install(self, name: str, version: str, host_ids: list[int], bk_tenant_id: str | None = None) -> Any:
        """提交安装或升级；返回提交结果，不代表主机上已完成安装。"""
        params = {
            "plugin_params": {"name": name, "version": version},
            "job_type": "MAIN_INSTALL_PLUGIN",
            "bk_host_id": host_ids,
        }
        if bk_tenant_id is not None:
            params["bk_tenant_id"] = bk_tenant_id
        return api.node_man.official_plugin_operate(**params)


host_queries = CompatibleHostQueries()
official_plugins = CompatibleOfficialPlugins()
