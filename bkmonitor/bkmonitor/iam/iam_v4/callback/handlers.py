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
# IAM v4 资源回调 handler 实现
#
# 逻辑复用自 v3 的 monitor_web/iam/views.py 中 SpaceProvider /
# ApmApplicationProvider / GrafanaDashboardProvider。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging
import operator
from functools import reduce

from django.db.models import Q

from apm_web.models import Application as ApmApplication
from bk_dataview.api import get_org_by_name
from bk_dataview.models import Dashboard, Org
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import space_uid_to_bk_biz_id
from constants.common import DEFAULT_TENANT_ID
from metadata.models import Space, SpaceType
from rum_web.models.application import Application as RumApplication

from .services import register

logger = logging.getLogger(__name__)


# ================================================================
# space — 顶级资源，复用 v3 SpaceProvider
# ================================================================


def _get_space_queryset(bk_tenant_id: str = DEFAULT_TENANT_ID):
    return Space.objects.exclude(space_id="0").filter(bk_tenant_id=bk_tenant_id)


def _generate_space_resources(queryset):
    space_types = {t.type_id: t.type_name for t in SpaceType.objects.all()}
    return [
        {
            # 注意：由于 space_uid 长度会超过 IAM 平台的 32 位限制，资源 ID 使用 bk_biz_id。
            # 规则：
            #   - bkcc 空间：bk_biz_id = int(space_id)，为正数，ID 以数字开头，符合 IAM 规范。
            #   - 非 bkcc 空间：bk_biz_id = -pk，为负数。** 负数 ID 以 "-" 开头，当前 IAM v4
            #     要求 ID 以字母/数字开头，这个负号会导致回调校验失败。暂时对负数 bk_biz_id
            #     不做特殊处理，保持与 v3 一致的编码；等 IAM v4 支持后再统一迁移。
            "id": str(space_uid_to_bk_biz_id(space.space_uid, space.id)),
            "display_name": f"[{space_types.get(space.space_type_id, space.space_type_id)}] {space.space_name}",
        }
        for space in queryset
    ]


def _list_space(filter_data: dict, page: dict) -> dict:
    queryset = _get_space_queryset()
    keyword = (filter_data.get("keyword") or "").strip()
    if keyword:
        queryset = queryset.filter(Q(space_type_id=keyword) | Q(space_id=keyword) | Q(space_name__icontains=keyword))
    total = queryset.count()
    pn = max(page.get("page", 1), 1)
    ps = max(min(page.get("page_size", 100), 1000), 1)
    start = (pn - 1) * ps
    results = _generate_space_resources(queryset[start : start + ps])
    return {"count": total, "results": results}


def _fetch_space(ids: list[str], requires: list[str]) -> list[dict]:
    if not ids:
        return []
    conditions = []
    for raw_id in ids:
        bk_biz_id = int(raw_id)
        if bk_biz_id >= 0:
            conditions.append(Q(space_type_id=SpaceTypeEnum.BKCC.value) & Q(space_id=bk_biz_id))
        else:
            conditions.append(Q(id=-bk_biz_id))
    if not conditions:
        return []
    queryset = _get_space_queryset().filter(reduce(operator.or_, conditions))
    result = []
    for s in _generate_space_resources(queryset):
        item: dict = {"id": s["id"], "display_name": s["display_name"]}
        if "_bk_iam_path_" in requires:
            item["_bk_iam_path_"] = f"/space,{s['id']}/"
        result.append(item)
    return result


# ================================================================
# apm_application — 复用 v3 ApmApplicationProvider
# ================================================================


def _list_apm(filter_data: dict, page: dict) -> dict:
    queryset = ApmApplication.objects.filter(bk_tenant_id=DEFAULT_TENANT_ID)
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
    results = [{"id": str(item.pk), "display_name": item.app_alias} for item in queryset[start : start + ps]]
    return {"count": total, "results": results}


def _fetch_apm(ids: list[str], requires: list[str]) -> list[dict]:
    if not ids:
        return []
    id_ints = [int(i) for i in ids]
    queryset = ApmApplication.objects.filter(pk__in=id_ints, bk_tenant_id=DEFAULT_TENANT_ID)
    result = []
    for item in queryset:
        r: dict = {"id": str(item.pk), "display_name": item.app_alias}
        if "_bk_iam_path_" in requires:
            r["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        result.append(r)
    return result


# ================================================================
# grafana_dashboard — 复用 v3 GrafanaDashboardProvider
# ================================================================

_FOLDER_PREFIX = "folder:"
_GENERAL_FOLDER_NAME = "General"


def _get_valid_org_ids() -> set[int]:
    spaces = Space.objects.filter(bk_tenant_id=DEFAULT_TENANT_ID)
    bk_biz_ids = {
        str(-space.id) if space.space_type_id != SpaceTypeEnum.BKCC.value else space.space_id for space in spaces
    }
    return set(Org.objects.filter(name__in=bk_biz_ids).values_list("id", flat=True))


def _list_grafana(filter_data: dict, page: dict) -> dict:
    valid_org_ids = _get_valid_org_ids()

    folders = Dashboard.objects.filter(is_folder=True, org_id__in=valid_org_ids)
    dashboards = Dashboard.objects.filter(is_folder=False, org_id__in=valid_org_ids)

    # 按 parent (space) 过滤
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

    # 构建结果
    folder_results = [
        {"id": f"{_FOLDER_PREFIX}{f.org_id}|{f.id}", "display_name": f"[目录] {f.title}"} for f in folders
    ]
    # folder_id -> title 映射
    folder_titles = {f.id: f.title for f in Dashboard.objects.filter(is_folder=True, org_id__in=valid_org_ids)}
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


def _fetch_grafana(ids: list[str], requires: list[str]) -> list[dict]:
    if not ids:
        return []
    valid_org_ids = _get_valid_org_ids()
    result = []
    for instance_id in ids:
        instance_id = str(instance_id)
        if instance_id.startswith(_FOLDER_PREFIX):
            # Folder: "folder:{org_id}|{folder_id}"
            part = instance_id[len(_FOLDER_PREFIX) :]
            if "|" in part:
                try:
                    fid = int(part.split("|", 1)[1])
                    folder = Dashboard.objects.filter(id=fid, is_folder=True, org_id__in=valid_org_ids).first()
                    if folder:
                        r: dict = {"id": instance_id, "display_name": f"[目录] {folder.title}"}
                        if "_bk_iam_path_" in requires:
                            org = Org.objects.filter(id=folder.org_id).first()
                            r["_bk_iam_path_"] = f"/space,{org.name}/" if org else "/"
                        result.append(r)
                except (ValueError, IndexError):
                    continue
        else:
            # Dashboard: "{org_id}|{uid}"
            uid = instance_id.split("|", 1)[1] if "|" in instance_id else instance_id
            dash = Dashboard.objects.filter(uid=uid, is_folder=False, org_id__in=valid_org_ids).first()
            if dash:
                folder_titles = {
                    f.id: f.title for f in Dashboard.objects.filter(is_folder=True, org_id__in=valid_org_ids)
                }
                fn = folder_titles.get(dash.folder_id, _GENERAL_FOLDER_NAME) if dash.folder_id else _GENERAL_FOLDER_NAME
                r: dict = {"id": instance_id, "display_name": f"[仪表盘] {fn}/{dash.title}"}
                if "_bk_iam_path_" in requires:
                    org = Org.objects.filter(id=dash.org_id).first()
                    r["_bk_iam_path_"] = f"/space,{org.name}/" if org else "/"
                result.append(r)
    return result


# ================================================================
# rum_application — v3 无 Provider，仿照 APM 实现
# ================================================================


def _list_rum(filter_data: dict, page: dict) -> dict:
    queryset = RumApplication.objects.filter(bk_tenant_id=DEFAULT_TENANT_ID)
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
    results = [{"id": str(item.pk), "display_name": item.app_alias} for item in queryset[start : start + ps]]
    return {"count": total, "results": results}


def _fetch_rum(ids: list[str], requires: list[str]) -> list[dict]:
    if not ids:
        return []
    id_ints = [int(i) for i in ids]
    queryset = RumApplication.objects.filter(pk__in=id_ints, bk_tenant_id=DEFAULT_TENANT_ID)
    result = []
    for item in queryset:
        r: dict = {"id": str(item.pk), "display_name": item.app_alias}
        if "_bk_iam_path_" in requires:
            r["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        result.append(r)
    return result


# ================================================================
# 注册
# ================================================================


def register_all():
    register("space", _list_space, _fetch_space)
    register("apm_application", _list_apm, _fetch_apm)
    register("grafana_dashboard", _list_grafana, _fetch_grafana)
    register("rum_application", _list_rum, _fetch_rum)
