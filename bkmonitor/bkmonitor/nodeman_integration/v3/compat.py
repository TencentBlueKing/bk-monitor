from __future__ import annotations

from bkmonitor.nodeman_integration.v3.client import NodeManV3HTTPClient, NodeManV3RequestContext
from bkmonitor.nodeman_integration.v3.client.host import HostClient
from bkmonitor.nodeman_integration.v3.client.package import PluginClient
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id


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
