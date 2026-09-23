"""Base 节点控制能力入口；后端选择只在这一层发生。"""

from typing import Any

from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.infras.nodeman_runtime import nodeman_v3_enabled
from bk_monitor_base.infras.third_party_api.nodeman import v3 as api_v3

from .contracts import HostQueries, OfficialPlugins, PluginOperation
from .v2 import V2HostQueries, V2OfficialPlugins
from .v3 import V3HostQueries, V3OfficialPlugins


def _request_v3(action: str, tenant: str, params: dict[str, Any]) -> dict[str, Any]:
    """把能力实现交给 Base 原生 V3 API，API 自身不做版本判断。"""
    return getattr(api_v3, action)(bk_tenant_id=tenant, params=params)


_v2_hosts, _v3_hosts = V2HostQueries(), V3HostQueries(_request_v3)
_v2_plugins, _v3_plugins = V2OfficialPlugins(), V3OfficialPlugins(_request_v3)


def get_host_queries() -> HostQueries:
    """由统一环境开关选择节点控制面。"""
    return _v3_hosts if nodeman_v3_enabled(get_config().nodeman) else _v2_hosts


def get_official_plugins() -> OfficialPlugins:
    """选择独立官方插件控制实现，与采集器安装的 V2 API 无关。"""
    return _v3_plugins if nodeman_v3_enabled(get_config().nodeman) else _v2_plugins


class HostQueryService(HostQueries):
    """稳定业务入口，调用方无需知道后端版本。"""

    @override
    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        """查询云区域 Proxy。"""
        return get_host_queries().proxies(bk_tenant_id, bk_cloud_id)

    @override
    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """查询业务使用的 Proxy。"""
        return get_host_queries().business_proxies(bk_tenant_id, bk_biz_id)

    @override
    def details(self, bk_tenant_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """查询选择器主机详情。"""
        return get_host_queries().details(bk_tenant_id, params)


class OfficialPluginService(OfficialPlugins):
    """稳定的官方插件提交入口。"""

    @override
    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> PluginOperation:
        """提交安装并返回操作引用。"""
        return get_official_plugins().install(bk_tenant_id, name, version, host_ids)


host_queries = HostQueryService()
official_plugins = OfficialPluginService()
