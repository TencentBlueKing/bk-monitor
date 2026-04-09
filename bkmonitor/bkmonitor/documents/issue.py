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

from bkmonitor.documents.base import BaseDocument, BulkActionType, Date, Flattened
from bkmonitor.documents.constants import ES_INDEX_SETTINGS
from constants.issue import IssueActivityType, IssueStatus

logger = logging.getLogger("fta_action.issue")


class IssueDocumentWriteError(Exception):
    """IssueDocument ES 持久化失败（重试仍失败）"""


@registry.register_document
class IssueDocument(BaseDocument):
    """Issue 主体文档（唯一持久化存储，对齐 AlertDocument）"""

    REINDEX_ENABLED = False

    id = field.Keyword(required=True)
    strategy_id = field.Keyword()
    bk_biz_id = field.Keyword()

    name = field.Text(fields={"raw": field.Keyword()})

    status = field.Keyword()
    is_regression = field.Boolean()
    assignee = field.Keyword(multi=True)
    priority = field.Keyword()

    alert_count = field.Long()
    first_alert_time = Date(format=BaseDocument.DATE_FORMAT)
    last_alert_time = Date(format=BaseDocument.DATE_FORMAT)

    impact_scope = Flattened()

    strategy_name = field.Text(fields={"raw": field.Keyword()})
    labels = field.Keyword(multi=True)

    aggregate_config = field.Object(enabled=False)

    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)
    resolved_time = Date(format=BaseDocument.DATE_FORMAT)

    class Index:
        name = "bkfta_issue"
        settings = ES_INDEX_SETTINGS.copy()

    class Meta:
        dynamic = MetaField("false")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.id is None:
            now = int(time.time()) if self.create_time is None else int(self.create_time)
            self.id = f"{now}{uuid.uuid4().hex[:8]}"

    @classmethod
    def parse_timestamp_by_id(cls, issue_id: str) -> int:
        return int(str(issue_id)[:10])

    def get_index_time(self):
        if self.create_time:
            return int(self.create_time)
        return self.parse_timestamp_by_id(self.id)

    def to_cache_dict(self):
        """
        Redis 缓存使用完整结构，避免读取端出现字段缺失。
        注意：ES 更新路径必须保留 to_dict(skip_empty=True) 的默认行为，防止局部更新误清空字段。
        """
        return super().to_dict(skip_empty=False)

    # ── 状态机方法 ──

    def assign(self, assignees: list[str], operator: str) -> None:
        """首次指派负责人：PENDING_REVIEW → UNRESOLVED"""
        if self.status != IssueStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot assign: current status={self.status}, expected={IssueStatus.PENDING_REVIEW}")
        old_status = self.status
        self.assignee = assignees
        self.status = IssueStatus.UNRESOLVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, None, ",".join(assignees), operator),
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator),
            ]
        )

    def reassign(self, assignees: list[str], operator: str) -> None:
        """改派负责人：UNRESOLVED 下改派，不触发状态流转"""
        if self.status != IssueStatus.UNRESOLVED:
            raise ValueError(f"Cannot reassign: current status={self.status}, expected={IssueStatus.UNRESOLVED}")
        old_assignees = list(self.assignee or [])
        self.assignee = assignees
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, ",".join(old_assignees), ",".join(assignees), operator),
            ]
        )

    def resolve(self, operator: str) -> None:
        """人工标记已解决：UNRESOLVED → RESOLVED or PENDING_REVIEW → RESOLVED"""
        if self.status not in IssueStatus.ACTIVE_STATUSES:
            raise ValueError(
                f"Cannot resolve: current status={self.status}, expected one of {IssueStatus.ACTIVE_STATUSES}"
            )
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

    def archive(self, operator: str) -> None:
        """归档（实例级）：PENDING_REVIEW → ARCHIVED or UNRESOLVED → ARCHIVED"""
        if self.status not in IssueStatus.ACTIVE_STATUSES:
            raise ValueError(
                f"Cannot archive: current status={self.status}, expected one of {IssueStatus.ACTIVE_STATUSES}"
            )
        old_status = self.status
        self.status = IssueStatus.ARCHIVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=False)
        self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.ARCHIVED, operator),
            ]
        )

    def reopen(self, operator: str) -> None:
        """重新打开：RESOLVED → UNRESOLVED"""
        if self.status != IssueStatus.RESOLVED:
            raise ValueError(f"Cannot reopen: current status={self.status}, expected={IssueStatus.RESOLVED}")
        old_status = self.status
        self.status = IssueStatus.UNRESOLVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator),
            ]
        )

    def restore(self, operator: str) -> None:
        """恢复归档：ARCHIVED → 归档前状态（从活动日志推断），无记录时回退到 PENDING_REVIEW"""
        if self.status != IssueStatus.ARCHIVED:
            raise ValueError(f"Cannot restore: current status={self.status}, expected={IssueStatus.ARCHIVED}")
        target_status = self._get_pre_archive_status()
        old_status = self.status
        self.status = target_status
        self.update_time = int(time.time())
        # 恢复后若目标状态为活跃状态则写回缓存
        self._persist_and_cache(active=target_status in IssueStatus.ACTIVE_STATUSES)
        self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, target_status, operator),
            ]
        )

    def add_comment(self, content: str, operator: str, now: int | None = None) -> "IssueActivityDocument":
        """
        添加跟进评论

        Args:
            content: 评论内容。
            operator: 操作人。
            now: 操作时间戳（秒），默认取当前时间。

        Returns:
            写入成功的 IssueActivityDocument 实例。
        """
        if now is None:
            now = int(time.time())
        extra_activities = []
        if self.status == IssueStatus.PENDING_REVIEW:
            old_status = self.status
            self.status = IssueStatus.UNRESOLVED
            extra_activities.append(
                IssueActivityDocument(
                    issue_id=self.id,
                    bk_biz_id=self.bk_biz_id,
                    activity_type=IssueActivityType.STATUS_CHANGE,
                    from_value=old_status,
                    to_value=IssueStatus.UNRESOLVED,
                    operator=operator,
                    time=now,
                    create_time=now,
                )
            )
        self.update_time = now
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)
        activity = IssueActivityDocument(
            issue_id=self.id,
            bk_biz_id=self.bk_biz_id,
            activity_type=IssueActivityType.COMMENT,
            content=content,
            operator=operator,
            time=now,
            create_time=now,
        )
        IssueActivityDocument.bulk_create([activity, *extra_activities])
        return activity

    def update_priority(self, priority: str, operator: str) -> None:
        """修改优先级（任意活跃状态均可）"""
        if self.status not in IssueStatus.ACTIVE_STATUSES:
            raise ValueError(f"Cannot update priority: current status={self.status} is not active")
        old_priority = self.priority
        self.priority = priority
        activits = [
            (
                IssueActivityType.PRIORITY_CHANGE,
                str(old_priority) if old_priority else None,
                str(priority),
                operator,
            ),
        ]
        if self.status == IssueStatus.PENDING_REVIEW:
            old_status = self.status
            self.status = IssueStatus.UNRESOLVED
            activits.append((IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator))
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        self._write_activities(activits)

    def _get_pre_archive_status(self) -> str:
        """
        从活动日志中找到最近一次归档操作（STATUS_CHANGE to_value=ARCHIVED）之前的状态。
        无法确定时兜底返回 PENDING_REVIEW。
        """
        try:
            search = (
                IssueActivityDocument.search(all_indices=True)
                .filter("term", issue_id=self.id)
                .filter("term", activity_type=IssueActivityType.STATUS_CHANGE)
                .filter("term", to_value=IssueStatus.ARCHIVED)
                .sort("-time")
                .extra(size=1)
            )
            results = list(search.execute())
            if results:
                return results[0].from_value or IssueStatus.PENDING_REVIEW
        except Exception:
            logger.exception("Failed to get pre_archive_status from activity log, issue_id=%s", self.id)
        return IssueStatus.PENDING_REVIEW

    def _persist_and_cache(self, active: bool) -> None:
        """
        UPSERT ES + 缓存处理。
        失败重试 1 次；仍失败则 raise IssueDocumentWriteError。
        """
        try:
            IssueDocument.bulk_create([self], action=BulkActionType.UPSERT)
        except Exception as e:
            logger.warning("IssueDocument UPSERT failed, retrying once, issue_id=%s: %s", self.id, e)
            try:
                IssueDocument.bulk_create([self], action=BulkActionType.UPSERT)
            except Exception as e2:
                logger.error("IssueDocument UPSERT retry failed, issue_id=%s: %s", self.id, e2)
                raise IssueDocumentWriteError(f"IssueDocument write failed: issue_id={self.id}") from e2

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
            cache_key, json.dumps(self.to_cache_dict()), ex=ISSUE_ACTIVE_CONTENT_KEY.ttl
        )

    def _delete_redis_cache(self) -> None:
        """删除 Redis 热缓存（Issue 变为非活跃后）"""
        from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY

        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(strategy_id=self.strategy_id)
        ISSUE_ACTIVE_CONTENT_KEY.client.delete(cache_key)

    def _write_activities(self, activity_tuples: list) -> None:
        """批量写 IssueActivityDocument"""
        now = int(time.time())
        activities = [
            IssueActivityDocument(
                issue_id=self.id,
                bk_biz_id=self.bk_biz_id,
                activity_type=atype,
                from_value=str(from_v) if from_v is not None else None,
                to_value=str(to_v) if to_v is not None else None,
                operator=operator,
                time=now,
                create_time=now,
            )
            for atype, from_v, to_v, operator in activity_tuples
        ]
        try:
            IssueActivityDocument.bulk_create(activities)
        except Exception:
            logger.exception("IssueActivityDocument bulk_create failed, issue_id=%s", self.id)


@registry.register_document
class IssueActivityDocument(BaseDocument):
    """Issue 活动/评论日志（append-only，对齐 AlertLog）"""

    REINDEX_ENABLED = False

    id = field.Keyword(required=True)
    issue_id = field.Keyword()
    bk_biz_id = field.Keyword()
    activity_type = field.Keyword()
    content = field.Text()
    operator = field.Keyword()
    from_value = field.Keyword()
    to_value = field.Keyword()
    time = Date(format=BaseDocument.DATE_FORMAT)
    create_time = Date(format=BaseDocument.DATE_FORMAT)

    class Index:
        name = "bkfta_fta_issue_act"
        settings = ES_INDEX_SETTINGS.copy()

    class Meta:
        dynamic = MetaField("false")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.id is None:
            now = int(time.time()) if self.create_time is None else int(self.create_time)
            self.id = f"{now}{uuid.uuid4().hex[:8]}"

    def get_index_time(self):
        if self.create_time:
            return int(self.create_time)
        return int(str(self.id)[:10])
