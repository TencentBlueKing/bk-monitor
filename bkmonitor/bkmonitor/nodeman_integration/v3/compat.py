from __future__ import annotations

from bkmonitor.nodeman_integration.v3.client import NodeManV3HTTPClient, NodeManV3RequestContext
from bkmonitor.nodeman_integration.v3.client.host import HostClient
from bkmonitor.nodeman_integration.v3.client.package import PackageClient, PluginClient
from bkmonitor.nodeman_integration.v3.client.process import ProcessClient
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.version import get_max_version


HOST_PAGE_SIZE = 500


def ipchooser_host_detail(params: dict, *, client=None) -> list[dict]:
    """Return V3 host state in the small V2 shape consumed by the existing IP chooser."""

    host_ids = sorted(
        {int(item["host_id"]) for item in params.get("host_list") or () if item.get("host_id") is not None}
    )
    if not host_ids:
        return []
    bk_biz_id = _bk_biz_id(params)
    context = NodeManV3RequestContext(
        bk_tenant_id=params.get("bk_tenant_id") or _tenant_id(params, bk_biz_id),
        bk_biz_id=bk_biz_id,
    )
    client = client or HostClient(NodeManV3HTTPClient())
    items = []
    offset = 0
    while offset < len(host_ids):
        batch = host_ids[offset : offset + 500]
        result = client.list(
            {
                "page": {"offset": 0, "limit": len(batch)},
                "only_count": False,
                "exact_include_conditions": {
                    "bk_host_id": batch,
                    "bk_biz_id": [bk_biz_id],
                },
            },
            context=context,
        )
        items.extend(result.get("items") or [])
        offset += len(batch)

    return [
        {
            "host_id": int(item["bk_host_id"]),
            "alive": int(str((item.get("state") or {}).get("node_status") or "").lower() == "running"),
            "version": (item.get("state") or {}).get("node_version") or "",
        }
        for item in items
        if item.get("bk_host_id") is not None
    ]


def plugin_exists(*, bk_tenant_id: str, bk_biz_id: int, plugin_name: str, client=None) -> bool:
    client = client or PluginClient(NodeManV3HTTPClient())
    result = client.list(
        {
            "page": {"offset": 0, "limit": 2},
            "only_count": False,
            "exact_include_conditions": {"name": [plugin_name]},
        },
        context=NodeManV3RequestContext(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id),
    )
    return bool(result.get("items"))


def latest_enabled_plugin_version(*, bk_tenant_id: str, plugin_name: str, client=None) -> str:
    """Return the greatest enabled V3 release version for a plugin."""

    client = client or PackageClient(NodeManV3HTTPClient())
    versions = []
    offset = 0
    while True:
        result = client.list_plugin_releases(
            {
                "page": {"offset": offset, "limit": HOST_PAGE_SIZE},
                "only_count": False,
                "exact_include_conditions": {"name": [plugin_name], "enabled": [True]},
            },
            context=NodeManV3RequestContext(bk_tenant_id=bk_tenant_id, bk_biz_id=0),
        )
        page = result.get("items") or []
        versions.extend(version for item in page if (version := (item.get("release") or {}).get("version")))
        offset += len(page)
        if not page or offset >= int(result.get("total", len(page))):
            break
    if not versions:
        raise NodeManV3PayloadError(f"NodeMan V3 has no enabled release for plugin {plugin_name}")
    return get_max_version("0.0.0", versions)


def plugin_search_host_status(
    *,
    bk_tenant_id: str,
    bk_host_ids: list[int],
    bk_biz_id: int | None = None,
    plugin_names: list[str] | None = None,
    host_client=None,
    process_client=None,
) -> list[dict]:
    """Return V3 host and process state in the V2 plugin_search shape."""

    host_ids = sorted({int(host_id) for host_id in bk_host_ids})
    if not host_ids:
        return []
    host_client = host_client or HostClient(NodeManV3HTTPClient())
    process_client = process_client or ProcessClient(NodeManV3HTTPClient())
    hosts = _list_hosts(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        exact_conditions={"bk_host_id": host_ids},
        client=host_client,
    )
    resolved_host_ids = {int(host["bk_host_id"]) for host in hosts}
    missing_host_ids = sorted(set(host_ids) - resolved_host_ids)
    if missing_host_ids:
        raise NodeManV3PayloadError(f"NodeMan V3 host query did not resolve host IDs: {missing_host_ids}")
    processes = _list_processes(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        bk_host_ids=host_ids,
        plugin_names=plugin_names,
        client=process_client,
    )
    processes_by_host: dict[int, list[dict]] = {}
    for process in processes:
        host_id = int(process["bk_host_id"])
        process_info = process.get("process_info") or {}
        process_identity = process.get("process_identity") or {}
        processes_by_host.setdefault(host_id, []).append(
            {
                "name": process.get("plugin_name") or "",
                "version": process_info.get("version") or "",
                "status": process_info.get("status") or "",
                "setup_path": process_identity.get("setup_path") or "",
            }
        )

    result = []
    for host in hosts:
        host_id = int(host["bk_host_id"])
        info = host.get("info") or {}
        state = host.get("state") or {}
        inner_ips = info.get("bk_host_innerip_list") or []
        inner_ipv6s = info.get("bk_host_innerip_v6_list") or []
        result.append(
            {
                "bk_host_id": host_id,
                "bk_biz_id": info.get("bk_biz_id"),
                "bk_cloud_id": info.get("bk_networkarea_id"),
                "inner_ip": inner_ips[0] if inner_ips else "",
                "inner_ipv6": inner_ipv6s[0] if inner_ipv6s else "",
                "status": str(state.get("node_status") or "").upper(),
                "plugin_status": processes_by_host.get(host_id, []),
            }
        )
    return result


def _list_processes(
    *,
    bk_tenant_id: str,
    bk_biz_id: int | None,
    bk_host_ids: list[int],
    plugin_names: list[str] | None,
    client,
) -> list[dict]:
    items = []
    for batch_start in range(0, len(bk_host_ids), HOST_PAGE_SIZE):
        batch = bk_host_ids[batch_start : batch_start + HOST_PAGE_SIZE]
        offset = 0
        while True:
            exact_conditions = {"bk_host_id": batch}
            if plugin_names:
                exact_conditions["plugin_name"] = plugin_names
            result = client.list(
                {
                    "page": {"offset": offset, "limit": HOST_PAGE_SIZE},
                    "only_count": False,
                    "exact_include_conditions": exact_conditions,
                },
                context=NodeManV3RequestContext(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id),
            )
            page = result.get("items") or []
            items.extend(page)
            offset += len(page)
            if not page or offset >= int(result.get("total", len(page))):
                break
    return items


def get_proxies(*, bk_tenant_id: str, bk_cloud_id: int, client=None) -> list[dict]:
    """Return V3 Proxy hosts in the small V2 shape consumed by monitor services."""

    return _proxy_items(
        _list_hosts(
            bk_tenant_id=bk_tenant_id,
            exact_conditions={"bk_networkarea_id": [int(bk_cloud_id)], "node_role": ["proxy"]},
            client=client,
        )
    )


def get_proxies_by_biz(*, bk_tenant_id: str, bk_biz_id: int, client=None) -> list[dict]:
    """Resolve the Proxy hosts serving every network area currently used by a business."""

    client = client or HostClient(NodeManV3HTTPClient())
    business_hosts = _list_hosts(
        bk_tenant_id=bk_tenant_id,
        exact_conditions={"bk_biz_id": [int(bk_biz_id)]},
        bk_biz_id=bk_biz_id,
        client=client,
    )
    networkarea_ids = sorted(
        {
            int(info["bk_networkarea_id"])
            for item in business_hosts
            if (info := item.get("info") or {}).get("bk_networkarea_id") is not None
        }
    )
    if not networkarea_ids:
        return []
    return _proxy_items(
        _list_hosts(
            bk_tenant_id=bk_tenant_id,
            exact_conditions={"bk_networkarea_id": networkarea_ids, "node_role": ["proxy"]},
            client=client,
        )
    )


def _list_hosts(*, bk_tenant_id: str, exact_conditions: dict, client, bk_biz_id: int | None = None) -> list[dict]:
    items = []
    offset = 0
    while True:
        result = client.list(
            {
                "page": {"offset": offset, "limit": HOST_PAGE_SIZE},
                "only_count": False,
                "exact_include_conditions": exact_conditions,
            },
            context=NodeManV3RequestContext(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id),
        )
        page = result.get("items") or []
        items.extend(page)
        offset += len(page)
        if not page or offset >= int(result.get("total", len(page))):
            return items


def _proxy_items(items: list[dict]) -> list[dict]:
    proxies = []
    for item in items:
        info = item.get("info") or {}
        state = item.get("state") or {}
        inner_ips = info.get("bk_host_innerip_list") or []
        inner_ipv6s = info.get("bk_host_innerip_v6_list") or []
        proxies.append(
            {
                "bk_host_id": item.get("bk_host_id"),
                "bk_biz_id": info.get("bk_biz_id"),
                "bk_cloud_id": info.get("bk_networkarea_id"),
                "inner_ip": inner_ips[0] if inner_ips else "",
                "inner_ipv6": inner_ipv6s[0] if inner_ipv6s else "",
                "status": str(state.get("node_status") or "").upper(),
            }
        )
    return proxies


def _bk_biz_id(params: dict) -> int:
    for item in params.get("host_list") or ():
        meta = item.get("meta") or {}
        if meta.get("bk_biz_id") is not None:
            return int(meta["bk_biz_id"])
    for item in params.get("scope_list") or ():
        if item.get("scope_id") is not None:
            return int(item["scope_id"])
    if params.get("bk_biz_id") is not None:
        return int(params["bk_biz_id"])
    raise ValueError("bk_biz_id is required for NodeMan V3 host status query")


def _tenant_id(params: dict, bk_biz_id: int) -> str:
    for item in params.get("host_list") or ():
        meta = item.get("meta") or {}
        if meta.get("bk_tenant_id"):
            return str(meta["bk_tenant_id"])
    return bk_biz_id_to_bk_tenant_id(bk_biz_id)
