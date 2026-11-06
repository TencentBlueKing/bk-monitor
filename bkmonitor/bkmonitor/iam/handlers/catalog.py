"""Monitor ID parsing and resource resolution using the native SDK providers.

No independent catalog queries or callback handler registry are maintained here.
"""

from dataclasses import dataclass
from typing import Literal

from iam.resource.utils import get_filter_obj

_FOLDER_PREFIX = "folder:"

@dataclass(frozen=True)
class GrafanaRef:
    """Grafana 实例 ID 的结构化表示。"""

    kind: Literal["folder", "dashboard"]
    org_id: int | None = None
    uid: str | None = None
    folder_id: int | None = None


def parse_grafana_instance_id(instance_id: str) -> GrafanaRef | None:
    """解析 Grafana 实例 ID，解析失败返回 None。

    支持三种格式（与平台回调 GrafanaDashboardProvider 约定一致）：
      * "folder:{org_id}|{folder_id}"  → GrafanaRef(kind="folder", org_id=..., folder_id=...)
      * "{org_id}|{uid}"               → GrafanaRef(kind="dashboard", org_id=..., uid=...)
      * "{uid}"                        → GrafanaRef(kind="dashboard", uid=...)
    """
    raw = str(instance_id or "")
    if not raw:
        return None
    if raw.startswith(_FOLDER_PREFIX):
        body = raw[len(_FOLDER_PREFIX) :]
        if "|" not in body:
            return None
        org_str, _, folder_str = body.partition("|")
        try:
            org_id = int(org_str)
            folder_id = int(folder_str)
        except (TypeError, ValueError):
            return None
        return GrafanaRef(kind="folder", org_id=org_id, folder_id=folder_id)
    if "|" in raw:
        org_str, _, uid = raw.partition("|")
        try:
            org_id = int(org_str)
        except (TypeError, ValueError):
            # 头段不是数字 → 按纯 uid 处理（历史兼容）
            return GrafanaRef(kind="dashboard", uid=raw)
        return GrafanaRef(kind="dashboard", org_id=org_id, uid=uid)
    return GrafanaRef(kind="dashboard", uid=raw)


def parse_iam_path(path_value: str) -> list[dict[str, str]]:
    """Parse _bk_iam_path_ value into path chain. Fully generic, not coupled to resource type or depth.

    "/space,2/"            → [{"type": "space", "id": "2"}]
    "/space,2/apm_app,3/"  → [{"type": "space", "id": "2"}, {"type": "apm_app", "id": "3"}]
    """
    segments = [s for s in (path_value or "").strip("/").split("/") if s]
    result: list[dict[str, str]] = []
    for seg in segments:
        typ, _, idx = seg.partition(",")
        if idx:
            result.append({"type": typ, "id": idx})
    return result


def get_resource_provider(resource_type):
    from monitor_web.iam.views import (
        ApmApplicationProvider,
        GrafanaDashboardProvider,
        RumApplicationProvider,
        SpaceProvider,
    )

    providers = {
        "space": SpaceProvider,
        "apm_application": ApmApplicationProvider,
        "grafana_dashboard": GrafanaDashboardProvider,
        "rum_application": RumApplicationProvider,
    }
    return providers[resource_type]()


def fetch_instance_info(rt_id, ids, requires, bk_tenant_id):
    """Resolve local metadata through the same query used by V3/V4 callbacks."""
    filters = get_filter_obj({"ids": ids, "attrs": requires}, ["ids", "attrs"])
    return get_resource_provider(rt_id).fetch_instance_info(
        filters, bk_tenant_id=bk_tenant_id, include_resource_metadata=True
    ).to_list()
