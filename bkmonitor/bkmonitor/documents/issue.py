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
import uuid

from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import MetaField, field

from bkmonitor.documents.base import BaseDocument, BulkActionType, Date
from bkmonitor.documents.constants import ES_INDEX_SETTINGS
from constants.issue import IssueActivityType, IssuePriority, IssueStatus

logger = logging.getLogger("action")


class IssueDocumentWriteError(Exception):
    """IssueDocument ES 持久化失败（重试仍失败）"""

    pass


@registry.register_document
class IssueDocument(BaseDocument):
    """Issue 主体文档

    唯一持久化存储，对齐 AlertDocument 索引分片策略。
    id 前 10 位为秒级时间戳，用于按时间范围缩小索引查询。
    """

    class Index:
        name = "bkfta_issue"
        settings = ES_INDEX_SETTINGS.copy()

    class Meta:
        dynamic = MetaField("false")

    # 第一阶段保留全量历史 Issue，不做 active-only reindex
    REINDEX_ENABLED = False

    # 核心标识
    id = field.Keyword(required=True)
    strategy_id = field.Keyword()
    bk_biz_id = field.Keyword()

    # 内容：创建时按稳定规则生成（至少含 strategy_name）；后续 API 阶段支持人工编辑
    name = field.Text(fields={"raw": field.Keyword()})

    # 状态机字段
    status = field.Keyword()
    is_regression = field.Boolean()
    # 空字符串表示未指派；展示层统一渲染为"未指派"
    assignee = field.Keyword()
    priority = field.Keyword()

    # 告警统计（由周期任务 sync_issue_alert_stats 异步更新，不在实时写路径维护）
    alert_count = field.Long()
    first_alert_time = Date(format=BaseDocument.DATE_FORMAT)  # 创建时写入，后续不变
    last_alert_time = Date(format=BaseDocument.DATE_FORMAT)  # 周期任务更新

    # 影响范围快照：创建时写初值，周期任务重算覆盖；允许为空
    impact_scope = field.Object(enabled=False)

    # 策略冗余信息（避免跨索引 JOIN）
    strategy_name = field.Text(fields={"raw": field.Keyword()})
    labels = field.Keyword(multi=True)

    # 聚合配置快照（创建时保存，用于历史追溯）
    aggregate_config = field.Object(enabled=False)

    # 时间戳
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)
    resolved_time = Date(format=BaseDocument.DATE_FORMAT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.id is None:
            now_ts = int(time.time())
            self.id = f"{now_ts}{uuid.uuid4().hex[:8]}"

    @classmethod
    def parse_timestamp_by_id(cls, issue_id: str) -> int:
        """从 Issue id 前缀反解创建时间戳（秒）"""
        return int(str(issue_id)[:10])

    def get_index_time(self):
        """用于写入时确定目标时间分片索引"""
        if self.create_time:
            ts = self.create_time
            # create_time 可能是 int 或 datetime；统一转换为 int
            if hasattr(ts, "timestamp"):
                return int(ts.timestamp())
            return int(ts)
        return self.parse_timestamp_by_id(self.id)

    # ── 状态机方法 ─────────────────────────────────────────────────────────────

    def assign(self, assignee: str, operator: str) -> None:
        """首次指派负责人：PENDING_REVIEW → UNRESOLVED"""
        if self.status != IssueStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot assign: status={self.status}")
        old_status = self.status
        self.assignee = assignee
        self.status = IssueStatus.UNRESOLVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, None, assignee, operator),
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator),
            ]
        )

    def reassign(self, assignee: str, operator: str) -> None:
        """改派负责人：UNRESOLVED 下改派，不流转状态"""
        if self.status != IssueStatus.UNRESOLVED:
            raise ValueError(f"Cannot reassign: status={self.status}")
        old_assignee = self.assignee
        self.assignee = assignee
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, old_assignee, assignee, operator),
            ]
        )

    def resolve(self, operator: str) -> None:
        """人工标记已解决：UNRESOLVED → RESOLVED"""
        if self.status != IssueStatus.UNRESOLVED:
            raise ValueError(f"Cannot resolve: status={self.status}")
        old_status = self.status
        self.status = IssueStatus.RESOLVED
        self.resolved_time = int(time.time())
        self.update_time = self.resolved_time
        self._persist_and_cache(active=False)
        self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.RESOLVED, operator),
            ]
        )

    def reject(self, operator: str) -> None:
        """拒绝/无效：PENDING_REVIEW → REJECTED"""
        if self.status != IssueStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot reject: status={self.status}")
        old_status = self.status
        self.status = IssueStatus.REJECTED
        self.update_time = int(time.time())
        self._persist_and_cache(active=False)
        self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.REJECTED, operator),
            ]
        )

    def update_priority(self, priority: str, operator: str) -> None:
        """修改优先级（任意活跃状态均可）"""
        if self.status not in IssueStatus.ACTIVE_STATUSES:
            raise ValueError(f"Cannot update priority: status={self.status}")
        old_priority = self.priority
        self.priority = priority
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.PRIORITY_CHANGE, str(old_priority), str(priority), operator),
            ]
        )

    def _persist_and_cache(self, active: bool) -> None:
        """UPSERT ES + 处理缓存。

        ES 写失败重试 1 次；重试仍失败则 raise IssueDocumentWriteError。
        状态机方法不捕获该异常，保证"主文档落库"与"活动日志写入"不分裂。
        """
        try:
            IssueDocument.bulk_create([self], action=BulkActionType.UPSERT)
        except Exception as e:
            logger.warning(
                "IssueDocument UPSERT failed, retrying once, issue_id=%s: %s",
                self.id,
                e,
            )
            try:
                IssueDocument.bulk_create([self], action=BulkActionType.UPSERT)
            except Exception as e2:
                logger.error(
                    "IssueDocument UPSERT retry failed, issue_id=%s: %s",
                    self.id,
                    e2,
                )
                raise IssueDocumentWriteError(
                    f"IssueDocument write failed: issue_id={self.id}"
                ) from e2

        if active:
            self._update_redis_cache()
        else:
            self._delete_redis_cache()

    def _update_redis_cache(self) -> None:
        """写回 Redis 热缓存（活跃 Issue）"""
        import json

        from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY

        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(strategy_id=self.strategy_id)
        ISSUE_ACTIVE_CONTENT_KEY.client.set(
            cache_key,
            json.dumps(self.to_dict()),
            ex=ISSUE_ACTIVE_CONTENT_KEY.ttl,
        )

    def _delete_redis_cache(self) -> None:
        """删除 Redis 热缓存（Issue 变为非活跃状态后）"""
        from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY

        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(strategy_id=self.strategy_id)
        ISSUE_ACTIVE_CONTENT_KEY.client.delete(cache_key)

    def _write_activities(self, activity_tuples: list) -> None:
        """批量写 IssueActivityDocument（主文档落库后才调用）"""
        now = int(time.time())
        activities = [
            IssueActivityDocument(
                issue_id=self.id,
                bk_biz_id=self.bk_biz_id,
                activity_type=atype,
                from_value=from_v,
                to_value=to_v,
                operator=operator,
                time=now,
                create_time=now,
            )
            for atype, from_v, to_v, operator in activity_tuples
        ]
        IssueActivityDocument.bulk_create(activities)


@registry.register_document
class IssueActivityDocument(BaseDocument):
    """Issue 活动/评论日志（append-only，对齐 AlertLog）"""

    class Index:
        name = "bkfta_issue_activity"
        settings = ES_INDEX_SETTINGS.copy()

    class Meta:
        dynamic = MetaField("false")

    REINDEX_ENABLED = False

    id = field.Keyword(required=True)
    issue_id = field.Keyword()
    bk_biz_id = field.Keyword()
    activity_type = field.Keyword()
    # 仅 COMMENT 类型写入用户评论；系统活动由结构化字段表达
    content = field.Text()
    operator = field.Keyword()
    from_value = field.Keyword()
    to_value = field.Keyword()
    time = Date(format=BaseDocument.DATE_FORMAT)
    create_time = Date(format=BaseDocument.DATE_FORMAT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.id is None:
            now_ts = int(time.time())
            self.id = f"{now_ts}{uuid.uuid4().hex[:8]}"

    def get_index_time(self):
        if self.create_time:
            ts = self.create_time
            if hasattr(ts, "timestamp"):
                return int(ts.timestamp())
            return int(ts)
        return int(str(self.id)[:10])
