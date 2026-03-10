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

from config.celery.celery import app

logger = logging.getLogger("action")

# 孤儿 Issue 阈值：Issue 创建后超过此秒数仍无任何 Alert 关联，视为异常
ORPHAN_ISSUE_THRESHOLD_SECONDS = 300  # 5 分钟


def _backfill_unlinked_alerts(issue):
    """漏关联补偿：将同 strategy_id、未关联 Issue、时间 >= issue.create_time 的告警回填

    v1.2 架构（1:1）下每个策略最多一个活跃 Issue，可直接回填到该活跃 Issue。
    """
    from bkmonitor.documents.alert import AlertDocument
    from bkmonitor.documents.base import BulkActionType

    try:
        create_ts = issue.create_time
        if hasattr(create_ts, "timestamp"):
            create_ts = int(create_ts.timestamp())
        else:
            create_ts = int(create_ts) if create_ts else 0

        unlinked = (
            AlertDocument.search(all_indices=True)
            .filter("term", strategy_id=issue.strategy_id)
            .filter("range", begin_time={"gte": create_ts})
            .exclude("exists", field="issue_id")
            .params(size=500)
            .execute()
            .hits
        )
        if not unlinked:
            return

        alerts_to_update = []
        for hit in unlinked:
            alert = AlertDocument(**hit.to_dict())
            alert.issue_id = issue.id
            alerts_to_update.append(alert)

        AlertDocument.bulk_create(alerts_to_update, action=BulkActionType.UPSERT)
        logger.info(
            "sync_issue_alert_stats: backfilled %d alerts to issue_id=%s, strategy_id=%s",
            len(alerts_to_update),
            issue.id,
            issue.strategy_id,
        )
    except Exception as e:
        logger.warning(
            "sync_issue_alert_stats: backfill failed, issue_id=%s, err=%s",
            issue.id,
            e,
        )


def _build_impact_scope_from_alerts(issue_id: str) -> dict:
    """重算 impact_scope：从关联告警的维度中聚合影响范围"""
    from bkmonitor.documents.alert import AlertDocument

    try:
        hits = (
            AlertDocument.search(all_indices=True)
            .filter("term", issue_id=issue_id)
            .params(size=500)
            .execute()
            .hits
        )
        scope = {}
        for hit in hits:
            alert = hit.to_dict()
            for dim in alert.get("dimensions") or []:
                key = dim.get("key")
                val = dim.get("value")
                if key and val is not None:
                    scope.setdefault(key, set()).add(str(val))
        # 将 set 转为 list 以便 JSON 序列化
        return {k: list(v) for k, v in scope.items()}
    except Exception as e:
        logger.warning("_build_impact_scope_from_alerts failed, issue_id=%s, err=%s", issue_id, e)
        return {}


@app.task(ignore_result=True, queue="celery_action_cron")
def sync_issue_alert_stats():
    """定期对活跃 Issue 执行：

    1. 漏关联补偿（回填 AlertDocument.issue_id）
    2. 统计 alert_count / last_alert_time
    3. 重算 impact_scope
    4. 检测 orphan issue 并记录 error log

    频率：每 5 分钟执行一次（由 celery beat 配置）。
    """
    from elasticsearch_dsl import A

    from bkmonitor.documents.base import BulkActionType
    from bkmonitor.documents.issue import IssueDocument
    from constants.issue import IssueStatus

    logger.info("sync_issue_alert_stats: start")
    try:
        active_issues = list(
            IssueDocument.search(all_indices=True)
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .params(size=10000)
            .execute()
            .hits
        )
    except Exception as e:
        logger.exception("sync_issue_alert_stats: query active issues failed: %s", e)
        return

    logger.info("sync_issue_alert_stats: found %d active issues", len(active_issues))

    for hit in active_issues:
        issue = IssueDocument(**hit.to_dict())
        try:
            # Step 0: 漏关联补偿
            _backfill_unlinked_alerts(issue)

            # Step 1: 统计
            from bkmonitor.documents.alert import AlertDocument

            search = AlertDocument.search(all_indices=True).filter("term", issue_id=issue.id)
            search.aggs.metric("count", A("value_count", field="id"))
            search.aggs.metric("max_time", A("max", field="begin_time"))
            result = search.params(size=0).execute()

            alert_count = int(result.aggregations.count.value or 0)
            last_alert_time = result.aggregations.max_time.value

            # Step 2: 重算 impact_scope
            impact_scope = _build_impact_scope_from_alerts(issue.id)

            # Step 3: 检测 orphan issue
            if alert_count == 0:
                create_ts = issue.create_time
                if hasattr(create_ts, "timestamp"):
                    create_ts = int(create_ts.timestamp())
                else:
                    create_ts = int(create_ts) if create_ts else 0
                issue_age = time.time() - create_ts
                if issue_age > ORPHAN_ISSUE_THRESHOLD_SECONDS:
                    logger.error(
                        "sync_issue_alert_stats: orphan issue detected (no alerts associated), "
                        "issue_id=%s, strategy_id=%s, age_seconds=%.0f",
                        issue.id,
                        issue.strategy_id,
                        issue_age,
                    )

            # Step 4: UPSERT 更新统计字段（仅更新统计字段，不覆盖 first_alert_time）
            IssueDocument.bulk_create(
                [
                    IssueDocument(
                        id=issue.id,
                        alert_count=alert_count,
                        last_alert_time=last_alert_time,
                        impact_scope=impact_scope,
                    )
                ],
                action=BulkActionType.UPSERT,
            )
        except Exception as e:
            logger.exception(
                "sync_issue_alert_stats: update issue failed, issue_id=%s, err=%s",
                issue.id,
                e,
            )

    logger.info("sync_issue_alert_stats: done, processed %d issues", len(active_issues))
