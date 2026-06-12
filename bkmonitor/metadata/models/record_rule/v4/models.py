"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone
from pypinyin import lazy_pinyin

from bkm_space.utils import space_uid_to_bk_biz_id
from metadata.models.common import BaseModelWithTime
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_BKBASE_NAMESPACE,
    RECORD_RULE_V4_BKMONITOR_NAMESPACE,
    RECORD_RULE_V4_DEFAULT_TENANT,
    RECORD_RULE_V4_DEFAULT_REFRESH_INTERVAL,
    RECORD_RULE_V4_INTERVAL_CHOICES,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
    RecordRuleV4InputType,
    RecordRuleV4Status,
)
from metadata.models.space.constants import SpaceTypes

if TYPE_CHECKING:
    from metadata.models.record_rule.v4.source import ResolvedVmResultTableConfig

logger = logging.getLogger("metadata")


CONDITION_TRUE = "True"
CONDITION_FALSE = "False"
CONDITION_UNKNOWN = "Unknown"

CONDITION_RECONCILED = "Reconciled"
CONDITION_RESOLVED = "Resolved"
CONDITION_FLOW_READY = "FlowReady"
CONDITION_FLOW_HEALTHY = "FlowHealthy"

EVENT_STATUS_STARTED = "started"
EVENT_STATUS_SUCCEEDED = "succeeded"
EVENT_STATUS_FAILED = "failed"
EVENT_STATUS_SKIPPED = "skipped"

EVENT_TYPE_USER_CREATE = "user.create"
EVENT_TYPE_USER_SPEC_CHANGED = "user.spec_changed"
EVENT_TYPE_USER_METADATA_CHANGED = "user.metadata_changed"
EVENT_TYPE_USER_AUTO_REFRESH_CHANGED = "user.auto_refresh_changed"
EVENT_TYPE_USER_DESIRED_STATUS_CHANGED = "user.desired_status_changed"
EVENT_TYPE_OPERATION_SKIPPED = "operation.skipped"
EVENT_TYPE_RESOLVE_CHANGED = "resolve.changed"
EVENT_TYPE_RESOLVE_UNCHANGED = "resolve.unchanged"
EVENT_TYPE_RESOLVE_FAILED = "resolve.failed"
EVENT_TYPE_APPLY_STARTED = "apply.started"
EVENT_TYPE_APPLY_SUCCEEDED = "apply.succeeded"
EVENT_TYPE_APPLY_FAILED = "apply.failed"
EVENT_TYPE_APPLY_SKIPPED = "apply.skipped"
EVENT_TYPE_FLOW_ACTION_STARTED = "flow_action.started"
EVENT_TYPE_FLOW_ACTION_SUCCEEDED = "flow_action.succeeded"
EVENT_TYPE_FLOW_ACTION_FAILED = "flow_action.failed"
EVENT_TYPE_FLOW_OBSERVED = "flow.observed"

EVENT_REASON_OPERATION_LOCKED = "OperationLocked"
EVENT_REASON_STALE_FLOW = "StaleFlow"
EVENT_REASON_SPEC_MISSING = "SpecMissing"
EVENT_REASON_RESOLVE_FAILED = "ResolveFailed"
EVENT_REASON_FLOW_MISSING = "FlowMissing"
EVENT_REASON_APPLY_FAILED = "ApplyFailed"

FLOW_TYPE_RECORD_RULE = "recording-rule"
FLOW_METADATA_ANNOTATION_PREFIX = "record-rule.bkmonitor"

EVENT_RELATION_REQUIRED = "required"
EVENT_RELATION_OPTIONAL = "optional"
EVENT_RELATION_FORBIDDEN = "forbidden"

EVENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    EVENT_TYPE_USER_CREATE: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_USER_SPEC_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"changed_fields"},
    },
    EVENT_TYPE_USER_METADATA_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"changed_fields"},
    },
    EVENT_TYPE_USER_AUTO_REFRESH_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"auto_refresh"},
    },
    EVENT_TYPE_USER_DESIRED_STATUS_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"desired_status"},
    },
    EVENT_TYPE_OPERATION_SKIPPED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {EVENT_REASON_OPERATION_LOCKED},
        "detail_keys": {"owner", "reason", "expires_at", "operation"},
    },
    EVENT_TYPE_RESOLVE_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_RESOLVE_UNCHANGED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_RESOLVE_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {EVENT_REASON_SPEC_MISSING, EVENT_REASON_RESOLVE_FAILED},
    },
    EVENT_TYPE_APPLY_STARTED: {
        "statuses": {EVENT_STATUS_STARTED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {""},
        "detail_keys": set(),
    },
    EVENT_TYPE_APPLY_SUCCEEDED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {""},
        "detail_keys": set(),
    },
    EVENT_TYPE_APPLY_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {EVENT_REASON_FLOW_MISSING, EVENT_REASON_APPLY_FAILED, EVENT_REASON_STALE_FLOW},
        "detail_keys": set(),
    },
    EVENT_TYPE_APPLY_SKIPPED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {EVENT_REASON_STALE_FLOW},
        "detail_keys": {"flow_id", "latest_resolved_id", "current_generation", "flow_generation"},
    },
    EVENT_TYPE_FLOW_ACTION_STARTED: {
        "statuses": {EVENT_STATUS_STARTED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {""},
        "detail_keys": {"action_type", "flow_id", "flow_name", "flow_content_hash"},
    },
    EVENT_TYPE_FLOW_ACTION_SUCCEEDED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {""},
        "detail_keys": {"action_type", "flow_id", "flow_name", "flow_content_hash"},
    },
    EVENT_TYPE_FLOW_ACTION_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {EVENT_REASON_APPLY_FAILED},
        "detail_keys": {"action_type", "flow_id", "flow_name", "flow_content_hash"},
    },
    EVENT_TYPE_FLOW_OBSERVED: {
        "statuses": {EVENT_STATUS_SUCCEEDED, EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {
            RecordRuleV4FlowStatus.OK.value,
            RecordRuleV4FlowStatus.ABNORMAL.value,
            RecordRuleV4FlowStatus.NOT_FOUND.value,
        },
    },
}

DEFAULT_OPERATION_LOCK_TTL_SECONDS = 300
RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH = 8
RECORD_RULE_V4_MAX_GENERATED_NAME_LENGTH = 50
RECORD_RULE_V4_TABLE_ID_SUFFIX = ".__default__"
SPEC_RECORD_KEY_PREFIX = "rr"


def stable_hash(payload: Any) -> str:
    """生成稳定内容指纹，用于判断 spec / resolved 语义快照是否真的变化。"""

    data = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def normalize_labels(labels: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """归一化 labels，保持对 bkbase recording rule 所需的 list[dict] 结构。"""

    result: list[dict[str, Any]] = []
    for label in labels or []:
        if not isinstance(label, dict):
            raise ValueError("label item must be dict")
        if label:
            result.append(dict(label))
    return result


def merge_labels(group_labels: list[dict[str, Any]], record_labels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """合并 group / record 两层 labels，record 级同名 key 覆盖 group 级。"""

    merged: dict[str, Any] = {}
    for label in [*normalize_labels(group_labels), *normalize_labels(record_labels)]:
        for key, value in label.items():
            merged[str(key)] = value
    return [{key: value} for key, value in merged.items()]


def now() -> datetime:
    """统一封装当前时间，方便模型方法和测试保持同一入口。"""

    return timezone.now()


def generate_record_key() -> str:
    """生成组内 record 的内部稳定 ID。"""

    return f"{SPEC_RECORD_KEY_PREFIX}_{uuid4().hex[:12]}"


def _safe_name_hint(value: str, max_length: int, fallback: str = "group") -> str:
    """把任意用户名称转换成可用于 table / flow name 的弱提示片段。

    group name 是用户可自由输入的展示名，不能反向约束资源创建。这里尽量把
    中文转换成拼音、把其他非法字符折成下划线；如果最终不可用，则退回到
    fallback，保证任何输入都不会让名称生成失败。
    """

    raw = str(value or "").strip().lower()
    if not raw:
        return fallback[:max_length] or fallback

    chars: list[str] = []
    for char in raw:
        if "\u4e00" <= char <= "\u9fff":
            chars.extend(lazy_pinyin(char))
        else:
            chars.append(char)
    hint = "".join(chars)
    hint = re.sub(r"[^a-z0-9_]+", "_", hint)
    hint = re.sub(r"_+", "_", hint).strip("_")
    if not hint:
        hint = fallback
    return hint[:max_length].strip("_") or fallback[:max_length] or fallback


def _extract_random_suffix_from_table(table_id: str) -> str:
    """从已生成 table_id 中取出随机段，用于关联 group 级 Flow 名称。"""

    name = table_id.split(".", 1)[0]
    suffix = name.rsplit("_", 1)[-1]
    return suffix[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH] or uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH]


class RecordRuleV4(BaseModelWithTime):
    """V4 Recording Rule group 声明。

    主对象只代表用户眼中的一组预计算配置。用户输入、实时解析结果、最终部署计划分别拆到
    Spec / Resolved / Flow；因此 flow 模板变化不会直接影响 group 是否可更新。
    """

    if TYPE_CHECKING:
        current_spec: RecordRuleV4Spec | None
        current_spec_id: int | None
        applied_resolved: RecordRuleV4Resolved | None
        applied_resolved_id: int | None
        specs: models.QuerySet[RecordRuleV4Spec]
        resolved: models.QuerySet[RecordRuleV4Resolved]
        flows: models.QuerySet[RecordRuleV4Flow]
        events: models.QuerySet[RecordRuleV4Event]

    space_type = models.CharField("空间类型", max_length=64)
    space_id = models.CharField("空间ID", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    name = models.CharField("预计算组名称", max_length=128)
    description = models.TextField("描述", blank=True, default="")
    data_label = models.CharField("数据标签", max_length=128, blank=True, default="")
    flow_name = models.CharField("V4 Flow 名称", max_length=128)
    table_id = models.CharField("结果表名", max_length=128)
    dst_vm_table_id = models.CharField("VM 结果表RT", max_length=128)
    dst_vm_storage_name = models.CharField("目标 VM 存储名称", max_length=128, blank=True, default="")

    generation = models.IntegerField("用户声明版本", default=0)
    current_spec = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        "RecordRuleV4Spec",
        verbose_name="当前用户声明快照",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    applied_resolved = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        "RecordRuleV4Resolved",
        verbose_name="最近成功生效的解析快照",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    desired_status = models.CharField("期望状态", max_length=32, default=RecordRuleV4DesiredStatus.RUNNING.value)
    applied_desired_status = models.CharField(
        "最近成功生效的期望状态", max_length=32, default=RecordRuleV4DesiredStatus.RUNNING.value
    )
    status = models.CharField("聚合阶段", max_length=32, default=RecordRuleV4Status.CREATED.value)
    conditions = models.JSONField("当前状态条件", default=dict)

    auto_refresh = models.BooleanField("是否自动刷新", default=True)
    last_check_time = models.DateTimeField("最近检查时间", null=True, blank=True)
    last_refresh_time = models.DateTimeField("最近刷新时间", null=True, blank=True)
    deleted_at = models.DateTimeField("删除完成时间", null=True, blank=True)

    operation_lock_token = models.CharField("操作锁 Token", max_length=64, blank=True, default="")
    operation_lock_owner = models.CharField("操作锁持有者", max_length=128, blank=True, default="")
    operation_lock_reason = models.CharField("操作锁原因", max_length=64, blank=True, default="")
    operation_lock_expires_at = models.DateTimeField("操作锁过期时间", null=True, blank=True)

    class Meta:
        verbose_name = "V4 预计算规则组"
        verbose_name_plural = "V4 预计算规则组"
        unique_together = (("bk_tenant_id", "table_id"), ("bk_tenant_id", "dst_vm_table_id"))
        indexes = [
            models.Index(fields=["space_type", "space_id", "bk_tenant_id", "deleted_at"], name="rrv4_space_del_idx"),
            models.Index(fields=["desired_status", "last_check_time"], name="rrv4_refresh_idx"),
        ]

    @property
    def space_uid(self) -> str:
        return f"{self.space_type}__{self.space_id}"

    @property
    def bk_biz_id(self) -> int:
        return self.resolve_bk_biz_id(self.space_type, self.space_id)

    @staticmethod
    def resolve_bk_biz_id(space_type: str, space_id: str) -> int:
        """根据空间信息解析权限和 DataLink 侧使用的业务 ID。"""

        if space_type == SpaceTypes.BKCC.value:
            return int(space_id)
        return space_uid_to_bk_biz_id(f"{space_type}__{space_id}")

    @classmethod
    def compose_name_base(cls, pk: int, name: str, random_suffix: str | None = None, max_length: int = 50) -> str:
        """生成 table / flow 共用的稳定基础名称。

        生成后会保存到主表，不随用户展示名变化重算。`pk` 放在固定前缀里，
        随机段用于进一步避免同名和并发场景下的碰撞。
        """

        suffix = (random_suffix or uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH])[
            :RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH
        ]
        prefix = f"bkm_rr_{pk}"
        reserved = len(prefix) + len(suffix) + 2
        hint_length = max(1, max_length - reserved)
        hint = _safe_name_hint(name, hint_length, "group")
        return f"{prefix}_{hint}_{suffix}"[:max_length].rstrip("_")

    @classmethod
    def compose_table_id(cls, pk: int, name: str, random_suffix: str | None = None) -> str:
        """生成 group 级输出结果表，`.__default__` 不计入 50 字符基础名约束。"""

        base_name = cls.compose_name_base(pk=pk, name=name, random_suffix=random_suffix)
        return f"{base_name}{RECORD_RULE_V4_TABLE_ID_SUFFIX}"

    @classmethod
    def compose_flow_name(cls, pk: int, name: str, random_suffix: str | None = None, max_length: int = 50) -> str:
        """生成目标 Flow 名称，与 table_id 基础名保持同一规则。"""

        return cls.compose_name_base(pk=pk, name=name, random_suffix=random_suffix, max_length=max_length)

    @classmethod
    def compose_group_flow_name(cls, pk: int, name: str, table_id: str) -> str:
        """根据已生成的 table_id 派生稳定 Flow 名称。

        table_id 在 group 创建时已经带随机段；Flow 名称复用这个随机段，
        因此同一个 group 后续更新 spec / resolved 时不会改名。
        """

        return cls.compose_flow_name(
            pk=pk,
            name=name,
            random_suffix=_extract_random_suffix_from_table(table_id),
        )

    def get_latest_resolved(self) -> RecordRuleV4Resolved | None:
        """返回当前 spec 最近一次解析结果。

        latest resolved 属于 spec 维度的解析状态，不再冗余刷新到 group 主表。
        group 主表只保存 applied_resolved，用于表达“哪份配置已生效”。
        """

        current_spec = self.current_spec
        if current_spec is None:
            return None
        return current_spec.latest_resolved

    @property
    def is_resolve_pending(self) -> bool:
        """当前 spec 尚未产生 latest resolved 时，配置仍处于解析等待态。"""

        current_spec = self.current_spec
        return bool(current_spec and current_spec.latest_resolved_id is None)

    def get_latest_flow(self) -> RecordRuleV4Flow | None:
        """返回当前 spec latest resolved 对应的目标 Flow 快照。"""

        latest_resolved = self.get_latest_resolved()
        if not latest_resolved:
            return None
        try:
            return latest_resolved.flow
        except RecordRuleV4Flow.DoesNotExist:
            return None

    def get_applied_flow(self) -> RecordRuleV4Flow | None:
        """返回当前已生效 resolved 对应的 Flow 快照。"""

        applied_resolved = self.applied_resolved
        if applied_resolved is None:
            return None
        try:
            return applied_resolved.flow
        except RecordRuleV4Flow.DoesNotExist:
            return None

    def get_condition(self, condition_type: str) -> dict[str, Any]:
        """按 condition type 获取当前状态。

        conditions 是按 type 覆盖的当前态，不保存历史；历史过程统一记录在
        RecordRuleV4Event。
        """

        return dict((self.conditions or {}).get(condition_type) or {})

    def set_condition(
        self,
        condition_type: str,
        status: str,
        reason: str = "",
        message: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        """按 condition type 覆盖当前状态。"""

        conditions = dict(self.conditions or {})
        conditions[condition_type] = {
            "type": condition_type,
            "status": status,
            "reason": reason,
            "message": message,
            "generation": self.generation,
            "last_transition_time": now().isoformat(),
            "detail": detail or {},
        }
        self.conditions = conditions

    def sync_phase(self) -> None:
        """根据声明态、观测态和 conditions 推导用户可见的聚合状态。"""

        if self.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            self.status = RecordRuleV4Status.DELETED.value if self.deleted_at else RecordRuleV4Status.DELETING.value
            return

        # 任何关键 condition 失败都优先展示 failed，避免被 pending/running 掩盖。
        if any(
            self.get_condition(condition_type).get("status") == CONDITION_FALSE
            and self.get_condition(condition_type).get("generation") == self.generation
            for condition_type in [
                CONDITION_RECONCILED,
                CONDITION_RESOLVED,
                CONDITION_FLOW_READY,
                CONDITION_FLOW_HEALTHY,
            ]
        ):
            self.status = RecordRuleV4Status.FAILED.value
            return

        # spec 已切换但还没有解析结果时，用户看到的是“正在等待解析/下发”。
        if self.is_resolve_pending:
            self.status = RecordRuleV4Status.PENDING.value
            return

        # resolved 漂移但未下发时，用 auto_refresh 区分“待自动执行”和“需要人工更新”。
        latest_resolved = self.get_latest_resolved()
        if latest_resolved and latest_resolved.pk != self.applied_resolved_id:
            self.status = RecordRuleV4Status.PENDING.value if self.auto_refresh else RecordRuleV4Status.OUTDATED.value
            return

        # 启停不推进 generation；单独比较 desired/applied desired 表达运行态是否已经生效。
        if self.desired_status != self.applied_desired_status:
            self.status = RecordRuleV4Status.PENDING.value
            return

        if self.desired_status == RecordRuleV4DesiredStatus.STOPPED.value:
            self.status = RecordRuleV4Status.STOPPED.value
            return

        self.status = RecordRuleV4Status.RUNNING.value

    def use_spec(self, spec: RecordRuleV4Spec) -> None:
        """切换当前用户声明快照并推进 generation。"""

        self.current_spec = spec
        self.generation = spec.generation
        self.set_condition(CONDITION_RESOLVED, CONDITION_UNKNOWN, "Pending", "waiting for resolve")
        self.set_condition(CONDITION_FLOW_READY, CONDITION_UNKNOWN, "Pending", "waiting for flow preparation")
        self.set_condition(CONDITION_RECONCILED, CONDITION_UNKNOWN, "Pending", "waiting for apply")
        self.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_UNKNOWN, "Pending", "waiting for observation")
        self.sync_phase()
        self.save(
            update_fields=[
                "current_spec",
                "generation",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def use_resolved(self, resolved: RecordRuleV4Resolved) -> None:
        """把解析结果挂到其 spec，并据此更新 group 的可更新状态。"""

        resolved.spec.latest_resolved = resolved
        resolved.spec.save(update_fields=["latest_resolved", "updated_at"])
        if self.current_spec_id == resolved.spec_id and self.current_spec:
            self.current_spec.latest_resolved = resolved
            self.current_spec.latest_resolved_id = resolved.pk
        self.last_check_time = now()
        self.set_condition(CONDITION_RESOLVED, CONDITION_TRUE, "Changed")
        self.sync_phase()
        self.save(
            update_fields=[
                "last_check_time",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def mark_flow_ready(self, flow: RecordRuleV4Flow) -> None:
        """标记当前 latest resolved 已经生成目标 Flow。

        Flow 不是 group 主表事实源；这里仅更新 condition，方便用户知道
        resolved 已经具备可下发的目标配置。
        """

        self.set_condition(CONDITION_FLOW_READY, CONDITION_TRUE, "Prepared")
        self.sync_phase()
        self.save(update_fields=["conditions", "status", "updated_at"])

    def set_desired_status(self, desired_status: str) -> None:
        """更新 group 运行态期望状态。

        running/stopped/deleted 都不生成 spec；配置定义和运行状态保持隔离。
        """

        self.validate_desired_status(desired_status)
        self.desired_status = desired_status
        if desired_status != RecordRuleV4DesiredStatus.DELETED.value:
            self.deleted_at = None
        self.sync_phase()
        self.save(update_fields=["desired_status", "deleted_at", "status", "updated_at"])

    def mark_flow_applied(self, flow: RecordRuleV4Flow) -> None:
        """标记目标 Flow 对应的 resolved 和运行态都已成功生效。"""

        self.applied_resolved = flow.resolved
        self.applied_desired_status = self.desired_status
        self.last_refresh_time = now()
        self.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "ApplySucceeded")
        self.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_UNKNOWN, "ApplySubmitted")
        self.sync_phase()
        self.save(
            update_fields=[
                "applied_resolved",
                "applied_desired_status",
                "last_refresh_time",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def mark_delete_applied(self) -> None:
        """标记外部 Flow 已删除，并清空当前生效配置。"""

        self.applied_resolved = None
        self.applied_desired_status = RecordRuleV4DesiredStatus.DELETED.value
        self.deleted_at = now()
        self.last_refresh_time = now()
        self.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "DeleteSucceeded")
        self.sync_phase()
        self.save(
            update_fields=[
                "applied_resolved",
                "applied_desired_status",
                "deleted_at",
                "last_refresh_time",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def mark_desired_status_applied(self, desired_status: str) -> None:
        """标记 running/stopped 运行态已经成功下发。"""

        self.applied_desired_status = desired_status
        self.last_refresh_time = now()
        self.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "DesiredStatusApplied")
        self.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_UNKNOWN, "ApplySubmitted")
        self.sync_phase()
        self.save(
            update_fields=[
                "applied_desired_status",
                "last_refresh_time",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def acquire_operation_lock(
        self, owner: str, reason: str, ttl_seconds: int = DEFAULT_OPERATION_LOCK_TTL_SECONDS
    ) -> str:
        """获取数据库级轻量操作锁。

        这里使用条件 update 做原子抢锁，避免后台 reconcile 和用户 apply
        同时下发同一个 group。
        """

        locked_until = now() + timedelta(seconds=ttl_seconds)
        token = uuid4().hex
        updated = (
            RecordRuleV4.objects.filter(pk=self.pk)
            .filter(
                models.Q(operation_lock_token="")
                | models.Q(operation_lock_expires_at__isnull=True)
                | models.Q(operation_lock_expires_at__lte=now())
            )
            .update(
                operation_lock_token=token,
                operation_lock_owner=owner,
                operation_lock_reason=reason,
                operation_lock_expires_at=locked_until,
                updated_at=now(),
            )
        )
        if updated:
            self.operation_lock_token = token
            self.operation_lock_owner = owner
            self.operation_lock_reason = reason
            self.operation_lock_expires_at = locked_until
            return token
        return ""

    def release_operation_lock(self, token: str) -> bool:
        """按 token 释放操作锁，避免误释放其他执行方持有的锁。"""

        updated = RecordRuleV4.objects.filter(pk=self.pk, operation_lock_token=token).update(
            operation_lock_token="",
            operation_lock_owner="",
            operation_lock_reason="",
            operation_lock_expires_at=None,
            updated_at=now(),
        )
        if updated:
            self.operation_lock_token = ""
            self.operation_lock_owner = ""
            self.operation_lock_reason = ""
            self.operation_lock_expires_at = None
        return bool(updated)

    def should_refresh(self, refresh_interval: int = RECORD_RULE_V4_DEFAULT_REFRESH_INTERVAL) -> bool:
        """判断当前 group 是否到达统一的定时检查周期。"""

        if not self.last_check_time:
            return True
        check_before = now() - timedelta(seconds=refresh_interval)
        return self.last_check_time <= check_before

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.pk,
            "bk_tenant_id": self.bk_tenant_id,
            "bk_biz_id": self.bk_biz_id,
            "space_uid": self.space_uid,
            "space_type": self.space_type,
            "space_id": self.space_id,
            "name": self.name,
            "description": self.description,
            "data_label": self.data_label,
            "flow_name": self.flow_name,
            "table_id": self.table_id,
            "dst_vm_table_id": self.dst_vm_table_id,
            "dst_vm_storage_name": self.dst_vm_storage_name,
            "generation": self.generation,
            "current_spec_id": self.current_spec_id,
            "latest_resolved_id": self.current_spec.latest_resolved_id if self.current_spec else None,
            "applied_resolved_id": self.applied_resolved_id,
            "desired_status": self.desired_status,
            "applied_desired_status": self.applied_desired_status,
            "status": self.status,
            "conditions": self.conditions,
            "auto_refresh": self.auto_refresh,
        }

    @staticmethod
    def validate_input_type(input_type: str) -> None:
        if input_type not in {item.value for item in RecordRuleV4InputType}:
            raise ValueError(f"unsupported input_type: {input_type}")

    @staticmethod
    def validate_interval(interval: str) -> None:
        if interval not in RECORD_RULE_V4_INTERVAL_CHOICES:
            raise ValueError(f"unsupported interval: {interval}")

    @staticmethod
    def validate_desired_status(desired_status: str) -> None:
        if desired_status not in {item.value for item in RecordRuleV4DesiredStatus}:
            raise ValueError(f"unsupported desired_status: {desired_status}")


class RecordRuleV4Spec(BaseModelWithTime):
    """用户提交的 group 原始配置快照。"""

    if TYPE_CHECKING:
        rule_id: int
        latest_resolved: RecordRuleV4Resolved | None
        latest_resolved_id: int | None
        records: models.QuerySet[RecordRuleV4SpecRecord]
        resolved: models.QuerySet[RecordRuleV4Resolved]

    rule = models.ForeignKey(RecordRuleV4, verbose_name="预计算规则组", related_name="specs", on_delete=models.CASCADE)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    generation = models.IntegerField("用户声明版本")
    raw_config = models.JSONField("用户原始完整配置", default=dict)
    interval = models.CharField("计算周期", max_length=16, default="1min")
    labels = models.JSONField("组级附加标签", default=list)
    content_hash = models.CharField("配置内容指纹", max_length=64)
    source = models.CharField("来源", max_length=32, default="user")
    operator = models.CharField("操作人", max_length=128, blank=True, default="")
    latest_resolved = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        "RecordRuleV4Resolved",
        verbose_name="最近解析快照",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "V4 预计算用户声明快照"
        verbose_name_plural = "V4 预计算用户声明快照"
        unique_together = (("rule", "generation"),)

    def get_records(self) -> list[RecordRuleV4SpecRecord]:
        """按用户输入顺序返回 spec records。"""

        return list(self.records.order_by("source_index", "id"))


class RecordRuleV4SpecRecord(BaseModelWithTime):
    """Spec 中的一条逻辑 record。

    record_key 是内部稳定 ID。JSON 模式可以显式传入；不外传 key 的模式按 input_config / metric_name 继承。
    """

    if TYPE_CHECKING:
        spec_id: int
        resolved_records: models.QuerySet[RecordRuleV4ResolvedRecord]

    spec = models.ForeignKey(
        RecordRuleV4Spec, verbose_name="用户声明快照", related_name="records", on_delete=models.CASCADE
    )
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    record_key = models.CharField("内部稳定记录ID", max_length=64)
    content_hash = models.CharField("记录内容指纹", max_length=64)
    source_index = models.IntegerField("原始顺序", default=0)

    input_type = models.CharField("输入类型", max_length=32)
    input_config = models.JSONField("用户原始输入", default=dict)
    metric_name = models.CharField("输出指标名", max_length=128)
    labels = models.JSONField("附加标签", default=list)

    class Meta:
        verbose_name = "V4 预计算用户声明记录"
        verbose_name_plural = "V4 预计算用户声明记录"
        unique_together = (("spec", "record_key"),)
        ordering = ("source_index", "id")

    @staticmethod
    def normalize_record_payload(record: dict[str, Any]) -> dict[str, Any]:
        """补齐单条 spec record 的默认字段。"""

        return {
            "record_key": record.get("record_key") or "",
            "input_type": record["input_type"],
            "input_config": record["input_config"],
            "metric_name": record["metric_name"],
            "labels": normalize_labels(record.get("labels")),
        }


class RecordRuleV4Resolved(BaseModelWithTime):
    """一次实时解析后的 group 语义快照。

    该层只描述 unify-query 解析出来的语义结果，不包含最终 Flow 模板。是否可更新只比较本层 content_hash。
    """

    if TYPE_CHECKING:
        rule: RecordRuleV4
        rule_id: int
        spec: RecordRuleV4Spec
        spec_id: int
        records: models.QuerySet[RecordRuleV4ResolvedRecord]
        flow: RecordRuleV4Flow

    rule = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        RecordRuleV4, verbose_name="预计算规则组", related_name="resolved", on_delete=models.CASCADE
    )
    spec = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        RecordRuleV4Spec, verbose_name="用户声明快照", related_name="resolved", on_delete=models.CASCADE
    )
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    generation = models.IntegerField("用户声明版本")
    resolve_version = models.IntegerField("同声明下解析版本")
    resolved_config = models.JSONField("解析完整配置", default=dict)
    content_hash = models.CharField("解析内容指纹", max_length=64)
    source = models.CharField("来源", max_length=32, default="scheduler")

    class Meta:
        verbose_name = "V4 预计算解析快照"
        verbose_name_plural = "V4 预计算解析快照"
        unique_together = (("rule", "spec", "resolve_version"),)

    def get_records(self) -> list[RecordRuleV4ResolvedRecord]:
        """按用户输入顺序返回 resolved records，并预加载 spec record。"""

        return list(self.records.select_related("spec_record").order_by("spec_record__source_index", "id"))


class RecordRuleV4ResolvedRecord(BaseModelWithTime):
    """Resolved 中的一条逻辑 record 解析结果。"""

    if TYPE_CHECKING:
        resolved_id: int
        spec_record_id: int
        src_vm_table_ids: list[str]
        src_result_table_configs: list[ResolvedVmResultTableConfig]

    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", related_name="records", on_delete=models.CASCADE
    )
    spec_record = models.ForeignKey(
        RecordRuleV4SpecRecord, verbose_name="用户声明记录", related_name="resolved_records", on_delete=models.CASCADE
    )
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    record_key = models.CharField("内部稳定记录ID", max_length=64)
    content_hash = models.CharField("解析记录内容指纹", max_length=64)

    metricql = models.TextField("MetricQL")
    labels = models.JSONField("合并附加标签", default=list)
    src_vm_table_ids = models.JSONField("源 VM 结果表列表", default=list)  # pyright: ignore[reportAssignmentType]
    src_result_table_configs = models.JSONField("源结果表配置列表", default=list)  # pyright: ignore[reportAssignmentType]

    class Meta:
        verbose_name = "V4 预计算解析记录"
        verbose_name_plural = "V4 预计算解析记录"
        unique_together = (("resolved", "record_key"),)
        ordering = ("spec_record__source_index", "id")


class RecordRuleV4Flow(BaseModelWithTime):
    """某份 resolved 下的目标 Flow 实体。"""

    if TYPE_CHECKING:
        rule: RecordRuleV4
        rule_id: int
        resolved: RecordRuleV4Resolved
        resolved_id: int

    rule = models.ForeignKey(  # pyright: ignore[reportAssignmentType]
        RecordRuleV4, verbose_name="预计算规则组", related_name="flows", on_delete=models.CASCADE
    )
    resolved = models.OneToOneField(  # pyright: ignore[reportAssignmentType]
        RecordRuleV4Resolved, verbose_name="解析快照", related_name="flow", on_delete=models.CASCADE
    )
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    flow_name = models.CharField("V4 Flow 名称", max_length=128)
    flow_config = models.JSONField("V4 Flow 配置", default=dict)
    content_hash = models.CharField("Flow 内容指纹", max_length=64)
    flow_status = models.CharField("Flow 实际状态", max_length=32, blank=True, default="")
    last_observed_at = models.DateTimeField("最近观测时间", null=True, blank=True)

    class Meta:
        verbose_name = "V4 预计算 Flow"
        verbose_name_plural = "V4 预计算 Flow"
        ordering = ("id",)
        indexes = [models.Index(fields=["rule", "content_hash"], name="rrv4flow_rule_hash_idx")]

    @classmethod
    def compose_for_resolved(cls, *, rule: RecordRuleV4, resolved: RecordRuleV4Resolved) -> dict[str, Any]:
        """把 resolved 快照展开成单个 group Flow 的持久化字段。"""

        flow_name = rule.flow_name
        records = resolved.get_records()
        flow_config = cls.compose_flow_config(rule=rule, resolved=resolved, flow_name=flow_name, records=records)
        content_hash = stable_hash(
            {
                "flow_name": flow_name,
                "resolved_hash": resolved.content_hash,
                "flow_config": cls.strip_runtime_status(flow_config),
            }
        )
        return {
            "flow_name": flow_name,
            "flow_config": flow_config,
            "content_hash": content_hash,
        }

    @staticmethod
    def compose_flow_config(
        *, rule: RecordRuleV4, resolved: RecordRuleV4Resolved, flow_name: str, records: list[RecordRuleV4ResolvedRecord]
    ) -> dict[str, Any]:
        """拼装 bkbase V4 Flow 配置。

        当前版本只支持一个 group 对应一个 Flow，因此这里会把所有
        resolved records 合并到同一个 RecordingRuleNode。
        """

        src_result_table_names = sorted(
            {
                config["bkbase_result_table_name"]
                for record in records
                for config in record.src_result_table_configs
                if config.get("bkbase_result_table_name")
            }
        )
        if not src_result_table_names:
            raise ValueError("resolved record src_result_table_configs is empty")
        if not rule.dst_vm_storage_name:
            raise ValueError("record rule dst_vm_storage_name is empty")

        bkbase_tenant = RecordRuleV4Flow.compose_bkbase_tenant(rule)
        source_nodes: list[dict[str, Any]] = []
        source_names: list[str] = []
        for index, result_table_name in enumerate(src_result_table_names):
            name = "vm_source" if len(src_result_table_names) == 1 else f"vm_source_{index + 1}"
            source_names.append(name)
            source_nodes.append(
                {
                    "kind": "VmSourceNode",
                    "name": name,
                    "data": {
                        "kind": "ResultTable",
                        "tenant": bkbase_tenant,
                        "namespace": RECORD_RULE_V4_BKMONITOR_NAMESPACE,
                        "name": result_table_name,
                    },
                }
            )

        recording_rule_config = [
            {
                "expr": resolved_record.metricql,
                "interval": resolved_record.resolved.spec.interval,
                "metric_name": resolved_record.spec_record.metric_name,
                "labels": resolved_record.labels,
            }
            for resolved_record in records
        ]

        return {
            "kind": "Flow",
            "metadata": {
                "tenant": bkbase_tenant,
                "namespace": RECORD_RULE_V4_BKBASE_NAMESPACE,
                "name": flow_name,
                "labels": RecordRuleV4Flow.compose_metadata_labels(rule),
                "annotations": RecordRuleV4Flow.compose_metadata_annotations(rule=rule, resolved=resolved),
            },
            "spec": {
                "nodes": [
                    *source_nodes,
                    {
                        "kind": "RecordingRuleNode",
                        "name": flow_name,
                        "inputs": source_names,
                        "output": rule.dst_vm_table_id,
                        "config": recording_rule_config,
                        "storage": {
                            "kind": "VmStorage",
                            "tenant": bkbase_tenant,
                            "namespace": RECORD_RULE_V4_BKMONITOR_NAMESPACE,
                            "name": rule.dst_vm_storage_name,
                        },
                    },
                ],
                "operation_config": {
                    "start_position": "from_head",
                    "stream_cluster": None,
                    "batch_cluster": None,
                    "deploy_mode": None,
                },
                "maintainers": [settings.BK_DATA_PROJECT_MAINTAINER],
                "desired_status": rule.desired_status,
            },
            "status": None,
        }

    @staticmethod
    def compose_bkbase_tenant(rule: RecordRuleV4) -> str:
        """生成 bkbase V4 资源 tenant。

        计算平台单租户模式仍使用历史默认租户；开启多租户后，Flow、source、storage
        需要跟随当前规则组所属的实际 bk_tenant_id。
        """

        if settings.ENABLE_MULTI_TENANT_MODE:
            return rule.bk_tenant_id or RECORD_RULE_V4_DEFAULT_TENANT
        return RECORD_RULE_V4_DEFAULT_TENANT

    @staticmethod
    def compose_metadata_labels(rule: RecordRuleV4) -> dict[str, str]:
        """生成 Flow metadata labels，只保留平台当前需要检索的业务标签。"""

        return {
            "bk_biz_id": str(rule.bk_biz_id),
            "flow_type": FLOW_TYPE_RECORD_RULE,
        }

    @staticmethod
    def compose_metadata_annotations(*, rule: RecordRuleV4, resolved: RecordRuleV4Resolved) -> dict[str, str]:
        """生成 Flow 的业务 annotation。

        annotation key 使用 DNS 前缀和 kebab-case，值统一保存为字符串，便于后续在 bkbase
        或排查工具里按 K8s 风格读取。
        """

        prefix = FLOW_METADATA_ANNOTATION_PREFIX
        return {
            f"{prefix}/space-uid": rule.space_uid,
            f"{prefix}/name": rule.name,
            f"{prefix}/generation": str(resolved.generation),
            f"{prefix}/resolved-version": str(resolved.resolve_version),
        }

    @staticmethod
    def strip_runtime_status(flow_config: dict[str, Any]) -> dict[str, Any]:
        """移除运行态字段，避免启停影响 Flow 内容指纹。"""

        pure_config = copy.deepcopy(flow_config)
        pure_config.get("spec", {}).pop("desired_status", None)
        return pure_config

    def mark_flow_observed(self, flow_status: str) -> None:
        """写入最近一次从 bkbase 观测到的 Flow 实际状态。"""

        self.flow_status = flow_status
        self.last_observed_at = now()
        self.save(update_fields=["flow_status", "last_observed_at", "updated_at"])


class RecordRuleV4Event(BaseModelWithTime):
    """严格枚举的 V4 预计算事件流。"""

    if TYPE_CHECKING:
        rule_id: int
        spec_id: int | None
        resolved_id: int | None
        flow_id: int | None

    rule = models.ForeignKey(RecordRuleV4, verbose_name="预计算规则组", related_name="events", on_delete=models.CASCADE)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    spec = models.ForeignKey(
        RecordRuleV4Spec, verbose_name="用户声明快照", null=True, blank=True, on_delete=models.SET_NULL
    )
    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", null=True, blank=True, on_delete=models.SET_NULL
    )
    flow = models.ForeignKey(RecordRuleV4Flow, verbose_name="Flow", null=True, blank=True, on_delete=models.SET_NULL)
    generation = models.IntegerField("用户声明版本", default=0)
    event_type = models.CharField("事件类型", max_length=64)
    status = models.CharField("事件状态", max_length=32)
    source = models.CharField("来源", max_length=32, default="system")
    operator = models.CharField("操作人", max_length=128, blank=True, default="")
    reason = models.CharField("原因", max_length=128, blank=True, default="")
    message = models.TextField("消息", blank=True, default="")
    detail = models.JSONField("详情", default=dict)

    class Meta:
        verbose_name = "V4 预计算事件"
        verbose_name_plural = "V4 预计算事件"
        indexes = [
            models.Index(fields=["rule", "generation"], name="rrv4event_rule_gen_idx"),
            models.Index(fields=["rule", "event_type"], name="rrv4event_rule_type_idx"),
        ]

    def clean(self) -> None:
        """保存前统一校验事件类型、状态、关联对象和 detail 字段。"""

        self.validate_event_payload(
            event_type=self.event_type,
            status=self.status,
            reason=self.reason,
            spec=self.spec,
            resolved=self.resolved,
            flow=self.flow,
            detail=self.detail or {},
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def record_user_create(
        cls, rule: RecordRuleV4, spec: RecordRuleV4Spec, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=spec,
            event_type=EVENT_TYPE_USER_CREATE,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_user_spec_changed(
        cls, rule: RecordRuleV4, spec: RecordRuleV4Spec, source: str, operator: str, changed_fields: list[str]
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=spec,
            event_type=EVENT_TYPE_USER_SPEC_CHANGED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
            detail={"changed_fields": changed_fields},
        )

    @classmethod
    def record_user_metadata_changed(
        cls, rule: RecordRuleV4, source: str, operator: str, changed_fields: list[str]
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_USER_METADATA_CHANGED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
            detail={"changed_fields": changed_fields},
        )

    @classmethod
    def record_user_auto_refresh_changed(cls, rule: RecordRuleV4, source: str, operator: str) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_USER_AUTO_REFRESH_CHANGED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
            detail={"auto_refresh": rule.auto_refresh},
        )

    @classmethod
    def record_user_desired_status_changed(cls, rule: RecordRuleV4, source: str, operator: str) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_USER_DESIRED_STATUS_CHANGED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
            detail={"desired_status": rule.desired_status},
        )

    @classmethod
    def record_operation_locked(
        cls, rule: RecordRuleV4, operation: str, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_OPERATION_SKIPPED,
            status=EVENT_STATUS_SKIPPED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_OPERATION_LOCKED,
            detail={
                "owner": rule.operation_lock_owner,
                "reason": rule.operation_lock_reason,
                "expires_at": rule.operation_lock_expires_at.isoformat() if rule.operation_lock_expires_at else "",
                "operation": operation,
            },
        )

    @classmethod
    def record_resolve_changed(
        cls,
        rule: RecordRuleV4,
        spec: RecordRuleV4Spec,
        resolved: RecordRuleV4Resolved,
        source: str,
        operator: str,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=spec,
            resolved=resolved,
            event_type=EVENT_TYPE_RESOLVE_CHANGED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_resolve_unchanged(
        cls,
        rule: RecordRuleV4,
        spec: RecordRuleV4Spec,
        resolved: RecordRuleV4Resolved,
        source: str,
        operator: str,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=spec,
            resolved=resolved,
            event_type=EVENT_TYPE_RESOLVE_UNCHANGED,
            status=EVENT_STATUS_SKIPPED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_resolve_failed(
        cls,
        rule: RecordRuleV4,
        source: str,
        operator: str,
        message: str,
        spec: RecordRuleV4Spec | None = None,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=spec,
            event_type=EVENT_TYPE_RESOLVE_FAILED,
            status=EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_RESOLVE_FAILED if spec else EVENT_REASON_SPEC_MISSING,
            message=message,
        )

    @classmethod
    def record_apply_started(
        cls, rule: RecordRuleV4, flow: RecordRuleV4Flow | None, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec if flow else rule.current_spec,
            resolved=flow.resolved if flow else rule.get_latest_resolved(),
            flow=flow,
            event_type=EVENT_TYPE_APPLY_STARTED,
            status=EVENT_STATUS_STARTED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_apply_succeeded(
        cls, rule: RecordRuleV4, flow: RecordRuleV4Flow | None, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec if flow else rule.current_spec,
            resolved=flow.resolved if flow else rule.get_latest_resolved(),
            flow=flow,
            event_type=EVENT_TYPE_APPLY_SUCCEEDED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_apply_failed(
        cls,
        rule: RecordRuleV4,
        source: str,
        operator: str,
        message: str,
        flow: RecordRuleV4Flow | None = None,
        stale: bool = False,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec if flow else rule.current_spec,
            resolved=flow.resolved if flow else rule.get_latest_resolved(),
            flow=flow,
            event_type=EVENT_TYPE_APPLY_FAILED,
            status=EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_STALE_FLOW if stale else EVENT_REASON_APPLY_FAILED,
            message=message,
        )

    @classmethod
    def record_apply_failed_missing_flow(cls, rule: RecordRuleV4, source: str, operator: str) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_APPLY_FAILED,
            status=EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_FLOW_MISSING,
            message="latest flow is missing",
        )

    @classmethod
    def record_apply_skipped_stale_flow(
        cls, rule: RecordRuleV4, flow: RecordRuleV4Flow, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec,
            resolved=flow.resolved,
            flow=flow,
            event_type=EVENT_TYPE_APPLY_SKIPPED,
            status=EVENT_STATUS_SKIPPED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_STALE_FLOW,
            detail={
                "flow_id": flow.pk,
                "latest_resolved_id": rule.current_spec.latest_resolved_id if rule.current_spec else None,
                "current_generation": rule.generation,
                "flow_generation": flow.resolved.generation,
            },
        )

    @classmethod
    def record_flow_action_started(
        cls,
        rule: RecordRuleV4,
        flow: RecordRuleV4Flow,
        action_type: str,
        source: str,
        operator: str,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec,
            resolved=flow.resolved,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_STARTED,
            status=EVENT_STATUS_STARTED,
            source=source,
            operator=operator,
            detail=cls.build_flow_action_detail(flow, action_type),
        )

    @classmethod
    def record_flow_action_result(
        cls,
        rule: RecordRuleV4,
        flow: RecordRuleV4Flow,
        action_type: str,
        succeeded: bool,
        source: str,
        operator: str,
        message: str = "",
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=flow.resolved.spec,
            resolved=flow.resolved,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_SUCCEEDED if succeeded else EVENT_TYPE_FLOW_ACTION_FAILED,
            status=EVENT_STATUS_SUCCEEDED if succeeded else EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason="" if succeeded else EVENT_REASON_APPLY_FAILED,
            message=message,
            detail=cls.build_flow_action_detail(flow, action_type),
        )

    @staticmethod
    def build_flow_action_detail(flow: RecordRuleV4Flow, action_type: str) -> dict[str, Any]:
        """生成固定结构的 Flow action detail。"""

        return {
            "action_type": action_type,
            "flow_id": flow.pk,
            "flow_name": flow.flow_name,
            "flow_content_hash": flow.content_hash,
        }

    @classmethod
    def record_flow_observed(
        cls,
        rule: RecordRuleV4,
        flow_status: str,
        source: str,
        operator: str,
        flow: RecordRuleV4Flow | None = None,
        message: str = "",
        observe_succeeded: bool | None = None,
    ) -> RecordRuleV4Event:
        if observe_succeeded is None:
            observe_succeeded = flow_status == RecordRuleV4FlowStatus.OK.value
        return cls.record(
            rule=rule,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_OBSERVED,
            status=EVENT_STATUS_SUCCEEDED if observe_succeeded else EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=flow_status,
            message=message,
        )

    @classmethod
    def record(
        cls,
        *,
        rule: RecordRuleV4,
        event_type: str,
        status: str,
        source: str,
        operator: str,
        spec: RecordRuleV4Spec | None = None,
        resolved: RecordRuleV4Resolved | None = None,
        flow: RecordRuleV4Flow | None = None,
        reason: str = "",
        message: str = "",
        detail: dict[str, Any] | None = None,
    ) -> RecordRuleV4Event:
        """写入一条结构化事件。

        事件只能通过这里或上方的语义化封装写入，避免 event_type/detail
        变成随意扩展的自由文本。
        """

        detail = detail or {}
        cls.validate_event_payload(
            event_type=event_type,
            status=status,
            reason=reason,
            spec=spec,
            resolved=resolved,
            flow=flow,
            detail=detail,
        )
        generation = (
            spec.generation
            if spec
            else resolved.generation
            if resolved
            else flow.resolved.generation
            if flow
            else rule.generation
        )
        return cls.objects.create(
            rule=rule,
            bk_tenant_id=rule.bk_tenant_id,
            spec=spec,
            resolved=resolved,
            flow=flow,
            generation=generation,
            event_type=event_type,
            status=status,
            source=source,
            operator=operator,
            reason=reason,
            message=message,
            detail=detail,
            creator=operator or source,
            updater=operator or source,
        )

    @classmethod
    def validate_event_payload(
        cls,
        *,
        event_type: str,
        status: str,
        reason: str,
        spec: RecordRuleV4Spec | None,
        resolved: RecordRuleV4Resolved | None,
        flow: RecordRuleV4Flow | None,
        detail: dict[str, Any],
    ) -> None:
        """按照 EVENT_DEFINITIONS 校验事件结构。"""

        definition = EVENT_DEFINITIONS.get(event_type)
        if not definition:
            raise ValueError(f"unsupported event_type: {event_type}")

        if status not in definition["statuses"]:
            raise ValueError(f"unsupported status for {event_type}: {status}")
        if reason not in definition["reasons"]:
            raise ValueError(f"unsupported reason for {event_type}: {reason}")

        for relation_name, value in [
            ("spec", spec),
            ("resolved", resolved),
            ("flow", flow),
        ]:
            # 每类事件都明确声明允许挂载哪些上下文对象，避免排查时语义混乱。
            policy = definition.get(relation_name, EVENT_RELATION_OPTIONAL)
            if policy == EVENT_RELATION_REQUIRED and value is None:
                raise ValueError(f"{relation_name} is required for event_type: {event_type}")
            if policy == EVENT_RELATION_FORBIDDEN and value is not None:
                raise ValueError(f"{relation_name} is forbidden for event_type: {event_type}")

        allowed_detail_keys = definition.get("detail_keys")
        if allowed_detail_keys is not None and set(detail) - set(allowed_detail_keys):
            # detail_keys 是白名单；新增字段需要先更新事件定义和测试。
            raise ValueError(f"unsupported detail keys for {event_type}: {sorted(set(detail) - allowed_detail_keys)}")
