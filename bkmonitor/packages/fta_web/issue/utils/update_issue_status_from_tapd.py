"""
TAPD 单据状态变更时，更新关联 Issue 的状态（流转为已解决）。
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from bkmonitor.documents.issue import IssueDocument
from bkmonitor.models.issue import IssueTapdRelation
from constants.issue import IssueStatus
from core.drf_resource import api
from fta_web.constants import TAPD_COMPLETED_STATUS_EN_KEYWORDS, TAPD_COMPLETED_STATUS_CN_KEYWORDS

logger = logging.getLogger("root")


def _query_and_check_tapd_status(workspace_id: int, tapd_type: str, tapd_id: str) -> bool:
    """查询tapd状态，返回是否为已完成"""
    from fta_web.issue.resources import SearchTAPDItemsResource

    items = SearchTAPDItemsResource._query_tapd_items(
        tapd_type=tapd_type,
        workspace_id=workspace_id,
        id=tapd_id,
        limit=1,
        page=1,
        order="created desc",
        fields="id,status",
    )
    if not items:
        return False
    item = items[0]
    status_value = item.get("status", "")
    status_display_name = item.get("status_display_name", "")
    if not status_value:
        return False
    if status_value.lower() in TAPD_COMPLETED_STATUS_EN_KEYWORDS:
        return True
    if status_display_name and any(keyword in status_display_name for keyword in TAPD_COMPLETED_STATUS_CN_KEYWORDS):
        return True

    return False


def _filter_resolved(relations: list[dict]) -> list[dict]:
    """排除 Issue 已处于"已解决"状态的关联记录。"""
    ids = {r["issue_id"] for r in relations}
    if not ids:
        return relations

    try:
        search = (
            IssueDocument.search(all_indices=True)
            .filter("terms", _id=list(ids))
            .filter("term", status=IssueStatus.RESOLVED)
            .source(["id"])
        )
        resolved_ids = {hit.meta.id for hit in search}
    except Exception:
        logger.warning("ES query failed, proceeding without pre-filter", exc_info=True)
        return relations

    return [r for r in relations if r["issue_id"] not in resolved_ids]


def _resolve_one(issue_id: str, bk_biz_id: int) -> dict:
    try:
        result = api.issue.resolve(bk_biz_id=bk_biz_id, issue_id=issue_id, operator="system")
        logger.info("Issue auto-resolved: issue=%s biz=%s", issue_id, bk_biz_id)
        return result
    except Exception:
        logger.warning("Issue resolve failed: issue=%s biz=%s", issue_id, bk_biz_id, exc_info=True)
        return {}


def _resolve_all(issues: set[tuple[int, str]]) -> tuple[int, int]:
    """并发流转 Issue。返回 (resolved, failed)。"""
    if not issues:
        return 0, 0

    done = failed = 0
    with ThreadPoolExecutor(max_workers=min(10, len(issues))) as executor:
        futures = {executor.submit(_resolve_one, iid, bid): (bid, iid) for bid, iid in issues}
        for f in as_completed(futures):
            bid, iid = futures[f]
            try:
                if f.result():
                    done += 1
                else:
                    failed += 1
            except Exception:
                logger.warning("resolve panic: biz=%s issue=%s", bid, iid, exc_info=True)
                failed += 1
    return done, failed


def update_issue_status_from_tapd(workspace_id: int, tapd_id: str, tapd_type: str) -> dict:
    """TAPD 单据状态变更为已完成时，将关联 Issue 流转为已解决"""
    relations = list(
        IssueTapdRelation.objects.filter(
            sync_status=True,
            workspace_id=workspace_id,
            tapd_id=tapd_id,
            tapd_type=tapd_type,
        ).values("bk_biz_id", "issue_id")
    )
    if not relations:
        logger.info("no relations, ws=%s tapd=%s", workspace_id, tapd_id)
        return {"checked": 0, "resolved": 0, "failed": 0, "skipped": 0}

    try:
        completed = _query_and_check_tapd_status(workspace_id, tapd_type, tapd_id)
    except Exception:
        logger.warning("tapd query failed, ws=%s tapd=%s", workspace_id, tapd_id, exc_info=True)
        return {"checked": 0, "resolved": 0, "failed": len(relations), "skipped": 0}

    if not completed:
        logger.info("tapd not completed, tapd=%s", tapd_id)
        return {"checked": len(relations), "resolved": 0, "failed": 0, "skipped": len(relations)}

    active = _filter_resolved(relations)
    skipped = len(relations) - len(active)
    if not active:
        return {"checked": len(relations), "resolved": 0, "failed": 0, "skipped": len(relations)}

    to_resolve = {(r["bk_biz_id"], r["issue_id"]) for r in active}
    done, failed = _resolve_all(to_resolve)

    stats = {"checked": len(relations), "resolved": done, "failed": failed, "skipped": skipped}
    logger.info("done: ws=%s tapd=%s stats=%s", workspace_id, tapd_id, stats)
    return stats
