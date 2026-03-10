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
from typing import Optional

from alarm_backends.core.cache.issue import StrategyIssueConfigCacheManager
from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY, ISSUE_STRATEGY_LOCK
from alarm_backends.core.control.item import gen_condition_matcher
from alarm_backends.core.lock import RedisLock
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import IssueActivityDocument, IssueDocument, IssueDocumentWriteError
from constants.issue import IssueActivityType, IssuePriority, IssueStatus

logger = logging.getLogger("action")


class IssueAggregationProcessor:
    """Issue 聚合处理器（v1.2）

    集成到 CreateActionProcessor.do_create_actions()，对每条告警执行 Issue 聚合：
      1. 读配置（Redis 缓存 → MySQL 降级）
      2. 校验告警级别 + 过滤条件
      3. 查找活跃 Issue（无锁）
      4. 无活跃 Issue → 加锁创建（仅此处加锁）
      5. 关联当前告警（无锁，独立写入 AlertDocument.issue_id）
    """

    def __init__(self, alert: AlertDocument, strategy: dict):
        """
        :param alert: 当前正在处理的告警 ES 文档
        :param strategy: 策略缓存字典（StrategyCacheManager.get_strategy_by_id() 返回值）
        """
        self.alert = alert
        self.strategy = strategy

    def process(self) -> bool:
        """执行 Issue 聚合，返回 True 表示成功关联，False 表示跳过或锁失败"""
        # Step 1: 读配置（缓存 → MySQL）
        config = self._get_strategy_config()
        if not config or not config.get("is_enabled", True):
            return False

        # Step 2: 快速失败校验
        if not self._check_alert_level(config):
            return False
        if not self._check_conditions(config):
            return False

        # Step 3: 查找活跃 Issue（无锁）
        issue = self._find_active_issue()

        if issue is None:
            # Step 4: 无活跃 Issue → 非阻塞加锁创建
            lock = self._acquire_lock()
            if lock is None:
                # 锁失败：记录日志后直接返回，不等待不重试
                # 此窗口期内加锁失败的告警由 sync_issue_alert_stats 周期补偿回填
                logger.warning(
                    "IssueAggregationProcessor: acquire lock failed, skip. "
                    "strategy_id=%s, alert_id=%s",
                    self.strategy.get("id"),
                    self.alert.id,
                )
                return False
            try:
                # 二次确认（已持锁），防止极端竞争下重复创建
                issue = self._find_active_issue()
                if issue is None:
                    issue = self._create_issue(config)
                    # _persist_and_cache 失败则 raise IssueDocumentWriteError
                    # 上层 do_create_actions 的 except 捕获，活动日志不写，保证一致性
                    issue._persist_and_cache(active=True)
                    IssueActivityDocument.bulk_create([self._make_create_activity(issue)])
            except IssueDocumentWriteError:
                raise
            except Exception as e:
                logger.exception(
                    "IssueAggregationProcessor: create issue failed. strategy_id=%s, err=%s",
                    self.strategy.get("id"),
                    e,
                )
                return False
            finally:
                lock.release()

        # Step 5: 关联当前告警（无锁，独立写入 AlertDocument.issue_id）
        self._associate_alert(issue)
        return True

    # ── 私有方法 ────────────────────────────────────────────────────────────────

    def _get_strategy_config(self):
        """从缓存读取策略 Issue 配置（缓存 → MySQL）"""
        strategy_id = self.strategy.get("id")
        if not strategy_id:
            return None
        return StrategyIssueConfigCacheManager.get_config_by_strategy_id(strategy_id)

    def _check_alert_level(self, config) -> bool:
        """检查告警级别是否在配置的生效级别列表中"""
        alert_levels = config.get("alert_levels", [])
        if not alert_levels:
            return False
        severity = self.alert.severity
        return severity in alert_levels

    def _check_conditions(self, config) -> bool:
        """检查告警维度是否满足过滤条件

        复用 gen_condition_matcher 和 condition.is_match()，格式对齐策略 agg_condition。
        conditions 字段格式：[{"key": ..., "method": ..., "value": [...]}]
        字段缺失或不命中时按"不满足条件"处理，直接跳过。
        """
        conditions = config.get("conditions", [])
        if not conditions:
            return True  # 无过滤条件视为全量命中

        try:
            # gen_condition_matcher 需要 condition 字段（AND/OR 连接符），默认 AND
            agg_condition = [dict(cond, condition="and") for cond in conditions]
            condition_matcher = gen_condition_matcher(agg_condition)

            # 从告警维度列表构造 {key: value} 字典供 is_match() 使用
            dimensions = {}
            if hasattr(self.alert, "dimensions") and self.alert.dimensions:
                for dim in self.alert.dimensions:
                    if hasattr(dim, "key") and hasattr(dim, "value"):
                        dimensions[dim.key] = dim.value

            return condition_matcher.is_match(dimensions)
        except Exception as e:
            logger.warning(
                "IssueAggregationProcessor._check_conditions failed, skip alert. "
                "strategy_id=%s, alert_id=%s, err=%s",
                self.strategy.get("id"),
                self.alert.id,
                e,
            )
            return False

    def _find_active_issue(self) -> Optional[IssueDocument]:
        """查找活跃 Issue：Redis 命中 → 反序列化；未命中 → 查 ES；无活跃 → None"""
        strategy_id = self.strategy.get("id")

        # 优先读 Redis 热缓存
        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(strategy_id=strategy_id)
        cached = ISSUE_ACTIVE_CONTENT_KEY.client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                if data and data.get("status") in IssueStatus.ACTIVE_STATUSES:
                    return IssueDocument(**data)
            except Exception as e:
                logger.warning(
                    "IssueAggregationProcessor: Redis cache deserialize failed, "
                    "strategy_id=%s, err=%s",
                    strategy_id,
                    e,
                )

        # Redis 未命中，查 ES
        try:
            hits = (
                IssueDocument.search(all_indices=True)
                .filter("term", strategy_id=str(strategy_id))
                .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
                .sort("-create_time")
                .params(size=1)
                .execute()
                .hits
            )
            if hits:
                issue = IssueDocument(**hits[0].to_dict())
                # 回写缓存
                issue._update_redis_cache()
                return issue
        except Exception as e:
            logger.warning(
                "IssueAggregationProcessor: ES query active issue failed, "
                "strategy_id=%s, err=%s",
                strategy_id,
                e,
            )
        return None

    def _check_is_regression(self) -> bool:
        """检查同 strategy_id 是否有历史已解决 Issue（复现场景）"""
        try:
            return (
                IssueDocument.search(all_indices=True)
                .filter("term", strategy_id=str(self.strategy.get("id")))
                .filter("term", status=IssueStatus.RESOLVED)
                .count()
                > 0
            )
        except Exception as e:
            logger.warning(
                "IssueAggregationProcessor._check_is_regression failed, "
                "strategy_id=%s, err=%s",
                self.strategy.get("id"),
                e,
            )
            return False

    def _create_issue(self, config) -> IssueDocument:
        """创建新的 IssueDocument（含 is_regression / 默认名称 / 配置快照）"""
        strategy_id = self.strategy.get("id")
        strategy_name = self.strategy.get("name", "")
        bk_biz_id = self.strategy.get("bk_biz_id")
        labels = self.strategy.get("labels", [])
        now = int(time.time())

        is_regression = self._check_is_regression()

        # impact_scope 初值：从告警维度提取
        impact_scope = {}
        if hasattr(self.alert, "dimensions") and self.alert.dimensions:
            for dim in self.alert.dimensions:
                if hasattr(dim, "key") and hasattr(dim, "value"):
                    impact_scope[dim.key] = dim.value

        aggregate_config = {
            "aggregate_dimensions": config.get("aggregate_dimensions", []),
            "conditions": config.get("conditions", []),
            "alert_levels": config.get("alert_levels", []),
        }

        issue = IssueDocument(
            strategy_id=str(strategy_id),
            bk_biz_id=str(bk_biz_id),
            name=strategy_name,
            status=IssueStatus.PENDING_REVIEW,
            is_regression=is_regression,
            assignee="",
            priority=IssuePriority.DEFAULT,
            alert_count=1,
            first_alert_time=now,
            last_alert_time=now,
            impact_scope=impact_scope,
            strategy_name=strategy_name,
            labels=labels,
            aggregate_config=aggregate_config,
            create_time=now,
            update_time=now,
        )
        return issue

    def _make_create_activity(self, issue: IssueDocument) -> IssueActivityDocument:
        """生成 Issue 创建活动记录"""
        now = int(time.time())
        return IssueActivityDocument(
            issue_id=issue.id,
            bk_biz_id=issue.bk_biz_id,
            activity_type=IssueActivityType.CREATE,
            operator="system",
            time=now,
            create_time=now,
        )

    def _associate_alert(self, issue: IssueDocument) -> None:
        """写入 AlertDocument.issue_id（失败重试 1 次，仍失败记 error log，不阻塞主流程）

        alert_count 统计由 sync_issue_alert_stats 周期任务异步更新，此处不维护。
        """
        self.alert.issue_id = issue.id
        try:
            AlertDocument.bulk_create([self.alert], action=BulkActionType.UPSERT)
        except Exception as e:
            logger.warning(
                "IssueAggregationProcessor: alert.issue_id write failed (retry), "
                "issue_id=%s, alert_id=%s, err=%s",
                issue.id,
                self.alert.id,
                e,
            )
            try:
                AlertDocument.bulk_create([self.alert], action=BulkActionType.UPSERT)
            except Exception as e2:
                logger.error(
                    "IssueAggregationProcessor: alert.issue_id write failed permanently, "
                    "issue_id=%s, alert_id=%s, err=%s",
                    issue.id,
                    self.alert.id,
                    e2,
                )
                # 漏关联由 sync_issue_alert_stats 周期补偿，此处不阻塞主流程

    def _acquire_lock(self) -> Optional[RedisLock]:
        """非阻塞尝试获取策略级分布式锁，失败返回 None"""
        strategy_id = self.strategy.get("id")
        lock_key = ISSUE_STRATEGY_LOCK.get_key(strategy_id=strategy_id)
        lock = RedisLock(lock_key, ISSUE_STRATEGY_LOCK.ttl)
        if lock.acquire(0):  # blocking=False（等待时间为 0）
            return lock
        return None
