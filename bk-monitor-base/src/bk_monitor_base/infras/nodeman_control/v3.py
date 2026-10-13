"""V3 能力实现：组合原生查询、映射监控字段，不依赖 V2 API。"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from typing_extensions import override

from .contracts import HostQueries, OfficialPlugins, PluginOperation

V3Request = Callable[[str, str, dict[str, Any]], dict[str, Any]]
PAGE_SIZE = 500


def _list_items(
    request: V3Request, action: str, tenant: str, conditions: dict[str, Any], **extra: Any
) -> list[dict[str, Any]]:
    """读取全部分页；中途失败不返回部分主机，不把空过滤条件误作无结果。"""
    result: dict[tuple[int, int], dict[str, Any]] = {}
    offset = 0
    items: list[dict[str, Any]] = []
    while True:
        page = request(
            action,
            tenant,
            {
                **extra,
                "page": {"offset": offset, "limit": PAGE_SIZE},
                "exact_include_conditions": conditions,
            },
        )
        batch: list[dict[str, Any]] = page.get("items") or []
        total = int(page["total"])
        if not batch and offset < total:
            raise ValueError("NodeMan V3 returned an incomplete page")
        items.extend(batch)
        offset += len(batch)
        if offset >= total:
            break
    # 主机列表可能在分页期间更新，至少避免重复主机继续参与部署。
    if action == "list_hosts":
        for item in items:
            result[int(item["bk_host_id"]), int(item["info"]["bk_biz_id"])] = item
        return list(result.values())
    return items


class V3HostQueries(HostQueries):
    """把 V3 拓扑与节点状态转换为监控使用的主机信息。"""

    def __init__(self, request: V3Request) -> None:
        self.request: V3Request = request

    @staticmethod
    def _proxy(host: dict[str, Any]) -> dict[str, Any]:
        """NetworkAreaID 来自 CMDB BKCloudID；不把 networkunit_id 当作云区域。"""
        info = host["info"]
        state: dict[str, Any] = host.get("state") or {}
        # 下游用这些字段查主机、生成上报 URL，沿用 V2 的首个 IP，不能拼接地址列表。
        return {
            "bk_host_id": int(host["bk_host_id"]),
            "bk_biz_id": int(info["bk_biz_id"]),
            "bk_cloud_id": int(info["bk_networkarea_id"]),
            "inner_ip": (info.get("bk_host_innerip_list") or [""])[0],
            "inner_ipv6": (info.get("bk_host_innerip_v6_list") or [""])[0],
            "outer_ip": (info.get("bk_host_outerip_list") or [""])[0],
            "conn_ip": info.get("advertise_ip") or info.get("advertise_ip_v6") or "",
            "status": str(state.get("node_status") or "unknown").upper(),
            "bk_agent_id": state.get("bk_agent_id") or "",
        }

    @override
    def proxies(self, bk_tenant_id: str, bk_cloud_id: int) -> list[dict[str, Any]]:
        """按云区域查询 Proxy，0 也是有效的精确条件。"""
        hosts = _list_items(
            self.request,
            "list_hosts",
            bk_tenant_id,
            {
                "bk_networkarea_id": [bk_cloud_id],
                "node_role": ["proxy"],
            },
        )
        return [self._proxy(host) for host in hosts]

    @override
    def business_proxies(self, bk_tenant_id: str, bk_biz_id: int) -> list[dict[str, Any]]:
        """先查询业务使用的区域，再查询这些区域的 Proxy，保留跨业务 Proxy。"""
        distinct = self.request(
            "distinct_hosts",
            bk_tenant_id,
            {
                "exact_include_conditions": {"bk_biz_id": [bk_biz_id]},
            },
        )
        area_ids = [int(value) for value in distinct["bk_networkarea_id"]]
        if not area_ids:
            return []
        hosts = _list_items(
            self.request,
            "list_hosts",
            bk_tenant_id,
            {
                "bk_networkarea_id": area_ids,
                "node_role": ["proxy"],
            },
        )
        return [self._proxy(host) for host in hosts]

    @override
    def details(self, bk_tenant_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """选择器输入在能力层转换；V3 无实时读取选项，使用其返回的节点状态。"""
        groups: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
        scopes: list[dict[str, Any]] = params.get("scope_list") or []
        allowed_biz_ids = {int(scope["scope_id"]) for scope in scopes if scope["scope_type"] == "biz"}
        for selected in params["host_list"]:
            meta = selected["meta"]
            biz_id, host_id = int(meta["bk_biz_id"]), int(selected["host_id"])
            if not params.get("all_scope") and allowed_biz_ids and biz_id not in allowed_biz_ids:
                continue
            groups[biz_id][host_id] = meta
        hosts: list[dict[str, Any]] = []
        for biz_id, targets in groups.items():
            ids = list(targets)
            for start in range(0, len(ids), PAGE_SIZE):
                batch = ids[start : start + PAGE_SIZE]
                for host in _list_items(
                    self.request,
                    "list_hosts",
                    bk_tenant_id,
                    {
                        "bk_biz_id": [biz_id],
                        "bk_host_id": batch,
                    },
                ):
                    # 不能把跨业务主机组合成一个笛卡尔查询后信任额外结果。
                    if int(host["bk_host_id"]) in targets and int(host["info"]["bk_biz_id"]) == biz_id:
                        hosts.append(host)
        if not hosts:
            return []
        biz_names = {
            int(item["bk_biz_id"]): item.get("bk_biz_name", "")
            for item in _list_items(
                self.request,
                "list_businesses",
                bk_tenant_id,
                {"bk_biz_id": sorted(groups)},
            )
        }
        area_ids = sorted({int(host["info"]["bk_networkarea_id"]) for host in hosts})
        area_names = {
            int(item["bk_networkarea_id"]): item.get("bk_networkarea_name", "")
            for item in _list_items(
                self.request,
                "list_network_areas",
                bk_tenant_id,
                {"bk_networkarea_id": area_ids},
            )
        }
        result: list[dict[str, Any]] = []
        for host in hosts:
            proxy = self._proxy(host)
            info = host["info"]
            state: dict[str, Any] = host.get("state") or {}
            host_id, biz_id, area_id = proxy["bk_host_id"], proxy["bk_biz_id"], proxy["bk_cloud_id"]
            alive = int(state.get("node_status") == "running")
            result.append(
                {
                    "meta": dict(groups[biz_id][host_id]),
                    "host_id": host_id,
                    "bk_host_id": host_id,
                    "bk_biz_id": biz_id,
                    "bk_cloud_id": area_id,
                    "ip": proxy["inner_ip"],
                    "ipv6": proxy["inner_ipv6"],
                    "host_name": info.get("bk_host_name") or "",
                    "os_name": info.get("os_type") or "",
                    "os_type": info.get("os_type") or "",
                    "agent_id": proxy["bk_agent_id"],
                    "bk_agent_id": proxy["bk_agent_id"],
                    "alive": alive,
                    "bk_agent_alive": alive,
                    "cloud_area": {"id": area_id, "name": area_names.get(area_id, "")},
                    "biz": {"id": biz_id, "name": biz_names.get(biz_id, "")},
                }
            )
        return result


class V3OfficialPlugins(OfficialPlugins):
    """把独立插件部署意图映射到 V3 安装工作流。"""

    def __init__(self, request: V3Request) -> None:
        self.request: V3Request = request

    @override
    def install(self, bk_tenant_id: str, name: str, version: str, host_ids: list[int]) -> PluginOperation:
        """提交安装，保留工作流引用；不追加轮询或失败后跨版本重试。"""
        host_ids = list(dict.fromkeys(host_ids))
        if not host_ids:
            raise ValueError("No target hosts for NodeMan V3 plugin installation")
        versions = (
            self._default_versions(bk_tenant_id, name, host_ids)
            if not version or version == "latest"
            else dict.fromkeys(host_ids, version)
        )
        result = self.request(
            "install_plugin",
            bk_tenant_id,
            {
                "plugin": [
                    {"bk_host_id": host_id, "plugin_name": name, "version": versions[host_id]} for host_id in host_ids
                ],
            },
        )
        workflow_id = result.get("workflow_id")
        if not workflow_id:
            raise ValueError("NodeMan V3 install was submitted but returned no workflow_id; do not retry blindly")
        return PluginOperation(operation_id=str(workflow_id))

    def _default_versions(self, tenant: str, name: str, host_ids: list[int]) -> dict[int, str]:
        """按目标主机的平台和代际解析默认包版本，全部解析成功后才提交安装。

        Args:
            tenant: 租户 ID。
            name: 逻辑插件名，可能与实际包名不同。
            host_ids: 去重后的目标主机 ID。

        Returns:
            主机 ID 到具体版本号的映射。

        Raises:
            ValueError: 插件、主机平台信息或唯一可用默认版本缺失。
        """
        plugins = _list_items(self.request, "list_plugins", tenant, {"name": [name]})
        pkg_names = {plugin["pkg_name"] for plugin in plugins if plugin["name"] == name and plugin.get("pkg_name")}
        if len(pkg_names) != 1:
            raise ValueError(f"NodeMan V3 plugin {name!r} has no unique package")
        pkg_name = pkg_names.pop()

        hosts: dict[int, dict[str, Any]] = {}
        for start in range(0, len(host_ids), PAGE_SIZE):
            for host in _list_items(
                self.request, "list_hosts", tenant, {"bk_host_id": host_ids[start : start + PAGE_SIZE]}
            ):
                hosts[int(host["bk_host_id"])] = host
        missing = set(host_ids) - hosts.keys()
        if missing:
            raise ValueError(f"NodeMan V3 target hosts not found: {sorted(missing)}")

        groups: dict[tuple[int, str, str], list[int]] = defaultdict(list)
        for host_id in host_ids:
            host = hosts[host_id]
            info = host["info"]
            state: dict[str, Any] = host.get("state") or {}
            generation = int(state.get("node_generation") or 0)
            os_type, arch = info.get("os_type"), info.get("cpu_arch")
            if not generation or not os_type or not arch:
                raise ValueError(f"NodeMan V3 host {host_id} has no complete platform/generation")
            groups[generation, os_type, arch].append(host_id)

        result: dict[int, str] = {}
        for (generation, os_type, arch), ids in groups.items():
            packages = _list_items(
                self.request,
                "list_plugin_releases",
                tenant,
                {
                    "name": [pkg_name],
                    "platform": [{"os_type": os_type, "cpu_arch": arch}],
                    "as_default": [True],
                    "enabled": [True],
                },
                generation=generation,
            )
            versions: set[str] = set()
            for package in packages:
                release = package["release"]
                if (
                    release.get("name") == pkg_name
                    and int(release.get("generation", 0)) == generation
                    and release.get("os_type") == os_type
                    and release.get("cpu_arch") == arch
                    and release.get("as_default") is True
                    and release.get("enabled") is True
                    and release.get("version")
                ):
                    versions.add(str(release["version"]))
            if len(versions) != 1:
                raise ValueError(
                    f"NodeMan V3 plugin {name!r} has no unique enabled default version "
                    + f"for generation={generation}, platform={os_type}/{arch}"
                )
            result.update(dict.fromkeys(ids, versions.pop()))
        return result
