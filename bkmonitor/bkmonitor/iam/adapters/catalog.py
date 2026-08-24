"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# 资源目录（catalog）—— 监控平台业务侧资源实例目录查询（provider 无关）
#
# 职责：按资源类型提供两类目录能力，全部使用业务 ID / 业务命名进出，
# 不掺任何平台 codec / provider 方言：
#   - list_instances：按父资源分页枚举实例（遍历资源数据库表）；
#   - fetch_instance_info：按 ID 批量查询实例展示名 / 父链。
#
# 消费方（四方复用）：
#   - adapters/v4/callback/handlers.py：IAM v4 平台反向回调 handler 的薄封装
#     （codec 编解码由 V4CallbackService 在 dispatch 层统一完成）；
#   - adapters/resolver.py：鉴权路径单实例补全（name / ancestor_chain）；
#   - kernel_api RPC（后续 PR）：权限树父路径 / 展示名批量补全。
#
# ID 口径约定：
#   - space：bk_biz_id（bkcc 空间为正 space_id，其余为 -pk，与 bkm_space 约定一致）
#   - apm_application / rum_application：application_id（即模型主键 pk）
#   - grafana_dashboard：三种格式，见 parse_grafana_instance_id
#
# 展示名约定：
#   - space："[{空间类型中文名}] {空间名}"
#   - apm_application / rum_application：display_name=app_alias（平台 UI 口径）、
#     name=app_name（权限树口径），两者同时返回，由消费方按用途自取
#   - grafana_dashboard：仪表盘 "[仪表盘] {目录}/{标题}"、目录 "[目录] {标题}"（平台 UI 口径）
#
# 依赖说明：各业务模型（apm_web / rum_web / bk_dataview / metadata）均为可选应用，
# 故在函数内惰性 import，与 adapters/resolver.py 的防御风格保持一致。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
import operator
from dataclasses import dataclass
from functools import reduce
from typing import Any, Literal
from collections.abc import Callable

from django.db.models import Q

from constants.common import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)

_FOLDER_PREFIX = "folder:"
_GENERAL_FOLDER_NAME = "General"


# ================================================================
# ID / 路径解析（纯函数）
# ================================================================


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


# ================================================================
# 目录查询接口
# ================================================================


def list_instances(
    rt_id: str,
    filter_data: dict,
    page: dict,
    bk_tenant_id: str = DEFAULT_TENANT_ID,
) -> dict:
    """按父资源分页枚举指定资源类型的实例。

    Args:
        rt_id: 资源类型 ID（业务命名，如 "space" / "apm_application"）。
        filter_data: 过滤条件，支持 {"parent": {"type": ..., "id": ...}, "keyword": ...}。
        page: 分页参数 {"page": int, "page_size": int}。
        bk_tenant_id: 租户 ID，默认 system。

    Returns:
        {"count": int, "results": [{"id": 业务 ID, "display_name": 展示名, ...}]}
    """
    handler = _LIST_HANDLERS.get(rt_id)
    if handler is None:
        logger.warning("[catalog] no list handler for type=%s", rt_id)
        return {"count": 0, "results": []}
    return handler(filter_data or {}, page or {}, bk_tenant_id)


def fetch_instance_info(
    rt_id: str,
    ids: list[str],
    requires: list[str],
    bk_tenant_id: str = DEFAULT_TENANT_ID,
) -> list[dict]:
    """按 ID 批量查询实例信息（展示名 / 父链）。

    Args:
        rt_id: 资源类型 ID（业务命名）。
        ids: 业务 ID 列表。
        requires: 需要返回的字段，支持 "display_name" / "name" / "_bk_iam_path_"。
        bk_tenant_id: 租户 ID，默认 system。

    Returns:
        [{"id": 业务 ID, "display_name"?: str, "name"?: str, "_bk_iam_path_"?: str}]
    """
    handler = _FETCH_HANDLERS.get(rt_id)
    if handler is None:
        logger.warning("[catalog] no fetch handler for type=%s", rt_id)
        return []
    return handler(ids or [], requires or [], bk_tenant_id)


# ================================================================
# space —— 顶级资源
# ================================================================


def _get_space_queryset(bk_tenant_id: str = DEFAULT_TENANT_ID):
    from metadata.models import Space

    return Space.objects.exclude(space_id="0").filter(bk_tenant_id=bk_tenant_id)


def _generate_space_resources(queryset) -> list[dict]:
    """把 Space 对象列表转成目录出参格式（业务 ID）。

    规则（与 bkm_space 约定一致）：
      - bkcc 空间：bk_biz_id = int(space_id)，正数
      - 非 bkcc 空间：bk_biz_id = -pk，负数
    """
    from bkm_space.utils import space_uid_to_bk_biz_id
    from metadata.models import SpaceType

    space_types = {t.type_id: t.type_name for t in SpaceType.objects.all()}
    return [
        {
            "id": str(space_uid_to_bk_biz_id(space.space_uid, space.id)),
            "display_name": f"[{space_types.get(space.space_type_id, space.space_type_id)}] {space.space_name}",
        }
        for space in queryset
    ]


def _list_space(filter_data: dict, page: dict, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    queryset = _get_space_queryset(bk_tenant_id)
    keyword = (filter_data.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(Q(space_type_id=keyword) | Q(space_id=keyword) | Q(space_name__icontains=keyword))
    total = queryset.count()
    pn = max(page.get("page", 1), 1)
    ps = max(min(page.get("page_size", 100), 1000), 1)
    start = (pn - 1) * ps
    results = _generate_space_resources(queryset[start : start + ps])
    return {"count": total, "results": results}


def _fetch_space(ids: list[str], requires: list[str], bk_tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
    if not ids:
        return []
    from bkm_space.define import SpaceTypeEnum

    conditions = []
    for raw_id in ids:
        try:
            bk_biz_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if bk_biz_id >= 0:
            conditions.append(Q(space_type_id=SpaceTypeEnum.BKCC.value) & Q(space_id=bk_biz_id))
        else:
            conditions.append(Q(id=-bk_biz_id))
    if not conditions:
        return []
    queryset = _get_space_queryset(bk_tenant_id).filter(reduce(operator.or_, conditions))
    result = []
    for s in _generate_space_resources(queryset):
        item: dict = {"id": s["id"], "display_name": s["display_name"]}
        if "_bk_iam_path_" in requires:
            item["_bk_iam_path_"] = f"/space,{s['id']}/"
        result.append(item)
    return result


# ================================================================
# apm_application
# ================================================================


def _list_apm(filter_data: dict, page: dict, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    from apm_web.models import Application as ApmApplication

    queryset = ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id)
    parent = filter_data.get("parent", {})
    if parent.get("type") == "space" and parent.get("id"):
        queryset = queryset.filter(bk_biz_id=parent["id"])
    keyword = (filter_data.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(Q(app_alias__icontains=keyword) | Q(app_name__icontains=keyword))
    total = queryset.count()
    pn = max(page.get("page", 1), 1)
    ps = max(min(page.get("page_size", 100), 1000), 1)
    start = (pn - 1) * ps
    results = [
        {"id": str(item.pk), "display_name": item.app_alias, "name": item.app_name}
        for item in queryset[start : start + ps]
    ]
    return {"count": total, "results": results}


def _fetch_apm(ids: list[str], requires: list[str], bk_tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
    if not ids:
        return []
    from apm_web.models import Application as ApmApplication

    id_ints = []
    for raw_id in ids:
        try:
            id_ints.append(int(raw_id))
        except (TypeError, ValueError):
            # 非数字 ID 直接跳过（与 _fetch_space 的防御风格一致）
            continue
    if not id_ints:
        return []
    queryset = ApmApplication.objects.filter(pk__in=id_ints, bk_tenant_id=bk_tenant_id)
    result = []
    for item in queryset:
        r: dict = {"id": str(item.pk), "display_name": item.app_alias, "name": item.app_name}
        if "_bk_iam_path_" in requires:
            r["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        result.append(r)
    return result


# ================================================================
# grafana_dashboard
# ================================================================


def _get_valid_org_ids(bk_tenant_id: str = DEFAULT_TENANT_ID) -> set[int]:
    from bkm_space.define import SpaceTypeEnum
    from bk_dataview.models import Org
    from metadata.models import Space

    spaces = Space.objects.filter(bk_tenant_id=bk_tenant_id)
    bk_biz_ids = {
        str(-space.id) if space.space_type_id != SpaceTypeEnum.BKCC.value else space.space_id for space in spaces
    }
    return set(Org.objects.filter(name__in=bk_biz_ids).values_list("id", flat=True))


def _list_grafana(filter_data: dict, page: dict, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    from bk_dataview.api import get_org_by_name
    from bk_dataview.models import Dashboard

    valid_org_ids = _get_valid_org_ids(bk_tenant_id)

    folders = Dashboard.objects.filter(is_folder=True, org_id__in=valid_org_ids)
    dashboards = Dashboard.objects.filter(is_folder=False, org_id__in=valid_org_ids)

    parent = filter_data.get("parent", {})
    if parent.get("type") == "space" and parent.get("id"):
        org = get_org_by_name(org_name=parent["id"])
        if not org:
            return {"count": 0, "results": []}
        target_org_id = org["id"]
        if target_org_id not in valid_org_ids:
            return {"count": 0, "results": []}
        folders = folders.filter(org_id=target_org_id)
        dashboards = dashboards.filter(org_id=target_org_id)

    # 只查询一次 folders：既用于目录枚举，也用于目录名映射。
    # dashboard 与其目录同属一个 org，因此 parent 过滤后 folder_titles 只需目标 org 的目录，
    # 与旧实现"全量查询 + .get() 兜底"的语义等价，同时完成收窄并省一次全量查询。
    folders_list = list(folders)
    folder_results = [
        {"id": f"{_FOLDER_PREFIX}{f.org_id}|{f.id}", "display_name": f"[目录] {f.title}"} for f in folders_list
    ]
    folder_titles = {f.id: f.title for f in folders_list}
    dashboard_results = []
    for d in dashboards:
        fn = folder_titles.get(d.folder_id, _GENERAL_FOLDER_NAME) if d.folder_id else _GENERAL_FOLDER_NAME
        dashboard_results.append({"id": f"{d.org_id}|{d.uid}", "display_name": f"[仪表盘] {fn}/{d.title}"})

    all_results = folder_results + dashboard_results
    keyword = (filter_data.get("keyword") or "").strip()
    if keyword:
        all_results = [r for r in all_results if keyword.lower() in r["display_name"].lower()]
    total = len(all_results)
    pn = max(page.get("page", 1), 1)
    ps = max(min(page.get("page_size", 100), 1000), 1)
    start = (pn - 1) * ps
    return {"count": total, "results": all_results[start : start + ps]}


def _fetch_grafana(ids: list[str], requires: list[str], bk_tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
    if not ids:
        return []
    from bk_dataview.models import Dashboard, Org

    # 第一遍：内存解析实例 ID（三种格式），收集 dashboard uid / folder id
    # 第二遍：按集合批量查询，避免逐 id 查库（N+1）
    parsed: list[tuple[str, GrafanaRef]] = []
    folder_ids: set[int] = set()
    dashboard_uids: set[str] = set()
    for instance_id in ids:
        ref = parse_grafana_instance_id(instance_id)
        if ref is None:
            continue
        parsed.append((str(instance_id), ref))
        if ref.kind == "folder":
            folder_ids.add(ref.folder_id)
        else:
            dashboard_uids.add(ref.uid)

    valid_org_ids = _get_valid_org_ids(bk_tenant_id)

    folder_map: dict[int, Any] = {}
    if folder_ids:
        folder_map = {
            f.id: f for f in Dashboard.objects.filter(id__in=folder_ids, is_folder=True, org_id__in=valid_org_ids)
        }

    dashboard_map: dict[str, Any] = {}
    folder_title_map: dict[int, str] = {}
    if dashboard_uids:
        dashboards = Dashboard.objects.filter(uid__in=dashboard_uids, is_folder=False, org_id__in=valid_org_ids)
        dashboard_map = {d.uid: d for d in dashboards}
        # 只查命中仪表盘实际引用的目录，等价于旧实现的全量 folder_titles 映射的 .get() 语义
        need_folder_ids = {d.folder_id for d in dashboards if d.folder_id}
        if need_folder_ids:
            folder_title_map = {f.id: f.title for f in Dashboard.objects.filter(id__in=need_folder_ids, is_folder=True)}

    need_path = "_bk_iam_path_" in requires
    org_map: dict[int, str] = {}
    if need_path:
        org_ids = {item.org_id for item in (*folder_map.values(), *dashboard_map.values())}
        if org_ids:
            org_map = {org.id: org.name for org in Org.objects.filter(id__in=org_ids)}

    # 第三遍：按输入顺序回填结果（重复 id 与旧实现一样逐条输出）
    result = []
    for raw_id, ref in parsed:
        if ref.kind == "folder":
            folder = folder_map.get(ref.folder_id)
            if folder:
                r: dict = {"id": raw_id, "display_name": f"[目录] {folder.title}"}
                if need_path:
                    r["_bk_iam_path_"] = f"/space,{org_map[folder.org_id]}/" if folder.org_id in org_map else "/"
                result.append(r)
        else:
            dash = dashboard_map.get(ref.uid)
            if dash:
                fn = (
                    folder_title_map.get(dash.folder_id, _GENERAL_FOLDER_NAME)
                    if dash.folder_id
                    else _GENERAL_FOLDER_NAME
                )
                r: dict = {"id": raw_id, "display_name": f"[仪表盘] {fn}/{dash.title}"}
                if need_path:
                    r["_bk_iam_path_"] = f"/space,{org_map[dash.org_id]}/" if dash.org_id in org_map else "/"
                result.append(r)
    return result


# ================================================================
# rum_application
# ================================================================


def _list_rum(filter_data: dict, page: dict, bk_tenant_id: str = DEFAULT_TENANT_ID) -> dict:
    from rum_web.models.application import Application as RumApplication

    queryset = RumApplication.objects.filter(bk_tenant_id=bk_tenant_id)
    parent = filter_data.get("parent", {})
    if parent.get("type") == "space" and parent.get("id"):
        queryset = queryset.filter(bk_biz_id=parent["id"])
    keyword = (filter_data.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(Q(app_alias__icontains=keyword) | Q(app_name__icontains=keyword))
    total = queryset.count()
    pn = max(page.get("page", 1), 1)
    ps = max(min(page.get("page_size", 100), 1000), 1)
    start = (pn - 1) * ps
    results = [
        {"id": str(item.pk), "display_name": item.app_alias, "name": item.app_name}
        for item in queryset[start : start + ps]
    ]
    return {"count": total, "results": results}


def _fetch_rum(ids: list[str], requires: list[str], bk_tenant_id: str = DEFAULT_TENANT_ID) -> list[dict]:
    if not ids:
        return []
    from rum_web.models.application import Application as RumApplication

    id_ints = []
    for raw_id in ids:
        try:
            id_ints.append(int(raw_id))
        except (TypeError, ValueError):
            # 非数字 ID 直接跳过（与 _fetch_space 的防御风格一致）
            continue
    if not id_ints:
        return []
    queryset = RumApplication.objects.filter(pk__in=id_ints, bk_tenant_id=bk_tenant_id)
    result = []
    for item in queryset:
        r: dict = {"id": str(item.pk), "display_name": item.app_alias, "name": item.app_name}
        if "_bk_iam_path_" in requires:
            r["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        result.append(r)
    return result


# ================================================================
# 分派表
# ================================================================

_LIST_HANDLERS: dict[str, Callable] = {
    "space": _list_space,
    "apm_application": _list_apm,
    "grafana_dashboard": _list_grafana,
    "rum_application": _list_rum,
}

_FETCH_HANDLERS: dict[str, Callable] = {
    "space": _fetch_space,
    "apm_application": _fetch_apm,
    "grafana_dashboard": _fetch_grafana,
    "rum_application": _fetch_rum,
}
