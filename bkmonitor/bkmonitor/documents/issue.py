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


class IssueNotFoundError(Exception):
    """Issue 不存在或业务归属不匹配"""


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

    @classmethod
    def get_issue_or_raise(cls, issue_id: str, bk_biz_id: int | None = None) -> "IssueDocument":
        """
        按 issue_id 查询单条 IssueDocument，不存在则抛出 IssueNotFoundError。
        使用 all_indices=True 避免跨天漏查。

        Args:
            issue_id: 要查询的 Issue ID。
            bk_biz_id: 若传入，则在查出 Issue 后校验业务归属，防止越权操作。
                       Issue 的 bk_biz_id 与传入值不匹配时抛出 IssueNotFoundError（而非权限错误），
                       避免泄露其他业务的 Issue 存在信息。

        Returns:
            IssueDocument 实例。

        Raises:
            IssueNotFoundError: Issue 不存在，或 bk_biz_id 不匹配时抛出。
        """
        search = cls.search(all_indices=True).filter("term", **{"_id": issue_id}).params(size=1)
        hits = search.execute().hits
        if not hits:
            raise IssueNotFoundError(f"Issue not found, issue_id={issue_id}")
        # IssueDocument._source 中含 id 字段，需先 pop 再显式传入 meta.id，
        # 否则会触发 "multiple values for keyword argument 'id'"；
        # 若不传 meta.id，__init__ 会自动生成新 ID，导致 UPSERT 退化为 INSERT。
        source = hits[0].to_dict()
        source.pop("id", None)
        issue = cls(id=hits[0].meta.id, **source)
        if bk_biz_id is not None and int(issue.bk_biz_id) != int(bk_biz_id):
            raise IssueNotFoundError(f"Issue not found, issue_id={issue_id}")
        return issue

    def to_cache_dict(self):
        """
        Redis 缓存使用完整结构，避免读取端出现字段缺失。
        注意：ES 更新路径必须保留 to_dict(skip_empty=True) 的默认行为，防止局部更新误清空字段。
        """
        return super().to_dict(skip_empty=False)

    # ── 状态机方法 ──

    def assign(self, assignees: list[str], operator: str) -> list:
        """首次指派负责人：PENDING_REVIEW → UNRESOLVED"""
        if self.status != IssueStatus.PENDING_REVIEW:
            raise ValueError(f"Cannot assign: current status={self.status}, expected={IssueStatus.PENDING_REVIEW}")
        old_status = self.status
        self.assignee = assignees
        self.status = IssueStatus.UNRESOLVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        return self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, None, ",".join(assignees), operator, None),
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator, None),
            ]
        )

    def reassign(self, assignees: list[str], operator: str) -> list:
        """改派负责人(任意状态均可)：不触发状态流转"""
        old_assignees = list(self.assignee or [])
        self.assignee = assignees
        self.update_time = int(time.time())
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)
        return self._write_activities(
            [
                (IssueActivityType.ASSIGNEE_CHANGE, ",".join(old_assignees), ",".join(assignees), operator, None),
            ]
        )

    def resolve(self, operator: str) -> list:
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
        return self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.RESOLVED, operator, None),
            ]
        )

    def archive(self, operator: str) -> list:
        """归档（实例级）：PENDING_REVIEW → ARCHIVED or UNRESOLVED → ARCHIVED"""
        if self.status not in IssueStatus.ACTIVE_STATUSES:
            raise ValueError(
                f"Cannot archive: current status={self.status}, expected one of {IssueStatus.ACTIVE_STATUSES}"
            )
        old_status = self.status
        self.status = IssueStatus.ARCHIVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=False)
        return self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.ARCHIVED, operator, None),
            ]
        )

    def reopen(self, operator: str) -> list:
        """重新打开：RESOLVED → UNRESOLVED"""
        if self.status != IssueStatus.RESOLVED:
            raise ValueError(f"Cannot reopen: current status={self.status}, expected={IssueStatus.RESOLVED}")
        old_status = self.status
        self.status = IssueStatus.UNRESOLVED
        self.update_time = int(time.time())
        self._persist_and_cache(active=True)
        return self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator, None),
            ]
        )

    def restore(self, operator: str) -> list:
        """恢复归档：ARCHIVED → 归档前状态（从活动日志推断），无记录时回退到 PENDING_REVIEW"""
        if self.status != IssueStatus.ARCHIVED:
            raise ValueError(f"Cannot restore: current status={self.status}, expected={IssueStatus.ARCHIVED}")
        target_status = self._get_pre_archive_status()
        old_status = self.status
        self.status = target_status
        self.update_time = int(time.time())
        # 恢复后若目标状态为活跃状态则写回缓存
        self._persist_and_cache(active=target_status in IssueStatus.ACTIVE_STATUSES)
        return self._write_activities(
            [
                (IssueActivityType.STATUS_CHANGE, old_status, target_status, operator, None),
            ]
        )

    def add_comment(self, content: str, operator: str) -> list:
        """
        添加跟进评论

        Args:
            content: 评论内容。
            operator: 操作人。

        Returns:
            该 Issue 全部活动日志列表（含本次新增），按时间降序排列。
        """
        activities = [
            (IssueActivityType.COMMENT, None, None, operator, content),
        ]
        if self.status == IssueStatus.PENDING_REVIEW:
            old_status = self.status
            self.status = IssueStatus.UNRESOLVED
            activities.append((IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator, None))
        self.update_time = int(time.time())
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)
        return self._write_activities(activities)

    def update_priority(self, priority: str, operator: str) -> list:
        """修改优先级（任意状态均可）"""
        old_priority = self.priority
        self.priority = priority
        activities = [
            (
                IssueActivityType.PRIORITY_CHANGE,
                str(old_priority) if old_priority else None,
                str(priority),
                operator,
                None,
            ),
        ]
        if self.status == IssueStatus.PENDING_REVIEW:
            old_status = self.status
            self.status = IssueStatus.UNRESOLVED
            activities.append((IssueActivityType.STATUS_CHANGE, old_status, IssueStatus.UNRESOLVED, operator, None))
        self.update_time = int(time.time())
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)
        return self._write_activities(activities)

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

    def _write_activities(self, activity_tuples: list, now: int | None = None) -> list:
        """
        批量写 IssueActivityDocument，返回该 Issue 全部活动日志（含本次新增）。

        activity_tuples 每项格式为 (activity_type, from_value, to_value, operator, content)，
        其中 content 仅 COMMENT 类型使用，其余传 None。
        """
        if now is None:
            now = int(time.time())
        # 写入前先查询历史活动日志，避免写后读的 ES 延迟问题
        existing_activities = []
        try:
            search = (
                IssueActivityDocument.search(all_indices=True)
                .filter("term", issue_id=self.id)
                .sort("-time")
                .extra(size=500)
            )
            hits = search.execute().hits
            existing_activities = [
                {
                    "bk_biz_id": hit.bk_biz_id,
                    "activity_id": hit.meta.id,
                    "activity_type": hit.activity_type,
                    "operator": hit.operator or "",
                    "from_value": hit.from_value,
                    "to_value": hit.to_value,
                    "content": hit.content,
                    "time": int(hit.time) if hit.time else 0,
                }
                for hit in hits
            ]
        except Exception:
            logger.exception("Failed to query existing activities before write, issue_id=%s", self.id)

        new_activities = [
            IssueActivityDocument(
                issue_id=self.id,
                bk_biz_id=self.bk_biz_id,
                activity_type=atype,
                from_value=str(from_v) if from_v is not None else None,
                to_value=str(to_v) if to_v is not None else None,
                operator=operator,
                content=content,
                time=now,
                create_time=now,
            )
            for atype, from_v, to_v, operator, content in activity_tuples
        ]
        try:
            IssueActivityDocument.bulk_create(new_activities)
        except Exception:
            logger.exception("IssueActivityDocument bulk_create failed, issue_id=%s", self.id)

        # 将本次新增的活动拼到历史记录头部（新活动时间最新，排在最前）
        new_activity_records = [
            {
                "bk_biz_id": act.bk_biz_id,
                "activity_id": act.id,
                "activity_type": act.activity_type,
                "operator": act.operator or "",
                "from_value": act.from_value,
                "to_value": act.to_value,
                "content": act.content,
                "time": act.time,
            }
            for act in new_activities
        ]
        return new_activity_records + existing_activities


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
