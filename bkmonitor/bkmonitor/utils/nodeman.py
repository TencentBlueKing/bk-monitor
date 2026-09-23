"""节点控制能力入口：在业务能力层选择后端，API 层保持各自原生协议。"""

from copy import deepcopy
from typing import Any

from bk_monitor_base.config.nodeman import is_nodeman_v3_enabled
from bk_monitor_base.infras.nodeman_control.contracts import HostQueries, OfficialPlugins, PluginOperation
from bk_monitor_base.infras.nodeman_control.v3 import V3HostQueries, V3OfficialPlugins

from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.nodeman_v2 import V2HostQueries, V2OfficialPlugins
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api


def _request_v3(action: str, tenant: str, params: dict[str, Any]) -> dict[str, Any]:
    return getattr(api.node_man_v3, action)(bk_tenant_id=tenant, **params)


_v2_hosts, _v3_hosts = V2HostQueries(), V3HostQueries(_request_v3)
_v2_plugins, _v3_plugins = V2OfficialPlugins(), V3OfficialPlugins(_request_v3)


def get_host_queries() -> HostQueries:
    return _v3_hosts if is_nodeman_v3_enabled() else _v2_hosts


def get_official_plugins() -> OfficialPlugins:
    return _v3_plugins if is_nodeman_v3_enabled() else _v2_plugins


def _tenant(tenant: str | None, biz_id: int | None = None) -> str:
    if tenant is not None:
        return tenant
    if biz_id is not None:
        return bk_biz_id_to_bk_tenant_id(biz_id)
    return get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID


class HostQueryService:
    """对调用方隐藏 V2/V3；空间 ID 在能力入口转换为 CMDB 业务 ID。"""

    def proxies(self, bk_cloud_id: int, bk_tenant_id: str | None = None) -> list[dict]:
        return get_host_queries().proxies(_tenant(bk_tenant_id), bk_cloud_id)

    def business_proxies(self, bk_biz_id: int, bk_tenant_id: str | None = None) -> list[dict]:
        return get_host_queries().business_proxies(_tenant(bk_tenant_id, bk_biz_id), validate_bk_biz_id(bk_biz_id))

    def details(self, params: dict | None = None, **kwargs: Any) -> list[dict]:
        query = deepcopy({**(params or {}), **kwargs})
        tenant = _tenant(query.pop("bk_tenant_id", None))
        for host in query.get("host_list", []):
            meta = host["meta"]
            meta["bk_biz_id"] = validate_bk_biz_id(int(meta["bk_biz_id"]))
            if meta.get("scope_type") == "biz":
                meta["scope_id"] = str(meta["bk_biz_id"])
        for scope in query.get("scope_list", []):
            if scope["scope_type"] == "biz":
                scope["scope_id"] = str(validate_bk_biz_id(int(scope["scope_id"])))
        return get_host_queries().details(tenant, query)


class OfficialPluginService:
    """独立官方插件安装；返回操作引用，不把提交成功视作安装完成。"""

    def install(self, name: str, version: str, host_ids: list[int], bk_tenant_id: str | None = None) -> PluginOperation:
        return get_official_plugins().install(_tenant(bk_tenant_id), name, version, host_ids)


host_queries = HostQueryService()
official_plugins = OfficialPluginService()
