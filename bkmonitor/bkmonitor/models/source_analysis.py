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

from django.db import models
from django.utils import timezone

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.issue_id import generate_issue_style_id
from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.issue import SourceAnalysisStatus, SourceAnalysisTriggerType
from core.errors.issue import SourceAnalysisInvalidStatusTransitionError

logger = logging.getLogger(__name__)

__all__ = [
    "IssueSourceAnalysisConfig",
    "IssueSourceAnalysisExecution",
    "IssueSourceAnalysisRule",
]


class IssueSourceAnalysisConfig(AbstractRecordModel):
    """业务级源码分析代码库配置。"""

    class Meta:
        db_table = "bkmonitor_issue_source_analysis_config"
        verbose_name = "Issue 源码分析配置"

    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField(unique=True, verbose_name="业务 ID")
    bkci_project_id = models.CharField(max_length=128, verbose_name="蓝盾项目 ID")
    repository_alias = models.CharField(max_length=255, verbose_name="蓝盾代码库别名")


class IssueSourceAnalysisRule(AbstractRecordModel):
    """业务级源码分析规则及每次执行所需的资源参数。"""

    class Meta:
        db_table = "bkmonitor_issue_source_analysis_rule"
        verbose_name = "Issue 源码分析规则"
        ordering = ["-priority", "id"]
        indexes = [
            models.Index(
                fields=["bk_biz_id", "is_deleted", "is_enabled", "priority"],
                name="idx_isar_biz_enabled_pri",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bk_biz_id", "priority"],
                name="uniq_issue_src_rule_priority",
            ),
            # 自定义规则按优先级从高到低匹配，-1 固定留给最后兜底的默认规则。
            models.CheckConstraint(
                check=(models.Q(is_default=True, priority=-1) | models.Q(is_default=False, priority__gte=0)),
                name="ck_issue_src_rule_priority",
            ),
        ]

    id = models.BigAutoField(primary_key=True)
    bk_biz_id = models.IntegerField(db_index=True, verbose_name="业务 ID")
    priority = models.IntegerField(verbose_name="优先级")
    is_enabled = models.BooleanField(default=False, verbose_name="是否启用")
    is_default = models.BooleanField(default=False, verbose_name="是否默认规则")
    # 条件项沿用告警分派结构：
    # {"field": str, "value": list[str], "method": str, "condition": str}
    # method 取 eq/neq/include/exclude/reg/nreg/issuperset；condition 取 and/or/""，最后一项固定为 ""。
    conditions = JsonField(default=list, blank=True, verbose_name="匹配条件")
    bkci_project_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        default=None,
        verbose_name="蓝盾项目 ID 快照",
    )
    repository_alias = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default=None,
        verbose_name="蓝盾代码库别名快照",
    )
    # 一条规则只驱动一个智能体，Skill 与知识库则是挂在该智能体上的多值输入
    agent_id = models.CharField(max_length=64, default="", blank=True, verbose_name="智能体 ID")
    skill_ids = JsonField(default=list, blank=True, verbose_name="Skill ID")
    knowledge_base_ids = JsonField(default=list, blank=True, verbose_name="知识库 ID")


class IssueSourceAnalysisExecution(AbstractRecordModel):
    """单次源码分析的执行记录、状态机与输入快照。

    Issue 本体存放在 ES，这里只按字符串关联 issue_id，与 IssueMergeRelation、IssueTapdRelation 保持一致。
    执行链路以 analysis_id -> bkfara_task_id 标识，analysis_id 同时是 BKM 到 BKFara 的任务幂等键。

    status、stage、trigger_type、failure_stage、result_type 的取值分别由 constants.issue 下的同名常量类定义。
    这些字段刻意不声明 choices：状态流转统一走条件更新，choices 在此不产生任何校验，
    反而会把带翻译的展示文案冻结进迁移，导致非中文 locale 下生成无关的 AlterField。
    """

    class Meta:
        db_table = "bkmonitor_issue_source_analysis_execution"
        verbose_name = "Issue 源码分析执行记录"
        ordering = ["-id"]
        indexes = [
            # 页面只展示最新一次执行，取数固定按业务 + Issue 倒序
            models.Index(fields=["bk_biz_id", "issue_id", "-id"], name="idx_isae_biz_issue"),
            # 超时恢复按活动态全表扫描
            models.Index(fields=["status"], name="idx_isae_status"),
        ]
        constraints = [
            # active_key 在活动态写入 issue_id、进入终态置空。
            # MySQL 唯一索引不约束 NULL，据此在库层保证同一 Issue 同时最多一条 pending/running 记录。
            models.UniqueConstraint(
                fields=["bk_biz_id", "active_key"],
                name="uniq_issue_src_exec_active",
            ),
        ]

    # 主状态允许的迁移方向；成功和失败都是终态，本期没有取消能力
    STATUS_TRANSITIONS = {
        SourceAnalysisStatus.PENDING: (SourceAnalysisStatus.RUNNING, SourceAnalysisStatus.FAILED),
        SourceAnalysisStatus.RUNNING: (
            SourceAnalysisStatus.RUNNING,
            SourceAnalysisStatus.SUCCESS,
            SourceAnalysisStatus.FAILED,
        ),
        SourceAnalysisStatus.SUCCESS: (),
        SourceAnalysisStatus.FAILED: (),
    }

    id = models.BigAutoField(primary_key=True)
    # 与 IssueDocument.id 同款形态，可按 ID 前缀还原发起时间
    analysis_id = models.CharField(
        max_length=64,
        unique=True,
        default=generate_issue_style_id,
        verbose_name="分析记录 ID",
    )
    bk_biz_id = models.IntegerField(db_index=True, verbose_name="业务 ID")
    issue_id = models.CharField(max_length=64, verbose_name="Issue ID")
    # 由 status 派生，不接受调用方直接赋值，取值规则见 _resolve_active_key
    active_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="活动记录标识",
    )

    status = models.CharField(
        max_length=32,
        default=SourceAnalysisStatus.PENDING,
        verbose_name="主状态",
    )
    stage = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        default=None,
        verbose_name="执行阶段",
    )
    trigger_type = models.CharField(
        max_length=16,
        default=SourceAnalysisTriggerType.INITIAL,
        verbose_name="触发方式",
    )
    attempt = models.IntegerField(default=1, verbose_name="尝试次数")
    retry_of_analysis_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        default=None,
        verbose_name="被重试的分析记录 ID",
    )

    # 触发时固化的输入，后续规则或配置变更都不影响已创建的执行记录
    alert_id = models.CharField(max_length=64, verbose_name="告警 ID")
    # 规则可能在执行期间被删除，只留 ID 作追溯线索，不建外键
    rule_id = models.BigIntegerField(null=True, blank=True, default=None, verbose_name="命中规则 ID")
    rule_priority = models.IntegerField(null=True, blank=True, default=None, verbose_name="命中规则优先级快照")
    bkci_project_id = models.CharField(max_length=128, verbose_name="蓝盾项目 ID 快照")
    repository_alias = models.CharField(max_length=255, verbose_name="蓝盾代码库别名快照")
    # 发起分析要求规则完整，此处必有值
    agent_id = models.CharField(max_length=64, verbose_name="智能体 ID 快照")
    skill_ids = JsonField(default=list, blank=True, verbose_name="Skill ID 快照")
    knowledge_base_ids = JsonField(default=list, blank=True, verbose_name="知识库 ID 快照")

    # 拿到 task_id 后不得重复创建 BKFara 任务，只能查询并恢复
    bkfara_task_id = models.CharField(
        max_length=128, null=True, blank=True, default=None, verbose_name="BKFara 任务 ID"
    )
    failure_stage = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        default=None,
        verbose_name="失败阶段",
    )
    failure_code = models.CharField(max_length=64, null=True, blank=True, default=None, verbose_name="失败错误码")
    failure_message = models.TextField(default="", blank=True, verbose_name="失败提示")
    failure_retryable = models.BooleanField(null=True, default=None, verbose_name="是否可重试")
    failure_request_id = models.CharField(
        max_length=64, null=True, blank=True, default=None, verbose_name="失败请求 ID"
    )

    result_type = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        default=None,
        verbose_name="结论类型",
    )
    result_schema_version = models.CharField(
        max_length=16, null=True, blank=True, default=None, verbose_name="结果 Schema 版本"
    )
    # 已通过 Schema 校验的结果协议，包含结论卡片与 Markdown 正文
    result_payload = JsonField(null=True, blank=True, default=None, verbose_name="分析结果")

    started_at = models.DateTimeField(null=True, blank=True, default=None, verbose_name="开始执行时间")
    finished_at = models.DateTimeField(null=True, blank=True, default=None, verbose_name="终态时间")

    def _resolve_active_key(self, status: str) -> str | None:
        """活动位由状态派生：活动态占位、终态让位。唯一约束的正确性依赖这一处规则。"""

        return self.issue_id if status in SourceAnalysisStatus.ACTIVE_STATUSES else None

    def save(self, *args, **kwargs):
        """写库前统一回填活动位，调用方不需要也不应该自己维护 active_key。"""

        self.active_key = self._resolve_active_key(self.status)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "active_key" not in update_fields:
            kwargs["update_fields"] = [*update_fields, "active_key"]
        return super().save(*args, **kwargs)

    def delete(self, hard: bool = False, *args, **kwargs):
        """软删除同样要让出活动位，否则该 Issue 会被一条应用层已不可见的记录长期挡住。"""

        result = super().delete(hard, *args, **kwargs)
        if not hard:
            type(self).origin_objects.filter(pk=self.pk).update(active_key=None)
            self.active_key = None
        return result

    def mark_running(self, stage: str) -> None:
        """推进到执行中。允许 running -> running，用于活动期间只更新阶段。"""

        updates = {"stage": stage}
        if self.started_at is None:
            updates["started_at"] = timezone.now()
        self._transition(SourceAnalysisStatus.RUNNING, **updates)

    def mark_success(self, result_type: str, result_payload: dict, result_schema_version: str) -> None:
        """推进到成功终态。证据不足同样是成功，由 result_type 区分。"""

        self._transition(
            SourceAnalysisStatus.SUCCESS,
            stage=None,
            result_type=result_type,
            result_payload=result_payload,
            result_schema_version=result_schema_version,
            finished_at=timezone.now(),
        )

    def mark_failed(
        self,
        failure_stage: str,
        failure_code: str,
        failure_message: str,
        failure_retryable: bool,
        failure_request_id: str | None = None,
    ) -> None:
        """推进到失败终态。具体失败位置记在 failure_stage，不扩充主状态。"""

        self._transition(
            SourceAnalysisStatus.FAILED,
            stage=None,
            failure_stage=failure_stage,
            failure_code=failure_code,
            failure_message=failure_message,
            failure_retryable=failure_retryable,
            failure_request_id=failure_request_id,
            finished_at=timezone.now(),
        )

    def _transition(self, target_status: str, **updates) -> None:
        """按当前库内状态做条件更新，避免并发下两个调用方同时改写同一条记录。"""

        allowed_from = [source for source, targets in self.STATUS_TRANSITIONS.items() if target_status in targets]
        updates.update(
            status=target_status,
            active_key=self._resolve_active_key(target_status),
            update_time=timezone.now(),
        )
        updated_rows = type(self).objects.filter(pk=self.pk, status__in=allowed_from).update(**updates)
        if not updated_rows:
            logger.warning(
                "Illegal source analysis transition, analysis_id=%s, %s -> %s",
                self.analysis_id,
                self.status,
                target_status,
            )
            raise SourceAnalysisInvalidStatusTransitionError()

        for field, value in updates.items():
            setattr(self, field, value)
