"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

bkm-cli `inspect-issue` 后端：只读访问 IssueDocument / IssueActivityDocument / IssueMergeRelation。

六个 operation 复用 fta_web 内部 handler 与 Issue 标题公共规则，确保字段清洗、indices 选择、anomaly_message
填充与 web 入口一致：

- detail               : IssueDocument.get_issue_or_raise + IssueQueryHandler.clean_document
                         + merge_status 字段（合并关系：main / member / none + active_members）
- list_by_strategy     : IssueDocument.search().filter("term", strategy_id=...)
- list_by_fingerprint  : IssueDocument.search().filter("term", fingerprint=...)
- list_activities      : IssueActivityDocument.search().filter("term", issue_id=...)
- list_conflicts       : 扫描三类合并/拆分状态不一致（运维对账兜底；含 cascade follow resync）
- list_llm_title_candidates: 分页发现可安全补偿 LLM 标题的活跃 Issue（严格只读）
"""

from __future__ import annotations

import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

OPERATION_DETAIL = "detail"
OPERATION_LIST_BY_STRATEGY = "list_by_strategy"
OPERATION_LIST_BY_FINGERPRINT = "list_by_fingerprint"
OPERATION_LIST_ACTIVITIES = "list_activities"
OPERATION_LIST_CONFLICTS = "list_conflicts"
OPERATION_LIST_LLM_TITLE_CANDIDATES = "list_llm_title_candidates"
ALLOWED_OPERATIONS = {
    OPERATION_DETAIL,
    OPERATION_LIST_BY_STRATEGY,
    OPERATION_LIST_BY_FINGERPRINT,
    OPERATION_LIST_ACTIVITIES,
    OPERATION_LIST_CONFLICTS,
    OPERATION_LIST_LLM_TITLE_CANDIDATES,
}

DEFAULT_LIMIT = 50
MAX_LIMIT = 500


def inspect_issue(params: dict[str, Any]) -> dict[str, Any]:
    operation = str(params.get("operation") or OPERATION_DETAIL).strip()
    if operation not in ALLOWED_OPERATIONS:
        raise CustomException(
            message=f"不支持的 inspect-issue operation: {operation}; 允许: {sorted(ALLOWED_OPERATIONS)}"
        )

    if operation == OPERATION_DETAIL:
        result = _inspect_issue_detail(params)
    elif operation == OPERATION_LIST_BY_STRATEGY:
        result = _list_issues_by_strategy(params)
    elif operation == OPERATION_LIST_BY_FINGERPRINT:
        result = _list_issues_by_fingerprint(params)
    elif operation == OPERATION_LIST_ACTIVITIES:
        result = _list_issue_activities(params)
    elif operation == OPERATION_LIST_CONFLICTS:
        result = _list_merge_conflicts(params)
    else:
        result = _list_llm_title_candidates(params)

    return _to_json_safe(result)


def _to_json_safe(obj: Any) -> Any:
    """递归把 Django gettext_lazy / datetime / Decimal 等转成 JSON-safe。

    BkmCliOpCallResource.result 是 serializers.JSONField，to_representation 时
    json.dumps 不认 __proxy__ (gettext_lazy) 等类型，会抛 TypeError →
    "返回参数格式错误：(result) 值必须是有效的 JSON 数据"。

    IssueQueryHandler.enrich_aggregate_dimensions / enrich_impact_scope 返回的
    display_name 字段是 _("xxx") = gettext_lazy，是常见触发点。这里用
    DjangoJSONEncoder 兜底（自带 lazy / datetime / Decimal 处理）+ json.loads
    回到 Python dict，保证 JSONField 校验通过。
    """
    return json.loads(json.dumps(obj, cls=DjangoJSONEncoder, ensure_ascii=False))


# ---------- operations ----------


def _inspect_issue_detail(params: dict[str, Any]) -> dict[str, Any]:
    from bkmonitor.documents.issue import IssueDocument, IssueNotFoundError
    from fta_web.issue.handlers.issue import IssueQueryHandler

    issue_id = _required_str(params, "issue_id")
    bk_biz_id = _optional_int(params, "bk_biz_id")

    try:
        issue = IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)
    except IssueNotFoundError as error:
        detail = f"issue_id={issue_id}"
        if bk_biz_id is not None:
            detail = f"bk_biz_id={bk_biz_id}, {detail}"
        raise CustomException(message=f"Issue 不存在或业务归属不匹配: {detail}") from error

    cleaned = IssueQueryHandler.clean_document(issue)

    # 注入 merge_status 字段（main / member / none + active_members）：
    # 复用 IssueMergeResolver 视图层逻辑，确保与 SearchIssue / IssueDetail 同口径。
    try:
        from bkmonitor.issue_merge import IssueMergeResolver, MergeResolverContext

        merge_biz_id = bk_biz_id if bk_biz_id is not None else int(cleaned.get("bk_biz_id") or 0)
        if merge_biz_id:
            ctx = MergeResolverContext(merge_biz_id)
            ctx.load()
            IssueMergeResolver.hydrate_aggregations([cleaned], ctx)
        # 显式补 role=none，确保 inspect-issue 调用方拿到稳定字段（无关系时）
        cleaned.setdefault("merge_status", {"role": "none", "main_issue_id": None, "active_members": None})
    except Exception:
        # fail-open：merge 注入失败不阻塞 inspect-issue detail 主路径
        cleaned.setdefault("merge_status", {"role": "none", "main_issue_id": None, "active_members": None})

    # 注入 split_info（独立 Issue 拿到拆分溯源信息）：与 fta_web IssueDetailResource 同口径
    _inject_split_info(cleaned, bk_biz_id)

    return {
        "operation": OPERATION_DETAIL,
        "bk_biz_id": cleaned.get("bk_biz_id"),
        "issue_id": cleaned.get("id"),
        "issue": cleaned,
    }


def _inject_split_info(cleaned: dict[str, Any], bk_biz_id: int | None) -> None:
    """查 IssueMergeRelation status='split' 最新一条，拼装 split_info。

    与 ``fta_web.issue.resources.IssueDetailResource._fill_split_info`` 同口径。
    reasons 取关系表（结构化 SoT），失败 fail-open 不阻塞主路径。
    """
    try:
        from bkmonitor.documents.issue import IssueDocument
        from bkmonitor.models.issue import IssueMergeRelation

        issue_id = cleaned.get("id")
        merge_biz_id = bk_biz_id if bk_biz_id is not None else int(cleaned.get("bk_biz_id") or 0)
        if not issue_id or not merge_biz_id:
            return

        relation = (
            IssueMergeRelation.objects.filter(
                member_issue_id=issue_id,
                bk_biz_id=merge_biz_id,
                status=IssueMergeRelation.STATUS_SPLIT,
            )
            .order_by("-update_time")
            .first()
        )
        if not relation:
            return

        main_name = None
        try:
            main_hits = (
                IssueDocument.search(all_indices=True)
                .filter("term", _id=relation.main_issue_id)
                .source(["name"])
                .params(size=1)
                .execute()
                .hits
            )
            if main_hits:
                main_name = getattr(main_hits[0], "name", None)
        except Exception:
            pass  # name 留 None 走兜底文本

        cleaned["split_info"] = {
            "split_from_main_issue_id": relation.main_issue_id,
            "split_from_main_issue_name": main_name or f"{relation.main_issue_id} (已删除)",
            "split_reasons": relation.split_reasons or [],
            "split_kind": relation.split_kind,
            "split_time": int(relation.update_time.timestamp()) if relation.update_time else 0,
            "split_operator": relation.update_user,
        }
    except Exception:
        # fail-open：不阻塞 inspect-issue 主路径
        pass


def _list_issues_by_strategy(params: dict[str, Any]) -> dict[str, Any]:
    strategy_id = _required_str(params, "strategy_id")
    bk_biz_id = _required_int(params, "bk_biz_id")
    return _list_issues(
        params,
        filter_kwargs={"strategy_id": strategy_id},
        bk_biz_id=bk_biz_id,
        operation=OPERATION_LIST_BY_STRATEGY,
        meta={"strategy_id": strategy_id},
    )


def _list_issues_by_fingerprint(params: dict[str, Any]) -> dict[str, Any]:
    fingerprint = _required_str(params, "fingerprint")
    bk_biz_id = _required_int(params, "bk_biz_id")
    return _list_issues(
        params,
        filter_kwargs={"fingerprint": fingerprint},
        bk_biz_id=bk_biz_id,
        operation=OPERATION_LIST_BY_FINGERPRINT,
        meta={"fingerprint": fingerprint},
    )


def _list_issues(
    params: dict[str, Any],
    *,
    filter_kwargs: dict[str, Any],
    bk_biz_id: int,
    operation: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    from bkmonitor.documents.issue import IssueDocument
    from fta_web.issue.handlers.issue import IssueQueryHandler

    limit = _normalize_limit(params.get("limit"))
    status = params.get("status")
    statuses: list[str] = []
    if isinstance(status, str) and status.strip():
        statuses = [status.strip()]
    elif isinstance(status, list):
        statuses = [str(s).strip() for s in status if str(s).strip()]

    start_time = _optional_int(params, "start_time")
    end_time = _optional_int(params, "end_time")

    search = IssueDocument.search(all_indices=True)
    for field_name, value in filter_kwargs.items():
        search = search.filter("term", **{field_name: value})
    # IssueDocument.bk_biz_id 是 Keyword 字段（documents/issue.py:49），
    # 必须显式转 str 才能精确命中——对齐 fta_web/issue/resources.py:816 模式。
    search = search.filter("term", bk_biz_id=str(bk_biz_id))
    if statuses:
        search = search.filter("terms", status=statuses)
    if start_time is not None:
        search = search.filter("range", create_time={"gte": start_time})
    if end_time is not None:
        search = search.filter("range", create_time={"lte": end_time})

    search = search.sort({"create_time": {"order": "desc"}}).params(size=limit, track_total_hits=True)
    response = search.execute()

    issues = [IssueQueryHandler.clean_document(hit) for hit in response.hits]
    total = _extract_total(response)

    return {
        "operation": operation,
        "bk_biz_id": bk_biz_id,
        **meta,
        "count": len(issues),
        "total": total,
        "truncated": total is not None and total > len(issues),
        "issues": issues,
    }


def _list_issue_activities(params: dict[str, Any]) -> dict[str, Any]:
    from bkmonitor.documents.issue import IssueActivityDocument, IssueDocument, IssueNotFoundError

    issue_id = _required_str(params, "issue_id")
    bk_biz_id = _optional_int(params, "bk_biz_id")

    if bk_biz_id is not None:
        try:
            IssueDocument.get_issue_or_raise(issue_id, bk_biz_id=bk_biz_id)
        except IssueNotFoundError as error:
            raise CustomException(message=f"Issue 不存在或业务归属不匹配: issue_id={issue_id}") from error

    limit = _normalize_limit(params.get("limit"))
    search = (
        IssueActivityDocument.search(all_indices=True)
        .filter("term", issue_id=issue_id)
        .sort({"time": {"order": "desc"}})
        .params(size=limit, track_total_hits=True)
    )
    response = search.execute()
    total = _extract_total(response)

    activities = [
        {
            "activity_id": hit.meta.id,
            "issue_id": getattr(hit, "issue_id", None),
            "bk_biz_id": getattr(hit, "bk_biz_id", None),
            "activity_type": getattr(hit, "activity_type", None),
            "operator": getattr(hit, "operator", None) or "",
            "from_value": getattr(hit, "from_value", None) or None,
            "to_value": getattr(hit, "to_value", None) or None,
            "content": getattr(hit, "content", None) or None,
            "time": int(hit.time) if getattr(hit, "time", None) else 0,
        }
        for hit in response.hits
    ]

    return {
        "operation": OPERATION_LIST_ACTIVITIES,
        "issue_id": issue_id,
        "bk_biz_id": bk_biz_id,
        "count": len(activities),
        "total": total,
        "truncated": total is not None and total > len(activities),
        "activities": activities,
    }


def _list_llm_title_candidates(params: dict[str, Any]) -> dict[str, Any]:
    """分页发现可安全补偿 LLM 标题的活跃 Issue；依赖查询失败时不返回部分候选。"""
    from bkmonitor.documents.issue import IssueDocument
    from bkmonitor.utils.issue_title import (
        TITLE_SOURCE_UNKNOWN,
        TITLE_SOURCE_USER,
        build_issue_default_name,
        classify_issue_title_source,
    )
    from constants.issue import IssueStatus

    bk_biz_id = _required_int(params, "bk_biz_id")
    limit = _normalize_limit(params.get("limit"))
    offset = _normalize_offset(params.get("offset"))
    start_time = _optional_int(params, "start_time")
    end_time = _optional_int(params, "end_time")

    try:
        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", bk_biz_id=str(bk_biz_id))
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
        )
        if start_time is not None:
            search = search.filter("range", create_time={"gte": start_time})
        if end_time is not None:
            search = search.filter("range", create_time={"lte": end_time})
        search = search.sort({"create_time": {"order": "desc"}}).params(track_total_hits=True)
        response = search[offset : offset + limit].execute()
    except Exception as error:
        raise CustomException(message="查询活跃 Issue 失败，未返回候选") from error

    issue_rows: list[dict[str, Any]] = []
    excluded_counts = {
        "title_changed": 0,
        "user_renamed": 0,
        "merged_member": 0,
        "no_alert": 0,
    }
    for hit in response.hits:
        issue_id = str(hit.meta.id)
        current_name = str(getattr(hit, "name", "") or "")
        try:
            dimension_values = getattr(hit, "dimension_values", {}) or {}
            if hasattr(dimension_values, "to_dict"):
                dimension_values = dimension_values.to_dict()
            default_name = build_issue_default_name(
                str(getattr(hit, "strategy_name", "") or ""),
                dict(dimension_values),
                bool(getattr(hit, "is_regression", False)),
            )
        except Exception as error:
            raise CustomException(message=f"重建 Issue 默认标题失败，未返回候选: issue_id={issue_id}") from error

        if current_name != default_name:
            excluded_counts["title_changed"] += 1
            continue
        issue_rows.append(
            {
                "hit": hit,
                "issue_id": issue_id,
                "name": current_name,
                "default_name": default_name,
            }
        )

    default_title_ids = [row["issue_id"] for row in issue_rows]
    operator_map = _latest_name_change_operators(default_title_ids)
    title_safe_rows = []
    for row in issue_rows:
        title_source = classify_issue_title_source(row["name"], row["default_name"], operator_map.get(row["issue_id"]))
        if title_source in {TITLE_SOURCE_USER, TITLE_SOURCE_UNKNOWN}:
            excluded_counts["user_renamed"] += 1
            continue
        title_safe_rows.append(row)

    title_safe_ids = [row["issue_id"] for row in title_safe_rows]
    merge_map = _active_merge_main_issue_ids(title_safe_ids, bk_biz_id)
    unmerged_rows = []
    for row in title_safe_rows:
        if row["issue_id"] in merge_map:
            excluded_counts["merged_member"] += 1
            continue
        unmerged_rows.append(row)

    unmerged_ids = [row["issue_id"] for row in unmerged_rows]
    alert_map = _latest_alert_ids(unmerged_ids)
    candidates = []
    for row in unmerged_rows:
        issue_id = row["issue_id"]
        alert_id = alert_map.get(issue_id)
        if not alert_id:
            excluded_counts["no_alert"] += 1
            continue
        hit = row["hit"]
        candidates.append(
            {
                "issue_id": issue_id,
                "name": row["name"],
                "default_name": row["default_name"],
                "status": getattr(hit, "status", None),
                "strategy_id": str(getattr(hit, "strategy_id", "") or ""),
                "strategy_name": str(getattr(hit, "strategy_name", "") or ""),
                "create_time": int(getattr(hit, "create_time", 0) or 0),
                "alert_id": alert_id,
                "safe_to_regenerate": True,
                "candidate_reason": "active_default_title_safe",
            }
        )

    scanned_count = len(response.hits)
    total_active = _extract_total(response)
    page_end = offset + scanned_count
    if total_active is None:
        truncated = scanned_count == limit
    else:
        truncated = page_end < total_active

    return {
        "operation": OPERATION_LIST_LLM_TITLE_CANDIDATES,
        "bk_biz_id": bk_biz_id,
        "scanned_count": scanned_count,
        "candidate_count": len(candidates),
        "total_active": total_active,
        "excluded_counts": excluded_counts,
        "offset": offset,
        "next_offset": page_end if truncated else None,
        "truncated": truncated,
        "candidates": candidates,
    }


def _latest_name_change_operators(issue_ids: list[str]) -> dict[str, str]:
    """批量查询每个 Issue 最近一次 NAME_CHANGE operator；失败时拒绝返回候选。"""
    if not issue_ids:
        return {}

    from bkmonitor.documents.issue import IssueActivityDocument
    from constants.issue import IssueActivityType

    try:
        hits = (
            IssueActivityDocument.search(all_indices=True)
            .filter("terms", issue_id=issue_ids)
            .filter("term", activity_type=IssueActivityType.NAME_CHANGE)
            .sort({"time": {"order": "desc"}})
            .extra(collapse={"field": "issue_id"})
            .params(size=len(issue_ids))
            .execute()
            .hits
        )
    except Exception as error:
        raise CustomException(message="查询 Issue 改名活动失败，未返回候选") from error
    return {
        str(getattr(hit, "issue_id", "")): str(getattr(hit, "operator", "") or "")
        for hit in hits
        if getattr(hit, "issue_id", None)
    }


def _active_merge_main_issue_ids(issue_ids: list[str], bk_biz_id: int) -> dict[str, str]:
    """批量查询活跃合并成员；失败时拒绝返回候选。"""
    if not issue_ids:
        return {}

    from bkmonitor.models.issue import IssueMergeRelation

    try:
        rows = IssueMergeRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            member_issue_id__in=issue_ids,
            status=IssueMergeRelation.STATUS_ACTIVE,
        ).values("member_issue_id", "main_issue_id")
        return {str(row["member_issue_id"]): str(row["main_issue_id"]) for row in rows}
    except Exception as error:
        raise CustomException(message="查询 Issue 活跃合并关系失败，未返回候选") from error


def _latest_alert_ids(issue_ids: list[str]) -> dict[str, str]:
    """批量查询每个 Issue 最新关联 Alert；失败时拒绝返回候选。"""
    if not issue_ids:
        return {}

    from bkmonitor.documents.alert import AlertDocument

    try:
        hits = (
            AlertDocument.search(all_indices=True)
            .filter("terms", issue_id=issue_ids)
            .sort({"begin_time": {"order": "desc"}})
            .extra(collapse={"field": "issue_id"})
            .params(size=len(issue_ids))
            .execute()
            .hits
        )
    except Exception as error:
        raise CustomException(message="查询 Issue 关联 Alert 失败，未返回候选") from error
    return {str(getattr(hit, "issue_id", "")): str(hit.meta.id) for hit in hits if getattr(hit, "issue_id", None)}


_DEFAULT_CONFLICT_LOOKBACK_DAYS = 7
_MAX_CONFLICT_LOOKBACK_DAYS = 90


def _list_merge_conflicts(params: dict[str, Any]) -> dict[str, Any]:
    """扫描合并/拆分状态不一致（运维对账兜底）。

    返回三类（顺序与下方代码计算顺序一致，第 1/2/3 类）：
    - duplicate_active_members：同一 member_issue_id 在多行 status='active' 关系（race window）
    - pending_split_resets    ：SQL status='split' 但对应 IssueDocument 物理状态未匹配 PENDING_REVIEW
      （deprecated：主状态变更不再触发拆分，仅历史遗留 split 关系仍可能触发；将随 reset_pending_split mode 一起移除）
    - pending_follow_resync   ：关系 active 但 member ES status ≠ 主当前 status
      （cascade follow fail-open 兜底，对应 repair_issue_merge_state --mode=follow_status_resync）

    Args:
        bk_biz_id (必填): 业务 ID
        since_days (可选): 回溯窗口，默认 7 天，最大 90 天
        limit (可选): 单类最大返回条数，默认 50，最大 500
    """
    import time as _time

    from bkmonitor.documents.issue import IssueDocument
    from bkmonitor.models.issue import IssueMergeRelation
    from constants.issue import IssueStatus
    from django.db.models import Count

    bk_biz_id = _required_int(params, "bk_biz_id")
    since_days = _optional_int(params, "since_days") or _DEFAULT_CONFLICT_LOOKBACK_DAYS
    if since_days <= 0 or since_days > _MAX_CONFLICT_LOOKBACK_DAYS:
        raise CustomException(message=f"since_days 必须在 [1, {_MAX_CONFLICT_LOOKBACK_DAYS}]，当前: {since_days}")
    limit = _normalize_limit(params.get("limit"))
    since_ts = int(_time.time()) - since_days * 86400

    # 第 1 类：duplicate active member
    duplicate_rows = (
        IssueMergeRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            status=IssueMergeRelation.STATUS_ACTIVE,
            create_time__gte=_dt_from_ts(since_ts),
        )
        .values("member_issue_id")
        .annotate(active_count=Count("id"))
        .filter(active_count__gt=1)
        .order_by("-active_count")[:limit]
    )
    duplicate_active_members = [
        {"member_issue_id": r["member_issue_id"], "active_count": r["active_count"]} for r in duplicate_rows
    ]

    # 第 2 类：SQL split 但 ES 状态未重置（pending reset）
    split_rows = list(
        IssueMergeRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            status=IssueMergeRelation.STATUS_SPLIT,
            update_time__gte=_dt_from_ts(since_ts),
        )
        .values("member_issue_id", "main_issue_id", "split_kind", "update_time")
        .order_by("-update_time")[:limit]
    )
    pending_split_resets: list[dict[str, Any]] = []
    if split_rows:
        member_ids = [r["member_issue_id"] for r in split_rows]
        hits = (
            IssueDocument.search(all_indices=True)
            .filter("terms", _id=member_ids)
            .source(["status", "assignee"])
            .params(size=len(member_ids))
            .execute()
            .hits
        )
        status_map = {
            hit.meta.id: (getattr(hit, "status", None), list(getattr(hit, "assignee", []) or [])) for hit in hits
        }
        for r in split_rows:
            es_status, es_assignee = status_map.get(r["member_issue_id"], (None, []))
            # 物理状态不为 PENDING_REVIEW 或 assignee 不为空 → 视为 pending reset
            if es_status is None:
                continue
            if es_status != IssueStatus.PENDING_REVIEW or es_assignee:
                pending_split_resets.append(
                    {
                        "member_issue_id": r["member_issue_id"],
                        "main_issue_id": r["main_issue_id"],
                        "split_kind": r["split_kind"],
                        "es_status": es_status,
                        "es_assignee": es_assignee,
                    }
                )

    # 第 3 类：关系 active 但 member ES status ≠ 主当前 status
    # 与 repair follow_status_resync mode 配对：cascade follow 失败时此处检测得到，运维 mode 修复
    active_rows = list(
        IssueMergeRelation.objects.filter(
            bk_biz_id=bk_biz_id,
            status=IssueMergeRelation.STATUS_ACTIVE,
            update_time__gte=_dt_from_ts(since_ts),
        ).values("main_issue_id", "member_issue_id")[:limit]
    )
    pending_follow_resync: list[dict[str, Any]] = []
    if active_rows:
        main_to_members: dict[str, list[str]] = {}
        for r in active_rows:
            main_to_members.setdefault(r["main_issue_id"], []).append(r["member_issue_id"])
        all_ids = set(main_to_members.keys())
        for ms in main_to_members.values():
            all_ids.update(ms)
        try:
            es_hits = (
                IssueDocument.search(all_indices=True)
                .filter("terms", _id=list(all_ids))
                .source(["status"])
                .params(size=len(all_ids))
                .execute()
                .hits
            )
            es_status_map = {h.meta.id: getattr(h, "status", None) for h in es_hits}
        except Exception:
            es_status_map = {}
        for main_id, member_ids in main_to_members.items():
            main_es_status = es_status_map.get(main_id)
            if main_es_status is None:
                continue  # 主 ES 缺失，跳过（孤儿关系另作处理）
            for mid in member_ids:
                m_es_status = es_status_map.get(mid)
                if m_es_status is not None and m_es_status != main_es_status:
                    pending_follow_resync.append(
                        {
                            "main_issue_id": main_id,
                            "member_issue_id": mid,
                            "main_es_status": main_es_status,
                            "member_es_status": m_es_status,
                        }
                    )
                    if len(pending_follow_resync) >= limit:
                        break
            if len(pending_follow_resync) >= limit:
                break

    return {
        "operation": OPERATION_LIST_CONFLICTS,
        "bk_biz_id": bk_biz_id,
        "since_days": since_days,
        # 三类顺序与 docstring / 上方计算顺序一致：第 1/2/3 类
        "duplicate_active_members": duplicate_active_members,
        "pending_split_resets": pending_split_resets,
        "pending_follow_resync": pending_follow_resync,
        "total_conflicts": (len(duplicate_active_members) + len(pending_split_resets) + len(pending_follow_resync)),
    }


def _dt_from_ts(ts: int):
    """unix 秒 → naive datetime（与 IssueMergeRelation.create_time/update_time auto_now 字段对齐）。"""
    import datetime as _dt

    return _dt.datetime.fromtimestamp(ts)


# ---------- helpers ----------


def _normalize_limit(value: Any) -> int:
    if value in (None, ""):
        return DEFAULT_LIMIT
    try:
        limit = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"limit 必须是整数: {value}") from error
    if limit <= 0:
        raise CustomException(message=f"limit 必须大于 0: {limit}")
    if limit > MAX_LIMIT:
        raise CustomException(message=f"limit 超过硬上限 {MAX_LIMIT}: {limit}")
    return limit


def _normalize_offset(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        offset = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"offset 必须是整数: {value}") from error
    if offset < 0:
        raise CustomException(message=f"offset 不能小于 0: {offset}")
    return offset


def _required_str(params: dict[str, Any], field_name: str) -> str:
    value = params.get(field_name)
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        raise CustomException(message=f"inspect-issue 必须提供 {field_name}")
    return str(value).strip()


def _required_int(params: dict[str, Any], field_name: str) -> int:
    value = params.get(field_name)
    if value in (None, ""):
        raise CustomException(message=f"inspect-issue 必须提供 {field_name}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


def _optional_int(params: dict[str, Any], field_name: str) -> int | None:
    value = params.get(field_name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


def _extract_total(response: Any) -> int | None:
    """从 ES 响应里取 hits.total.value（track_total_hits=True 时存在）。"""
    try:
        total = response.hits.total
    except AttributeError:
        return None
    if isinstance(total, int):
        return total
    return getattr(total, "value", None)


# ---------- registration ----------

KernelRPCRegistry.register_function(
    func_name="bkm_cli.inspect_issue",
    summary="只读访问 IssueDocument / IssueActivityDocument / IssueMergeRelation",
    description=(
        "bkm-cli inspect-issue 后端：六个 operation 复用 fta_web IssueQueryHandler.clean_document、"
        "IssueDocument.get_issue_or_raise；detail 注入 merge_status，list_conflicts 扫描合并/拆分状态"
        "不一致，list_llm_title_candidates 失败关闭地发现安全补偿候选并返回 candidate_reason；"
        "仅只读，不暴露任何写动作。"
    ),
    handler=inspect_issue,
    params_schema={
        "operation": (
            "detail | list_by_strategy | list_by_fingerprint | list_activities | list_conflicts | "
            "list_llm_title_candidates"
        ),
        "issue_id": "detail / list_activities 必填",
        "bk_biz_id": (
            "list_by_strategy / list_by_fingerprint / list_conflicts / list_llm_title_candidates 必填；"
            "detail / list_activities 可选（提供时校验业务归属）"
        ),
        "strategy_id": "list_by_strategy 必填",
        "fingerprint": "list_by_fingerprint 必填",
        "status": "可选状态过滤；string 或 list（如 ABNORMAL / RESOLVED）",
        "start_time": "可选；create_time 下限（unix 秒）",
        "end_time": "可选；create_time 上限（unix 秒）",
        "since_days": f"list_conflicts 可选；默认 {_DEFAULT_CONFLICT_LOOKBACK_DAYS}，最大 {_MAX_CONFLICT_LOOKBACK_DAYS}",
        "limit": f"默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
        "offset": "list_llm_title_candidates 可选；默认 0，不能小于 0",
    },
    example_params={
        "operation": "list_by_strategy",
        "bk_biz_id": 2,
        "strategy_id": "10313",
        "status": ["ABNORMAL"],
        "limit": 50,
    },
)

BkmCliOpRegistry.register(
    op_id="inspect-issue",
    func_name="bkm_cli.inspect_issue",
    summary="只读访问 Issue 模块（IssueDocument / IssueActivityDocument / IssueMergeRelation）",
    description=(
        "通过 monitor-api 服务桥读取 Issue 模块的 ES + SQL 数据：单 Issue 详情（含 merge_status）、"
        "按 strategy_id / fingerprint 列出活跃或历史 Issue、Issue activity 时序、合并/拆分状态不一致对账、"
        "LLM 标题安全补偿候选发现。"
        "配合 read-cache-key 的 4 个 ISSUE_* keys 完整覆盖 issue fingerprint + merge 改造后的取证面。"
    ),
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["issue", "es", "readonly", "inspect"],
    params_schema={
        "operation": (
            "string (detail | list_by_strategy | list_by_fingerprint | list_activities | list_conflicts | "
            "list_llm_title_candidates)"
        ),
        "issue_id": "string",
        "bk_biz_id": "integer",
        "strategy_id": "string",
        "fingerprint": "string",
        "status": "string | string[]",
        "start_time": "integer (unix seconds)",
        "end_time": "integer (unix seconds)",
        "since_days": "integer (list_conflicts only, default 7, max 90)",
        "limit": "integer",
        "offset": "integer (list_llm_title_candidates only, default 0)",
    },
    example_params={
        "operation": "list_by_strategy",
        "bk_biz_id": 2,
        "strategy_id": "10313",
        "status": ["ABNORMAL"],
        "limit": 50,
    },
)
