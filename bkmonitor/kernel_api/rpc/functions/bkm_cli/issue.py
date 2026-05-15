"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT

bkm-cli `inspect-issue` 后端：只读访问 IssueDocument / IssueActivityDocument。

四个 operation 复用 fta_web 内部 handler，确保字段清洗、indices 选择、anomaly_message
填充与 web 入口一致：

- detail               : IssueDocument.get_issue_or_raise + IssueQueryHandler.clean_document
- list_by_strategy     : IssueDocument.search().filter("term", strategy_id=...)
- list_by_fingerprint  : IssueDocument.search().filter("term", fingerprint=...)
- list_activities      : IssueActivityDocument.search().filter("term", issue_id=...)
"""

from __future__ import annotations

from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

OPERATION_DETAIL = "detail"
OPERATION_LIST_BY_STRATEGY = "list_by_strategy"
OPERATION_LIST_BY_FINGERPRINT = "list_by_fingerprint"
OPERATION_LIST_ACTIVITIES = "list_activities"
ALLOWED_OPERATIONS = {
    OPERATION_DETAIL,
    OPERATION_LIST_BY_STRATEGY,
    OPERATION_LIST_BY_FINGERPRINT,
    OPERATION_LIST_ACTIVITIES,
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
        return _inspect_issue_detail(params)
    if operation == OPERATION_LIST_BY_STRATEGY:
        return _list_issues_by_strategy(params)
    if operation == OPERATION_LIST_BY_FINGERPRINT:
        return _list_issues_by_fingerprint(params)
    return _list_issue_activities(params)


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
    return {
        "operation": OPERATION_DETAIL,
        "bk_biz_id": cleaned.get("bk_biz_id"),
        "issue_id": cleaned.get("id"),
        "issue": cleaned,
    }


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
    summary="只读访问 IssueDocument / IssueActivityDocument",
    description=(
        "bkm-cli inspect-issue 后端：四个 operation 复用 fta_web IssueQueryHandler.clean_document 与 "
        "IssueDocument.get_issue_or_raise；仅只读，不暴露任何写动作。"
    ),
    handler=inspect_issue,
    params_schema={
        "operation": "detail | list_by_strategy | list_by_fingerprint | list_activities",
        "issue_id": "detail / list_activities 必填",
        "bk_biz_id": "list_by_strategy / list_by_fingerprint 必填；detail / list_activities 可选（提供时校验业务归属）",
        "strategy_id": "list_by_strategy 必填",
        "fingerprint": "list_by_fingerprint 必填",
        "status": "可选状态过滤；string 或 list（如 ABNORMAL / RESOLVED）",
        "start_time": "可选；create_time 下限（unix 秒）",
        "end_time": "可选；create_time 上限（unix 秒）",
        "limit": f"默认 {DEFAULT_LIMIT}，最大 {MAX_LIMIT}",
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
    summary="只读访问 Issue 模块（IssueDocument / IssueActivityDocument）",
    description=(
        "通过 monitor-api 服务桥读取 Issue 模块的 ES 数据：单 Issue 详情、按 strategy_id / fingerprint "
        "列出活跃或历史 Issue、Issue activity 时序。配合 read-cache-key 的 4 个 ISSUE_* keys 完整覆盖 "
        "issue fingerprint 改造后的取证面。"
    ),
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["issue", "es", "readonly", "inspect"],
    params_schema={
        "operation": "string (detail | list_by_strategy | list_by_fingerprint | list_activities)",
        "issue_id": "string",
        "bk_biz_id": "integer",
        "strategy_id": "string",
        "fingerprint": "string",
        "status": "string | string[]",
        "start_time": "integer (unix seconds)",
        "end_time": "integer (unix seconds)",
        "limit": "integer",
    },
    example_params={
        "operation": "list_by_strategy",
        "bk_biz_id": 2,
        "strategy_id": "10313",
        "status": ["ABNORMAL"],
        "limit": 50,
    },
)
