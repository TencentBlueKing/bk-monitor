"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time

from alarm_backends.core.cache.issue import StrategyIssueConfigCache
from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY, ISSUE_STRATEGY_LOCK
from alarm_backends.core.control.item import gen_condition_matcher
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import (
    IssueActivityDocument,
    IssueDocument,
)
from constants.issue import IssueActivityType, IssuePriority, IssueStatus

logger = logging.getLogger("fta_action.issue")


class IssueAggregationProcessor:
    """Issue 聚合处理器：在 fta_action 阶段将告警聚合到 Issue"""

    def __init__(self, alert: AlertDocument, strategy: dict):
        self.alert = alert
        self.strategy = strategy
        self.strategy_id = strategy.get("id") or (int(alert.strategy_id) if alert.strategy_id else 0)

    def process(self) -> bool:
        """
        主入口：配置校验 → 查找活跃 Issue → 创建/关联
        Returns True if alert was associated to an issue.
        """
        if not self.strategy_id:
            return False

        config = self._get_strategy_config()
        if not config or not config.get("is_enabled"):
            return False
        if not self._check_alert_level(config):
            return False
        if not self._check_conditions(config):
            return False

        issue = self._find_active_issue()

        if issue is None:
            lock = self._acquire_lock()
            if not lock:
                logger.warning(
                    "IssueAggregationProcessor: acquire lock failed, skip, strategy_id=%s, alert_id=%s",
                    self.strategy_id,
                    self.alert.id,
                )
                return False
            try:
                issue = self._find_active_issue()
                if issue is None:
                    issue = self._create_issue(config)
                    issue._persist_and_cache(active=True)
                    IssueActivityDocument.bulk_create([self._make_create_activity(issue)])
            finally:
                try:
                    lock.release()
                except Exception:
                    pass

        self._associate_alert(issue)
        return True

    def _get_strategy_config(self) -> dict | None:
        return StrategyIssueConfigCache.get(self.strategy_id)

    def _check_alert_level(self, config: dict) -> bool:
        alert_levels = config.get("alert_levels", [])
        if not alert_levels:
            return False
        severity = int(self.alert.severity) if self.alert.severity else 0
        return severity in alert_levels

    def _check_conditions(self, config: dict) -> bool:
        """复用 access 模块 gen_condition_matcher 匹配告警维度"""
        conditions = config.get("conditions", [])
        if not conditions:
            return True

        alert_dimensions = self._get_alert_dimensions()
        agg_condition = []
        for cond in conditions:
            if not isinstance(cond, dict):
                logger.warning(
                    "IssueAggregationProcessor: invalid condition type, strategy_id=%s, alert_id=%s, condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            if any(k not in cond for k in ("key", "method", "value")):
                logger.warning(
                    "IssueAggregationProcessor: invalid condition format, strategy_id=%s, alert_id=%s, condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            if not cond.get("key") or cond.get("value") is None:
                logger.warning(
                    "IssueAggregationProcessor: invalid condition value, strategy_id=%s, alert_id=%s, condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            agg_condition.append({"key": cond["key"], "method": cond["method"], "value": cond["value"]})

        if not agg_condition:
            logger.warning(
                "IssueAggregationProcessor: conditions present but empty after parse, strategy_id=%s, alert_id=%s",
                self.strategy_id,
                self.alert.id,
            )
            return False

        try:
            matcher = gen_condition_matcher(agg_condition)
            return matcher.is_match(alert_dimensions)
        except Exception:
            logger.warning(
                "IssueAggregationProcessor: condition match failed, strategy_id=%s, alert_id=%s",
                self.strategy_id,
                self.alert.id,
                exc_info=True,
            )
            return False

    def _get_alert_dimensions(self) -> dict:
        """从 AlertDocument.dimensions 构建 {key: value} 映射"""
        dimensions = {}
        if not self.alert.dimensions:
            return dimensions
        for dim in self.alert.dimensions:
            if isinstance(dim, dict):
                key = dim.get("key", "")
                value = dim.get("value", "")
            else:
                key = getattr(dim, "key", "")
                value = getattr(dim, "value", "")
            if key:
                dimensions[key] = value
        return dimensions

    def _find_active_issue(self) -> IssueDocument | None:
        """Redis → ES 查找活跃 Issue"""
        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(strategy_id=self.strategy_id)
        cached = ISSUE_ACTIVE_CONTENT_KEY.client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return IssueDocument(**data)
            except Exception:
                pass

        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", strategy_id=str(self.strategy_id))
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .sort("-create_time")
            .params(size=1)
        )
        hits = search.execute().hits
        if hits:
            issue = IssueDocument(**hits[0].to_dict())
            issue._update_redis_cache()
            return issue

        return None

    def _create_issue(self, config: dict) -> IssueDocument:
        now = int(time.time())
        is_regression = self._check_is_regression()

        strategy_name = self.strategy.get("name", "")
        name = f"[回归] {strategy_name}" if is_regression else strategy_name

        labels = []
        for label in self.strategy.get("labels", []):
            if isinstance(label, str):
                labels.append(label)

        issue = IssueDocument(
            strategy_id=str(self.strategy_id),
            bk_biz_id=str(self.strategy.get("bk_biz_id", "")),
            name=name,
            status=IssueStatus.PENDING_REVIEW,
            is_regression=is_regression,
            assignee=[],
            priority=IssuePriority.DEFAULT,
            alert_count=1,
            first_alert_time=self.alert.begin_time or now,
            last_alert_time=self.alert.begin_time or now,
            impact_scope={},
            strategy_name=strategy_name,
            labels=labels,
            aggregate_config={
                "aggregate_dimensions": config.get("aggregate_dimensions", []),
                "conditions": config.get("conditions", []),
                "alert_levels": config.get("alert_levels", []),
            },
            create_time=now,
            update_time=now,
        )
        return issue

    def _check_is_regression(self) -> bool:
        count = (
            IssueDocument.search(all_indices=True)
            .filter("term", strategy_id=str(self.strategy_id))
            .filter("term", status=IssueStatus.RESOLVED)
            .count()
        )
        return count > 0

    def _make_create_activity(self, issue: IssueDocument) -> IssueActivityDocument:
        now = int(time.time())
        return IssueActivityDocument(
            issue_id=issue.id,
            bk_biz_id=issue.bk_biz_id,
            activity_type=IssueActivityType.CREATE,
            operator="system",
            time=now,
            create_time=now,
        )

    def _associate_alert(self, issue: IssueDocument):
        """写入 AlertDocument.issue_id，失败重试 1 次"""
        self.alert.issue_id = issue.id
        try:
            AlertDocument.bulk_create(
                [AlertDocument(id=self.alert.id, issue_id=issue.id)],
                action=BulkActionType.UPSERT,
            )
        except Exception as e:
            logger.warning("IssueAggregationProcessor: alert issue_id write failed (retry), error=%s", e)
            try:
                AlertDocument.bulk_create(
                    [AlertDocument(id=self.alert.id, issue_id=issue.id)],
                    action=BulkActionType.UPSERT,
                )
            except Exception as e2:
                logger.error(
                    "IssueAggregationProcessor: alert issue_id write failed permanently, "
                    "issue_id=%s, alert_id=%s, error=%s",
                    issue.id,
                    self.alert.id,
                    e2,
                )

    def _acquire_lock(self):
        """一次性尝试获取锁，失败返回 None。使用 token 保证只释放自己持有的锁。"""
        import uuid as _uuid

        lock_key = ISSUE_STRATEGY_LOCK.get_key(strategy_id=self.strategy_id)
        client = ISSUE_STRATEGY_LOCK.client
        token = _uuid.uuid4().hex
        acquired = client.set(lock_key, token, nx=True, ex=ISSUE_STRATEGY_LOCK.ttl)
        if acquired:
            return _TokenLock(client, lock_key, token)
        return None


class _TokenLock:
    """基于 token 的安全锁：只释放自己持有的锁，避免 TTL 过期后误删"""

    _release_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, client, key, token):
        self._client = client
        self._key = key
        self._token = token

    def release(self):
        self._client.eval(self._release_script, 1, self._key, self._token)
