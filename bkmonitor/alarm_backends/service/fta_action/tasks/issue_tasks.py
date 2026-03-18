"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

from alarm_backends.service.scheduler.app import app
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import IssueDocument
from constants.issue import IssueStatus

logger = logging.getLogger("fta_action.issue")

ORPHAN_ISSUE_THRESHOLD_SECONDS = 300
ISSUE_SCAN_PAGE_SIZE = 500
ALERT_SCAN_PAGE_SIZE = 500


PROGRESS_LOG_INTERVAL = 100


@app.task(ignore_result=True, queue="celery_action_cron")
def sync_issue_alert_stats():
    """
    定期对活跃 Issue 执行：
      1) 漏关联补偿（回填 AlertDocument.issue_id）
      2) 统计 alert_count / last_alert_time
      3) 重算 impact_scope
      4) 检测 orphan issue 并触发监控告警
    """
    start_ts = time.time()
    processed = 0
    failed = 0
    total = 0

    for hit, total in _iter_issue_hits_with_total():
        issue = IssueDocument(**hit.to_dict())
        processed += 1

        if processed == 1:
            logger.info("sync_issue_alert_stats: start, active_issues=%d", total)

        logger.debug(
            "sync_issue_alert_stats: processing [%d/%d] issue_id=%s, strategy_id=%s",
            processed,
            total,
            issue.id,
            issue.strategy_id,
        )
        if processed % PROGRESS_LOG_INTERVAL == 0:
            logger.info(
                "sync_issue_alert_stats: progress [%d/%d], failed=%d, elapsed=%.1fs",
                processed,
                total,
                failed,
                time.time() - start_ts,
            )

        try:
            _process_single_issue(issue)
        except Exception:
            failed += 1
            logger.exception(
                "sync_issue_alert_stats: failed for issue_id=%s, strategy_id=%s",
                issue.id,
                issue.strategy_id,
            )

    elapsed = time.time() - start_ts
    logger.info(
        "sync_issue_alert_stats: done, processed=%d/%d, failed=%d, elapsed=%.1fs",
        processed,
        total,
        failed,
        elapsed,
    )


def _process_single_issue(issue: IssueDocument):
    _backfill_unlinked_alerts(issue)

    alert_search = AlertDocument.search(all_indices=True).filter("term", issue_id=issue.id).params(size=0)
    alert_search.aggs.metric("alert_count", "value_count", field="id")
    alert_search.aggs.metric("max_begin_time", "max", field="begin_time")

    result = alert_search.execute()
    alert_count = int(result.aggregations.alert_count.value or 0)
    last_alert_time = result.aggregations.max_begin_time.value or issue.last_alert_time

    impact_scope = _build_impact_scope(issue.id)

    now = int(time.time())
    if alert_count == 0:
        issue_create_time = issue.create_time if issue.create_time else 0
        try:
            issue_create_time = int(issue_create_time)
        except (TypeError, ValueError):
            issue_create_time = 0
        age = now - issue_create_time
        if age > ORPHAN_ISSUE_THRESHOLD_SECONDS:
            logger.error(
                "sync_issue_alert_stats: orphan issue detected (no alerts associated), "
                "issue_id=%s, strategy_id=%s, age_seconds=%.0f",
                issue.id,
                issue.strategy_id,
                age,
            )

    update_doc = IssueDocument(
        id=issue.id,
        alert_count=alert_count,
        last_alert_time=last_alert_time,
        impact_scope=impact_scope,
        update_time=now,
    )
    try:
        IssueDocument.bulk_create([update_doc], action=BulkActionType.UPDATE)
    except Exception:
        logger.exception("sync_issue_alert_stats: UPDATE failed, issue_id=%s", issue.id)


def _backfill_unlinked_alerts(issue: IssueDocument):
    """回填创建窗口期及其后的同策略未关联 Alert 的 issue_id（1:1 模型）"""
    issue_create_time = issue.create_time
    if not issue_create_time:
        return

    try:
        issue_create_time = int(issue_create_time)
    except (TypeError, ValueError):
        return

    base_search = (
        AlertDocument.search(all_indices=True)
        .filter("term", strategy_id=str(issue.strategy_id))
        .filter("range", begin_time={"gte": issue_create_time})
        .exclude("exists", field="issue_id")
    )

    total = 0
    for hits in _iter_alert_hit_batches(base_search):
        update_docs = [AlertDocument(id=hit.id, issue_id=issue.id) for hit in hits]
        try:
            AlertDocument.bulk_create(update_docs, action=BulkActionType.UPSERT)
            total += len(update_docs)
        except Exception:
            logger.exception("sync_issue_alert_stats: backfill failed, issue_id=%s", issue.id)
            return

    if total:
        logger.info("sync_issue_alert_stats: backfilled %d unlinked alerts for issue_id=%s", total, issue.id)


def _build_impact_scope(issue_id: str) -> dict:
    """按关联告警汇总影响范围快照"""
    base_search = AlertDocument.search(all_indices=True).filter("term", issue_id=issue_id)
    hosts = set()
    services = set()
    for hits in _iter_alert_hit_batches(base_search, sort_fields=["id"]):
        for hit in hits:
            dimensions = hit.to_dict().get("dimensions") or []
            for dim in dimensions:
                if not isinstance(dim, dict):
                    continue
                key = dim.get("key", "")
                value = dim.get("value", "")
                if key in ("bk_target_ip", "ip", "bk_host_id") and value:
                    hosts.add(str(value))
                elif key in ("bk_target_service_instance_id", "service_instance_id") and value:
                    services.add(str(value))

    if not hosts and not services:
        return {}

    return {
        "host_count": len(hosts),
        "service_count": len(services),
        "hosts": list(hosts)[:50],
        "services": list(services)[:50],
    }


def _iter_issue_hits_with_total():
    """逐页迭代活跃 Issue，同时从首批响应中提取 total（无额外 ES count 请求）。
    每次 yield (hit, total)，total 在首批确定后保持不变。
    """
    search = (
        IssueDocument.search(all_indices=True)
        .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
        .sort("create_time", "id")
        .params(track_total_hits=True)
    )
    search_after = None
    total = 0
    while True:
        current = search.params(size=ISSUE_SCAN_PAGE_SIZE)
        if search_after:
            current = current.extra(search_after=search_after)
        response = current.execute()
        hits = response.hits
        if not hits:
            break
        if total == 0:
            total = getattr(getattr(hits, "total", None), "value", 0) or len(hits)
        for hit in hits:
            yield hit, total
        search_after = getattr(hits[-1].meta, "sort", None)
        if not search_after:
            break


def _iter_alert_hit_batches(base_search, sort_fields=None):
    sort_fields = sort_fields or ["begin_time", "id"]
    search = base_search.sort(*sort_fields)
    search_after = None
    while True:
        current = search.params(size=ALERT_SCAN_PAGE_SIZE)
        if search_after:
            current = current.extra(search_after=search_after)
        hits = current.execute().hits
        if not hits:
            break
        yield hits
        search_after = getattr(hits[-1].meta, "sort", None)
        if not search_after:
            break
