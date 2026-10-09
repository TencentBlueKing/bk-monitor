"""完整 V2 后台的能力实现；仅此层组装 V2 请求。"""

from typing import Any, cast

from typing_extensions import override

from bk_monitor_base.infras.third_party_api.nodeman import api

from .contracts import HostQueries, OfficialPlugins, PluginOperation


class V2HostQueries(HostQueries):
    """沿用 V2 主机查询，控制面配置不改变 V2 API 的目的地。"""

    @override
    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        """查询云区域 Proxy。"""
        return api.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)

    @override
    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """查询业务使用的 Proxy。"""
        return api.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    @override
    def details(self, bk_tenant_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """调用 V2 选择器接口，保留原有实时状态参数。"""
        return cast(
            list[dict[str, Any]],
            api.get_ipchooser_host_details(
                bk_tenant_id=bk_tenant_id, params=cast(api.IpchooserHostDetailsParams, cast(object, params))
            ),
        )


class V2OfficialPlugins(OfficialPlugins):
    """V2 独立官方插件安装，不改变自动采集器安装入口。"""

    @override
    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> PluginOperation:
        """将 V2 job_id 转为业务操作引用。"""
        result = api.plugin_operate(
            bk_tenant_id=bk_tenant_id,
            params={
                "plugin_params": {"name": name, "version": version},
                "job_type": "MAIN_INSTALL_PLUGIN",
                "bk_host_id": host_ids,
            },
        )
        return PluginOperation(operation_id=str(result["job_id"]))
