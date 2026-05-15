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


class IssueNameDuplicatedError(Exception):
    """同业务下已存在同名 Issue"""


class IssueActivityNotFoundError(Exception):
    """Issue 活动记录不存在"""


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

    # 指纹：唯一活跃 Issue 的标识（按 strategy_id + aggregate_dimensions 取值组合算出）
    # 创建时写入，后续不变。空仅会出现在迁移函数运行前的 legacy 数据；
    # 部署 post_migrate hook 会自动 RESOLVE 所有 fingerprint=null 的活跃 Issue，
    # 运行期 processor 仅在部署窗口期短暂遇到（read-only 兜底，见 _find_active_issue Step 2）。
    fingerprint = field.Keyword()
    # 维度取值快照：与 fingerprint 一对一。形如 {"bk_host_id": "9185731", "service": "order"}；
    # aggregate_dimensions=[] 时为 {}。
    # 使用 Flattened（与 impact_scope 同款）：动态 key 但需要按子字段查询，
    # 支持前端按 dimension_values.bk_host_id="X" 直接过滤 Issue 列表 / 做 TopN 聚合。
    dimension_values = Flattened()

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

    def edit_comment(self, activity_id: str, content: str, operator: str) -> list:
        """
        编辑已有评论

        Args:
            activity_id: 待编辑的评论文档 ID
            content: 新的评论内容。
            operator: 操作人，必须等于原评论作者。

        Returns:
            该 Issue 全部活动日志列表（含本次更新与新追加的 COMMENT_EDIT 记录），按时间降序排列。

        Raises:
            IssueActivityNotFoundError: 指定 activity_id 的 IssueActivityDocument不存在。
            PermissionError: operator 不是原评论操作者
        """
        # 查询原评论信息
        search = (
            IssueActivityDocument.search(all_indices=True)
            .filter("term", **{"_id": activity_id})
            .filter("term", issue_id=self.id)
            .filter("term", activity_type=IssueActivityType.COMMENT)
            .params(size=1)
        )
        hits = search.execute().hits
        if not hits:
            raise IssueActivityNotFoundError(f"IssueActivity not found, issue_id={self.id}, activity_id={activity_id}")
        original = hits[0]

        # 权限校验：仅原作者可编辑
        if original.operator != operator:
            raise PermissionError(f"Only the original author can edit this comment, activity_id={activity_id}")

        old_content = original.content or ""
        # 内容未变化时直接返回当前活动列表，不写 ES
        if old_content == content:
            return self._read_activities()

        self.update_time = int(time.time())
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)

        # 写入前先查询历史活动日志，避免写后读 ES 刷新延迟带来的"漏读最新写入"问题
        existing_activities = self._read_activities()

        # 评论编辑内容和评论编辑活动记录写入
        edited_comment = IssueActivityDocument(
            issue_id=self.id,
            bk_biz_id=self.bk_biz_id,
            activity_type=IssueActivityType.COMMENT,
            from_value=None,
            to_value=None,
            operator=operator,
            content=content,
            time=int(original.time),
            create_time=int(original.create_time),
        )
        edited_comment.meta.id = activity_id
        edited_comment.id = activity_id

        edit_activity = IssueActivityDocument(
            issue_id=self.id,
            bk_biz_id=self.bk_biz_id,
            activity_type=IssueActivityType.COMMENT_EDIT,
            from_value=old_content,
            to_value=content,
            operator=operator,
            content=None,
            time=self.update_time,
            create_time=self.update_time,
        )

        try:
            IssueActivityDocument.bulk_create([edited_comment, edit_activity], action=BulkActionType.UPSERT)
        except Exception as e:
            logger.warning(
                "IssueActivityDocument edit bulk_create failed, retrying once, issue_id=%s, activity_id=%s: %s",
                self.id,
                activity_id,
                e,
            )
            try:
                IssueActivityDocument.bulk_create([edited_comment, edit_activity], action=BulkActionType.UPSERT)
            except Exception as e2:
                logger.error(
                    "IssueActivityDocument edit bulk_create retry failed, issue_id=%s, activity_id=%s: %s",
                    self.id,
                    activity_id,
                    e2,
                )

        # 拼接返回：新增的 COMMENT_EDIT 在最前，历史列表中那条原 COMMENT 用最新内容覆盖
        new_records = [
            {
                "bk_biz_id": edit_activity.bk_biz_id,
                "activity_id": edit_activity.id,
                "activity_type": edit_activity.activity_type,
                "operator": edit_activity.operator or "",
                "from_value": edit_activity.from_value,
                "to_value": edit_activity.to_value,
                "content": edit_activity.content,
                "time": edit_activity.time,
            },
        ]
        merged_existing = [
            {**act, "content": content} if act["activity_id"] == activity_id else act for act in existing_activities
        ]
        return new_records + merged_existing

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

    def rename(self, new_name: str, operator: str) -> list:
        """重命名 Issue"""
        new_name = new_name.strip()
        old_name = self.name
        # 内容未变化时直接返回当前活动列表，不写 ES
        if new_name == old_name:
            return self._read_activities()

        dup_search = (
            IssueDocument.search(all_indices=True)
            .filter("term", bk_biz_id=str(self.bk_biz_id))
            .filter("term", **{"name.raw": new_name})
            .exclude("term", **{"_id": self.id})
            .params(size=1)
        )
        if dup_search.execute().hits:
            raise IssueNameDuplicatedError(f"Issue name already exists, bk_biz_id={self.bk_biz_id}, name={new_name}")

        self.name = new_name
        self.update_time = int(time.time())
        self._persist_and_cache(active=self.status in IssueStatus.ACTIVE_STATUSES)
        return self._write_activities(
            [
                (IssueActivityType.NAME_CHANGE, old_name, new_name, operator, None),
            ]
        )

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
        """写回 Redis 热缓存（活跃 Issue）。

        防御性 guard：迁移函数已保证活跃 Issue 都有 fingerprint，但用户主动 reopen
        一个 fingerprint=null 的 legacy RESOLVED Issue 仍会走到这里。此时跳过缓存
        写入避免污染 "None" key；warning 日志暴露非预期路径。
        """
        if not self.fingerprint:
            logger.warning(
                "[issue] _update_redis_cache called on legacy issue without fingerprint, issue_id=%s",
                self.id,
            )
            return
        import json

        from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY

        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(fingerprint=self.fingerprint)
        ISSUE_ACTIVE_CONTENT_KEY.client.set(
            cache_key, json.dumps(self.to_cache_dict()), ex=ISSUE_ACTIVE_CONTENT_KEY.ttl
        )

    def _delete_redis_cache(self) -> None:
        """删除 Redis 热缓存（Issue 变为非活跃后）。

        防御性 guard 同 _update_redis_cache：legacy Issue 跳过删除（无对应 key）。
        """
        if not self.fingerprint:
            return
        from alarm_backends.core.cache.key import ISSUE_ACTIVE_CONTENT_KEY

        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(fingerprint=self.fingerprint)
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
        existing_activities = self._read_activities()

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
        except Exception as e:
            logger.warning("IssueActivityDocument bulk_create failed, retrying once, issue_id=%s: %s", self.id, e)
            try:
                IssueActivityDocument.bulk_create(new_activities)
            except Exception as e2:
                logger.error("IssueActivityDocument bulk_create retry failed, issue_id=%s: %s", self.id, e2)

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

    def _read_activities(self) -> list:
        """读取当前 Issue 全部活动日志（按时间降序）"""
        try:
            search = (
                IssueActivityDocument.search(all_indices=True)
                .filter("term", issue_id=self.id)
                .sort("-time")
                .extra(size=500)
            )
            hits = search.execute().hits
            return [
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
            logger.exception("Failed to read activities, issue_id=%s", self.id)
            return []


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


class IssueMigrationError(Exception):
    """Issue legacy migration 失败（mapping 未 ready / bulk_update 残留失败等）"""


def migrate_legacy_active_issues(batch_size: int = 500) -> int:
    """一次性迁移：把 fingerprint 缺失的活跃 Issue 全部 RESOLVE。

    fingerprint 改造从 1:1（strategy ↔ 活跃 Issue）升级为按维度组合切分。存量
    fingerprint=null 的活跃 Issue 在新模型下无法可靠归属，必须在新代码生效前强制关闭。

    设计要点：
    - **mapping guard**：先调 IssueDocument.rollover() / IssueActivityDocument.rollover()
      ensure mapping 已同步（rollover 失败 → raise，避免 mapping 缺失时
      `exclude exists fingerprint` 在 ES 7.x 行为未定义导致全表误删）
    - **two-pass scan**：先收集 issue_id + meta，再 bulk_update。避免 scroll 与并行
      bulk_update 的 segment 一致性问题，杜绝同一 Issue 重复写活动日志
    - **失败 raise**：bulk_create 异常时不静默吞，让 post_migrate hook 报错
    - **幂等**：仅扫描 fingerprint 不存在的 ACTIVE 文档，重跑 noop

    回滚兼容：旧代码按 strategy_id 查活跃，已 RESOLVED 的旧 Issue 不会被命中，无冲突。

    **本函数不直接 set legacy 迁移完成哨兵**：post_migrate hook 实际跑在 web/saas role
    下，该 role 的 settings 不含 ``REDIS_*_CONF``（仅 worker role 有），调用
    ``_mark_legacy_migration_done()`` 会触发 ``alarm_backends.core.storage.redis`` 在
    模块加载时解析 ``settings.REDIS_CELERY_CONF`` 而抛 AttributeError，导致 migrate
    命令以非 0 退出。哨兵改由 worker role 周期任务 ``sync_issue_alert_stats`` →
    ``_renew_legacy_migration_done_sentinel_if_needed`` 在探查到 legacy=0 时异步 set；
    哨兵未 set 期间 processor 仅多走 fallback ES 查询，不影响功能正确性，最大窗口
    = 一个周期任务 interval（默认 5min）。

    Returns: 本次迁移的 Issue 数量
    Raises: IssueMigrationError（mapping 未 ready / bulk 失败重试仍失败）
    """
    # Step 0: mapping guard —— 显式触发 rollover ensure mapping 已同步，rollover 是幂等的
    # 避免运行顺序：fta_web post_migrate hook 先调 rollover_es_indices，但万一失败被吞掉，
    # 此处再做一次保险 ensure；rollover 失败时 raise，阻断后续扫描，防止误删
    try:
        IssueDocument.rollover()
        IssueActivityDocument.rollover()
    except Exception as e:
        raise IssueMigrationError(f"[issue migration] rollover failed before scan, mapping may be stale: {e}") from e

    # Step 1: scan-only —— 收集 issue_id + meta，不修改任何文档
    legacy_meta: dict[str, dict] = {}
    search = (
        IssueDocument.search(all_indices=True)
        .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
        .exclude("exists", field="fingerprint")
        .params(size=batch_size)
    )
    for hit in search.scan():
        legacy_meta[hit.meta.id] = {
            "bk_biz_id": getattr(hit, "bk_biz_id", ""),
            "status": getattr(hit, "status", ""),
        }

    if not legacy_meta:
        # noop 路径：全系统当前已无 fingerprint=null 活跃 Issue。
        # 哨兵由 worker 周期任务 _renew_legacy_migration_done_sentinel_if_needed 异步 set；
        # 不在此处调用 _mark_legacy_migration_done()，避免 web/saas role 缺 REDIS_*_CONF 触发 AttributeError。
        return 0

    # Step 2: 分批 bulk_update + 写活动日志；任一批次失败 → 重试 1 次 → 仍失败 raise
    now = int(time.time())
    legacy_ids = list(legacy_meta.keys())
    total = 0
    for batch_start in range(0, len(legacy_ids), batch_size):
        batch_ids = legacy_ids[batch_start : batch_start + batch_size]
        update_docs = [
            IssueDocument(
                id=iid,
                status=IssueStatus.RESOLVED,
                resolved_time=now,
                update_time=now,
            )
            for iid in batch_ids
        ]
        activity_docs = [
            IssueActivityDocument(
                issue_id=iid,
                bk_biz_id=legacy_meta[iid]["bk_biz_id"],
                activity_type=IssueActivityType.STATUS_CHANGE,
                from_value=str(legacy_meta[iid]["status"]) if legacy_meta[iid]["status"] else "",
                to_value=IssueStatus.RESOLVED,
                operator="system",
                content="legacy_fingerprint_migration",
                time=now,
                create_time=now,
            )
            for iid in batch_ids
        ]
        _bulk_update_with_retry(update_docs, activity_docs, batch_start)
        total += len(batch_ids)

    logger.info("[issue migration] resolved %d legacy active issues (fingerprint=null)", total)

    # 哨兵由 worker 周期任务异步 set（见 docstring 与 _mark_legacy_migration_done 说明）；
    # 此处不直接调用，避免 web/saas role 缺 REDIS_*_CONF 触发模块加载期 AttributeError。
    return total


def _mark_legacy_migration_done() -> None:
    """设置全局哨兵 cache，processor 据此跳过 legacy fallback。

    Redis 故障时仅 warning，不阻塞迁移成功——processor fail-open 退化到走 legacy fallback。

    **仅供 worker role 调用**（如 ``_renew_legacy_migration_done_sentinel_if_needed``
    在周期任务 ``sync_issue_alert_stats`` 里调用）。
    ``alarm_backends.core.cache.key`` 在模块加载时 ``import RedisProxy`` 会触发
    ``alarm_backends.core.storage.redis`` 在模块加载时解析 ``settings.REDIS_CELERY_CONF``，
    web/saas role 的 settings 不含 ``REDIS_*_CONF``（仅 ``bkmonitor/config/role/worker.py``
    定义），此时调用会抛 AttributeError。``migrate_legacy_active_issues`` 因此不调用本函数；
    legacy=0 的初始 set 由 worker 周期任务异步接管。
    """
    from alarm_backends.core.cache.key import ISSUE_LEGACY_MIGRATION_DONE_KEY

    try:
        cache_key = ISSUE_LEGACY_MIGRATION_DONE_KEY.get_key()
        ISSUE_LEGACY_MIGRATION_DONE_KEY.client.set(cache_key, "1", ex=ISSUE_LEGACY_MIGRATION_DONE_KEY.ttl)
        logger.info("[issue migration] legacy migration done sentinel set, processor will skip legacy fallback")
    except Exception:
        logger.warning(
            "[issue migration] set legacy migration done sentinel failed; "
            "processor will keep doing legacy fallback queries (safe but extra ES load)",
            exc_info=True,
        )


def _bulk_update_with_retry(
    update_docs: list,
    activity_docs: list,
    batch_offset: int,
) -> None:
    """update_docs 与 activity_docs 解耦的重试包装。

    设计要点：
    - update_docs 走 UPSERT，幂等可安全 retry；retry 1 次仍失败 → raise IssueMigrationError
    - activity_docs 在 update 成功后**单独写**：失败仅 warning（不阻塞 migration 主成功）
    - 不在同一 try 中 retry update + activity，避免 retry 时 activity 的 doc id 已存在
      导致 BulkIndexError → migration 整批 raise 的伪失败
    - activity 缺失会让 STATUS_CHANGE 审计有空缺，但 Issue 已 RESOLVED 是事实，
      运维通过 metric / 日志可发现这种情况
    """
    last_exc: Exception | None = None
    update_succeeded = False
    for attempt in (1, 2):
        try:
            IssueDocument.bulk_create(update_docs, action=BulkActionType.UPSERT)
            update_succeeded = True
            break
        except Exception as e:
            last_exc = e
            logger.warning(
                "[issue migration] update bulk attempt %d failed (offset=%d, batch_size=%d): %s",
                attempt,
                batch_offset,
                len(update_docs),
                e,
            )

    if not update_succeeded:
        raise IssueMigrationError(
            f"[issue migration] update bulk failed permanently at offset={batch_offset} "
            f"(batch_size={len(update_docs)}): {last_exc}"
        ) from last_exc

    # update 成功后单独写 activity；失败 warning 但不 raise（迁移主成功优先）
    try:
        IssueActivityDocument.bulk_create(activity_docs)
    except Exception as e:
        logger.warning(
            "[issue migration] activity write failed (migration update already succeeded), offset=%d batch_size=%d: %s",
            batch_offset,
            len(activity_docs),
            e,
        )
