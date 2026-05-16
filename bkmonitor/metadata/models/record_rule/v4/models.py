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

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from django.db import models
from django.utils import timezone

from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.utils.db import JsonField
from metadata.models.common import BaseModelWithTime
from metadata.models.record_rule import utils
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_DEFAULT_REFRESH_INTERVAL,
    RECORD_RULE_V4_INTERVAL_CHOICES,
    RecordRuleV4ApplyStatus,
    RecordRuleV4DeploymentStrategy,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
    RecordRuleV4InputType,
    RecordRuleV4Status,
)
from metadata.models.space.constants import SpaceTypes

logger = logging.getLogger("metadata")


CONDITION_TRUE = "True"
CONDITION_FALSE = "False"
CONDITION_UNKNOWN = "Unknown"

CONDITION_RECONCILED = "Reconciled"
CONDITION_RESOLVED = "Resolved"
CONDITION_DEPLOYMENT_READY = "DeploymentReady"
CONDITION_FLOW_HEALTHY = "FlowHealthy"
CONDITION_UPDATE_AVAILABLE = "UpdateAvailable"

EVENT_STATUS_STARTED = "started"
EVENT_STATUS_SUCCEEDED = "succeeded"
EVENT_STATUS_FAILED = "failed"
EVENT_STATUS_SKIPPED = "skipped"

EVENT_TYPE_USER_CREATE = "user.create"
EVENT_TYPE_USER_SPEC_CHANGED = "user.spec_changed"
EVENT_TYPE_USER_AUTO_REFRESH_CHANGED = "user.auto_refresh_changed"
EVENT_TYPE_USER_DESIRED_STATUS_CHANGED = "user.desired_status_changed"
EVENT_TYPE_OPERATION_SKIPPED = "operation.skipped"
EVENT_TYPE_RESOLVE_CHANGED = "resolve.changed"
EVENT_TYPE_RESOLVE_UNCHANGED = "resolve.unchanged"
EVENT_TYPE_RESOLVE_FAILED = "resolve.failed"
EVENT_TYPE_DEPLOYMENT_PLANNED = "deployment.planned"
EVENT_TYPE_DEPLOYMENT_UNCHANGED = "deployment.unchanged"
EVENT_TYPE_APPLY_STARTED = "apply.started"
EVENT_TYPE_APPLY_SUCCEEDED = "apply.succeeded"
EVENT_TYPE_APPLY_FAILED = "apply.failed"
EVENT_TYPE_APPLY_SKIPPED = "apply.skipped"
EVENT_TYPE_FLOW_ACTION_STARTED = "flow_action.started"
EVENT_TYPE_FLOW_ACTION_SUCCEEDED = "flow_action.succeeded"
EVENT_TYPE_FLOW_ACTION_FAILED = "flow_action.failed"
EVENT_TYPE_FLOW_OBSERVED = "flow.observed"

EVENT_REASON_OPERATION_LOCKED = "OperationLocked"
EVENT_REASON_STALE_SPEC = "StaleSpec"
EVENT_REASON_STALE_DEPLOYMENT = "StaleDeployment"
EVENT_REASON_SPEC_MISSING = "SpecMissing"
EVENT_REASON_RESOLVE_FAILED = "ResolveFailed"
EVENT_REASON_DEPLOYMENT_MISSING = "DeploymentMissing"
EVENT_REASON_APPLY_FAILED = "ApplyFailed"

EVENT_RELATION_REQUIRED = "required"
EVENT_RELATION_OPTIONAL = "optional"
EVENT_RELATION_FORBIDDEN = "forbidden"

EVENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    EVENT_TYPE_USER_CREATE: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_USER_SPEC_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"changed_fields"},
    },
    EVENT_TYPE_USER_AUTO_REFRESH_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"auto_refresh"},
    },
    EVENT_TYPE_USER_DESIRED_STATUS_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
        "detail_keys": {"desired_status"},
    },
    EVENT_TYPE_OPERATION_SKIPPED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {EVENT_REASON_OPERATION_LOCKED},
        "detail_keys": {"owner", "reason", "expires_at", "operation"},
    },
    EVENT_TYPE_RESOLVE_CHANGED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_RESOLVE_UNCHANGED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_RESOLVE_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_FORBIDDEN,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {EVENT_REASON_SPEC_MISSING, EVENT_REASON_RESOLVE_FAILED},
    },
    EVENT_TYPE_DEPLOYMENT_PLANNED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_DEPLOYMENT_UNCHANGED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_APPLY_STARTED: {
        "statuses": {EVENT_STATUS_STARTED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_APPLY_SUCCEEDED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {""},
    },
    EVENT_TYPE_APPLY_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "deployment": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_OPTIONAL,
        "reasons": {EVENT_REASON_DEPLOYMENT_MISSING, EVENT_REASON_APPLY_FAILED, EVENT_REASON_STALE_DEPLOYMENT},
    },
    EVENT_TYPE_APPLY_SKIPPED: {
        "statuses": {EVENT_STATUS_SKIPPED},
        "spec": EVENT_RELATION_OPTIONAL,
        "resolved": EVENT_RELATION_OPTIONAL,
        "deployment": EVENT_RELATION_OPTIONAL,
        "flow": EVENT_RELATION_FORBIDDEN,
        "reasons": {EVENT_REASON_STALE_DEPLOYMENT},
        "detail_keys": {"deployment_id", "latest_deployment_id", "current_generation", "deployment_generation"},
    },
    EVENT_TYPE_FLOW_ACTION_STARTED: {
        "statuses": {EVENT_STATUS_STARTED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {""},
        "detail_keys": {"action_key", "action_type"},
    },
    EVENT_TYPE_FLOW_ACTION_SUCCEEDED: {
        "statuses": {EVENT_STATUS_SUCCEEDED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {""},
        "detail_keys": {"action_key", "action_type"},
    },
    EVENT_TYPE_FLOW_ACTION_FAILED: {
        "statuses": {EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_REQUIRED,
        "resolved": EVENT_RELATION_REQUIRED,
        "deployment": EVENT_RELATION_REQUIRED,
        "flow": EVENT_RELATION_REQUIRED,
        "reasons": {EVENT_REASON_APPLY_FAILED},
        "detail_keys": {"action_key", "action_type"},
    },
    EVENT_TYPE_FLOW_OBSERVED: {
        "statuses": {EVENT_STATUS_SUCCEEDED, EVENT_STATUS_FAILED},
        "spec": EVENT_RELATION_FORBIDDEN,
        "resolved": EVENT_RELATION_FORBIDDEN,
        "deployment": EVENT_RELATION_OPTIONAL,
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


def get_deployment_strategy_name(deployment_strategy: str | dict[str, Any] | None) -> str:
    """从部署策略配置中取出策略名称。"""

    if deployment_strategy is None:
        return RecordRuleV4DeploymentStrategy.PER_RECORD.value
    if isinstance(deployment_strategy, str):
        return deployment_strategy
    if isinstance(deployment_strategy, dict):
        return str(deployment_strategy.get("strategy") or RecordRuleV4DeploymentStrategy.PER_RECORD.value)
    raise ValueError("deployment_strategy must be string or dict")


def normalize_deployment_strategy(deployment_strategy: str | dict[str, Any] | None) -> dict[str, Any]:
    """归一化部署策略配置，预留 options 结构给后续策略参数。"""

    strategy = get_deployment_strategy_name(deployment_strategy)
    if strategy not in {item.value for item in RecordRuleV4DeploymentStrategy}:
        raise ValueError(f"unsupported deployment_strategy: {strategy}")

    if isinstance(deployment_strategy, dict):
        options = deployment_strategy.get("options") or {}
        if not isinstance(options, dict):
            raise ValueError("deployment_strategy.options must be dict")
        result = dict(deployment_strategy)
        result["strategy"] = strategy
        result["options"] = dict(options)
        return result
    return {"strategy": strategy, "options": {}}


def now() -> datetime:
    """统一封装当前时间，方便模型方法和测试保持同一入口。"""

    return timezone.now()


def generate_record_key() -> str:
    """生成组内 record 的内部稳定 ID。"""

    return f"{SPEC_RECORD_KEY_PREFIX}_{uuid4().hex[:12]}"


def _safe_component(value: str, max_length: int, fallback: str) -> str:
    """把用户输入裁剪成可用于 table / flow name 的安全片段。"""

    raw = str(value or "").strip()
    if not raw:
        return fallback

    prefixed = f"{fallback}_{raw}"
    try:
        sanitized = utils.sanitize(prefixed, max_length=len(fallback) + 1 + max_length)
    except ValueError:
        sanitized = fallback

    prefix = f"{fallback}_"
    if sanitized.startswith(prefix):
        sanitized = sanitized[len(prefix) :]
    sanitized = sanitized.strip("_")
    return sanitized[:max_length] or fallback


def _extract_random_suffix_from_table(table_id: str) -> str:
    """从已生成 table_id 中取出随机段，用于关联 group 级 Flow 名称。"""

    name = table_id.split(".", 1)[0]
    suffix = name.rsplit("_", 1)[-1]
    return suffix[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH] or uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH]


class RecordRuleV4(BaseModelWithTime):
    """V4 Recording Rule group 声明。

    主对象只代表用户眼中的一组预计算配置。用户输入、实时解析结果、最终部署计划分别拆到
    Spec / Resolved / Deployment；因此 flow 模板变化不会直接影响 group 是否可更新。
    """

    if TYPE_CHECKING:
        current_spec_id: int | None
        latest_resolved_id: int | None
        latest_deployment_id: int | None
        applied_deployment_id: int | None
        specs: models.QuerySet[RecordRuleV4Spec]
        resolved: models.QuerySet[RecordRuleV4Resolved]
        deployments: models.QuerySet[RecordRuleV4Deployment]
        flows: models.QuerySet[RecordRuleV4Flow]
        events: models.QuerySet[RecordRuleV4Event]

    space_type = models.CharField("空间类型", max_length=64)
    space_id = models.CharField("空间ID", max_length=128)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    group_name = models.CharField("预计算组名称", max_length=128)
    table_id = models.CharField("结果表名", max_length=128)
    dst_vm_table_id = models.CharField("VM 结果表RT", max_length=128)

    generation = models.IntegerField("用户声明版本", default=0)
    observed_generation = models.IntegerField("已成功下发的声明版本", default=0)
    current_spec = models.ForeignKey(
        "RecordRuleV4Spec",
        verbose_name="当前用户声明快照",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    latest_resolved = models.ForeignKey(
        "RecordRuleV4Resolved",
        verbose_name="最近解析快照",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    latest_deployment = models.ForeignKey(
        "RecordRuleV4Deployment",
        verbose_name="最近部署计划",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    applied_deployment = models.ForeignKey(
        "RecordRuleV4Deployment",
        verbose_name="最近成功下发的部署计划",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    desired_status = models.CharField("期望状态", max_length=32, default=RecordRuleV4DesiredStatus.RUNNING.value)
    status = models.CharField("聚合阶段", max_length=32, default=RecordRuleV4Status.CREATED.value)
    conditions = JsonField("当前状态条件", default=dict)
    update_available = models.BooleanField("是否存在可更新配置", default=False)

    auto_refresh = models.BooleanField("是否自动刷新", default=True)
    last_error = models.TextField("最近错误", blank=True, default="")
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
    def compose_table_id(cls, group_name: str, random_suffix: str | None = None) -> str:
        """生成 group 级输出结果表，保留名称提示和随机段，总长度不超过 50。"""

        suffix = (random_suffix or uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH])[
            :RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH
        ]
        prefix = "bkprecal"
        reserved = len(prefix) + len(suffix) + len(RECORD_RULE_V4_TABLE_ID_SUFFIX) + 2
        component_length = max(1, RECORD_RULE_V4_MAX_GENERATED_NAME_LENGTH - reserved)
        group_slug = _safe_component(group_name, component_length, "group")
        return f"{prefix}_{group_slug}_{suffix}{RECORD_RULE_V4_TABLE_ID_SUFFIX}"

    @classmethod
    def compose_flow_name(
        cls, group_name: str, flow_hint: str, random_suffix: str | None = None, max_length: int = 50
    ) -> str:
        """生成目标 Flow 名称。

        Flow 名称跟 group/record 有可读关联，同时通过稳定随机段避免把 group_name 做成唯一约束。
        """

        suffix = (random_suffix or uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH])[
            :RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH
        ]
        group_slug = _safe_component(group_name, 12, "group")
        reserved = len("rrv4") + len(group_slug) + len(suffix) + 3
        hint_length = max(1, max_length - reserved)
        hint_slug = _safe_component(flow_hint, hint_length, "flow")
        return f"rrv4_{group_slug}_{hint_slug}_{suffix}"[:max_length].rstrip("_")

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
            for condition_type in [
                CONDITION_RECONCILED,
                CONDITION_RESOLVED,
                CONDITION_DEPLOYMENT_READY,
                CONDITION_FLOW_HEALTHY,
            ]
        ):
            self.status = RecordRuleV4Status.FAILED.value
            return

        # generation 表达用户声明变更，observed_generation 表达成功下发到外部的版本。
        if self.generation > self.observed_generation:
            self.status = RecordRuleV4Status.PENDING.value
            return

        # resolved 漂移但未下发时，用 auto_refresh 区分“待自动执行”和“需要人工更新”。
        if self.update_available:
            self.status = RecordRuleV4Status.PENDING.value if self.auto_refresh else RecordRuleV4Status.OUTDATED.value
            return

        if self.desired_status == RecordRuleV4DesiredStatus.STOPPED.value:
            self.status = RecordRuleV4Status.STOPPED.value
            return

        self.status = RecordRuleV4Status.RUNNING.value

    def use_spec(self, spec: RecordRuleV4Spec) -> None:
        """切换当前用户声明快照并推进 generation。"""

        self.current_spec = spec
        self.generation = spec.generation
        if spec.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            # running/stopped 是运行态，不走 use_spec；只有 deleted 会进入声明快照。
            self.desired_status = spec.desired_status
        self.update_available = True
        self.set_condition(CONDITION_UPDATE_AVAILABLE, CONDITION_TRUE, "SpecChanged")
        self.sync_phase()
        self.save(
            update_fields=[
                "current_spec",
                "generation",
                "desired_status",
                "update_available",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def use_resolved(self, resolved: RecordRuleV4Resolved) -> None:
        """切换最近解析快照，并根据 applied 指针标记是否可更新。"""

        self.latest_resolved = resolved
        self.last_error = ""
        self.last_check_time = now()
        self.update_available = self.applied_deployment_id is None or (
            self.applied_deployment is not None and self.applied_deployment.resolved_id != resolved.pk
        )
        self.set_condition(CONDITION_RESOLVED, CONDITION_TRUE, "Changed")
        self.set_condition(
            CONDITION_UPDATE_AVAILABLE,
            CONDITION_TRUE if self.update_available else CONDITION_FALSE,
            "ResolvedChanged" if self.update_available else "ResolvedApplied",
        )
        self.sync_phase()
        self.save(
            update_fields=[
                "latest_resolved",
                "last_error",
                "last_check_time",
                "update_available",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def use_deployment(self, deployment: RecordRuleV4Deployment) -> None:
        """切换最近部署计划，并根据 applied 指针标记是否需要下发。"""

        self.latest_deployment = deployment
        self.update_available = self.applied_deployment_id != deployment.pk
        self.set_condition(CONDITION_DEPLOYMENT_READY, CONDITION_TRUE, "Planned")
        self.set_condition(
            CONDITION_UPDATE_AVAILABLE,
            CONDITION_TRUE if self.update_available else CONDITION_FALSE,
            "DeploymentChanged" if self.update_available else "DeploymentApplied",
        )
        self.sync_phase()
        self.save(
            update_fields=[
                "latest_deployment",
                "update_available",
                "conditions",
                "status",
                "updated_at",
            ]
        )

    def set_desired_status(self, desired_status: str) -> None:
        """更新 group 运行态期望状态。

        running/stopped 不生成 spec；deleted 会由 use_spec 统一处理。
        """

        self.validate_desired_status(desired_status)
        self.desired_status = desired_status
        if desired_status != RecordRuleV4DesiredStatus.DELETED.value:
            self.deleted_at = None
        self.sync_phase()
        self.save(update_fields=["desired_status", "deleted_at", "status", "updated_at"])

    def mark_deployment_applied(self, deployment: RecordRuleV4Deployment) -> None:
        """标记一次 deployment 已完整下发成功。"""

        self.applied_deployment = deployment
        self.observed_generation = deployment.generation
        self.last_refresh_time = now()
        self.last_error = ""
        self.update_available = False
        self.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "ApplySucceeded")
        self.set_condition(CONDITION_UPDATE_AVAILABLE, CONDITION_FALSE, "DeploymentApplied")
        self.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_UNKNOWN, "ApplySubmitted")
        if deployment.spec.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            self.deleted_at = now()
        self.sync_phase()
        self.save()

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
            "group_name": self.group_name,
            "table_id": self.table_id,
            "dst_vm_table_id": self.dst_vm_table_id,
            "generation": self.generation,
            "observed_generation": self.observed_generation,
            "current_spec_id": self.current_spec_id,
            "latest_resolved_id": self.latest_resolved_id,
            "latest_deployment_id": self.latest_deployment_id,
            "applied_deployment_id": self.applied_deployment_id,
            "desired_status": self.desired_status,
            "status": self.status,
            "conditions": self.conditions,
            "update_available": self.update_available,
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

    @staticmethod
    def validate_deployment_strategy(strategy: str | dict[str, Any] | None) -> None:
        normalize_deployment_strategy(strategy)


class RecordRuleV4Spec(BaseModelWithTime):
    """用户提交的 group 原始配置快照。"""

    if TYPE_CHECKING:
        rule_id: int
        records: models.QuerySet[RecordRuleV4SpecRecord]
        resolved: models.QuerySet[RecordRuleV4Resolved]
        deployments: models.QuerySet[RecordRuleV4Deployment]

    rule = models.ForeignKey(RecordRuleV4, verbose_name="预计算规则组", related_name="specs", on_delete=models.CASCADE)
    generation = models.IntegerField("用户声明版本")
    raw_config = JsonField("用户原始完整配置", default=dict)
    interval = models.CharField("计算周期", max_length=16, default="1min")
    labels = JsonField("组级附加标签", default=list)
    deployment_strategy = JsonField("部署策略配置", default=dict)
    desired_status = models.CharField("期望状态", max_length=32, default=RecordRuleV4DesiredStatus.RUNNING.value)
    content_hash = models.CharField("配置内容指纹", max_length=64)
    source = models.CharField("来源", max_length=32, default="user")
    operator = models.CharField("操作人", max_length=128, blank=True, default="")

    class Meta:
        verbose_name = "V4 预计算用户声明快照"
        verbose_name_plural = "V4 预计算用户声明快照"
        unique_together = (("rule", "generation"),)

    def get_records(self) -> list[RecordRuleV4SpecRecord]:
        """按用户输入顺序返回 spec records。"""

        return list(self.records.order_by("source_index", "id"))

    @property
    def deployment_strategy_name(self) -> str:
        """返回当前 spec 的部署策略名称。"""

        return get_deployment_strategy_name(self.deployment_strategy)


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
    record_key = models.CharField("内部稳定记录ID", max_length=64)
    content_hash = models.CharField("记录内容指纹", max_length=64)
    source_index = models.IntegerField("原始顺序", default=0)

    input_type = models.CharField("输入类型", max_length=32)
    input_config = JsonField("用户原始输入", default=dict)
    metric_name = models.CharField("输出指标名", max_length=128)
    labels = JsonField("附加标签", default=list)

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
        rule_id: int
        spec_id: int
        records: models.QuerySet[RecordRuleV4ResolvedRecord]
        deployments: models.QuerySet[RecordRuleV4Deployment]
        flows: models.QuerySet[RecordRuleV4Flow]

    rule = models.ForeignKey(
        RecordRuleV4, verbose_name="预计算规则组", related_name="resolved", on_delete=models.CASCADE
    )
    spec = models.ForeignKey(
        RecordRuleV4Spec, verbose_name="用户声明快照", related_name="resolved", on_delete=models.CASCADE
    )
    generation = models.IntegerField("用户声明版本")
    resolve_version = models.IntegerField("同声明下解析版本")
    resolved_config = JsonField("解析完整配置", default=dict)
    content_hash = models.CharField("解析内容指纹", max_length=64)
    source = models.CharField("来源", max_length=32, default="scheduler")

    class Meta:
        verbose_name = "V4 预计算解析快照"
        verbose_name_plural = "V4 预计算解析快照"
        unique_together = (("rule", "spec", "resolve_version"),)

    def get_records(self) -> list[RecordRuleV4ResolvedRecord]:
        """按用户输入顺序返回 resolved records，并预加载 spec record。"""

        return list(self.records.select_related("spec_record").order_by("source_index", "id"))


class RecordRuleV4ResolvedRecord(BaseModelWithTime):
    """Resolved 中的一条逻辑 record 解析结果。"""

    if TYPE_CHECKING:
        resolved_id: int
        spec_record_id: int
        flow_id: int | None

    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", related_name="records", on_delete=models.CASCADE
    )
    spec_record = models.ForeignKey(
        RecordRuleV4SpecRecord, verbose_name="用户声明记录", related_name="resolved_records", on_delete=models.CASCADE
    )
    flow = models.ForeignKey(
        "RecordRuleV4Flow",
        verbose_name="归属 Flow",
        related_name="records",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    record_key = models.CharField("内部稳定记录ID", max_length=64)
    content_hash = models.CharField("解析记录内容指纹", max_length=64)
    source_index = models.IntegerField("原始顺序", default=0)

    metricql = models.TextField("MetricQL")
    labels = JsonField("合并附加标签", default=list)
    src_vm_table_ids = JsonField("源 VM 结果表列表", default=list)
    src_result_table_configs = JsonField("源结果表配置列表", default=list)
    dst_vm_storage_name = models.CharField("目标 VM 存储名称", max_length=128, blank=True, default="")

    class Meta:
        verbose_name = "V4 预计算解析记录"
        verbose_name_plural = "V4 预计算解析记录"
        unique_together = (("resolved", "record_key"),)
        ordering = ("source_index", "id")


class RecordRuleV4Deployment(BaseModelWithTime):
    """将 resolved 语义快照展开成可下发的物理部署计划。"""

    if TYPE_CHECKING:
        rule_id: int
        spec_id: int
        resolved_id: int

    rule = models.ForeignKey(
        RecordRuleV4, verbose_name="预计算规则组", related_name="deployments", on_delete=models.CASCADE
    )
    spec = models.ForeignKey(
        RecordRuleV4Spec, verbose_name="用户声明快照", related_name="deployments", on_delete=models.CASCADE
    )
    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", related_name="deployments", on_delete=models.CASCADE
    )
    generation = models.IntegerField("用户声明版本")
    deployment_version = models.IntegerField("同解析下部署版本")
    strategy = models.CharField("部署策略", max_length=32, default=RecordRuleV4DeploymentStrategy.PER_RECORD.value)
    content_hash = models.CharField("部署语义指纹", max_length=64)
    plan_config = JsonField("部署计划摘要", default=dict)
    source = models.CharField("来源", max_length=32, default="scheduler")
    apply_status = models.CharField("下发状态", max_length=32, default=RecordRuleV4ApplyStatus.PENDING.value)
    applied_at = models.DateTimeField("下发时间", null=True, blank=True)
    apply_error = models.TextField("下发错误", blank=True, default="")

    class Meta:
        verbose_name = "V4 预计算部署计划"
        verbose_name_plural = "V4 预计算部署计划"
        unique_together = (("rule", "resolved", "deployment_version"),)

    def mark_apply_succeeded(self) -> None:
        """记录 deployment 已成功执行。"""

        self.apply_status = RecordRuleV4ApplyStatus.SUCCEEDED.value
        self.applied_at = now()
        self.apply_error = ""
        self.save(update_fields=["apply_status", "applied_at", "apply_error", "updated_at"])

    def mark_apply_failed(self, err: Exception | str) -> None:
        """记录 deployment 执行失败及错误信息。"""

        self.apply_status = RecordRuleV4ApplyStatus.FAILED.value
        self.apply_error = str(err)
        self.save(update_fields=["apply_status", "apply_error", "updated_at"])


class RecordRuleV4Flow(BaseModelWithTime):
    """某份 resolved 下的目标 Flow 实体。"""

    if TYPE_CHECKING:
        rule_id: int
        resolved_id: int
        records: models.QuerySet[RecordRuleV4ResolvedRecord]

    rule = models.ForeignKey(RecordRuleV4, verbose_name="预计算规则组", related_name="flows", on_delete=models.CASCADE)
    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", related_name="flows", on_delete=models.CASCADE
    )
    flow_key = models.CharField("Flow 稳定ID", max_length=64)
    flow_name = models.CharField("V4 Flow 名称", max_length=128)
    strategy = models.CharField("部署策略", max_length=32, default=RecordRuleV4DeploymentStrategy.PER_RECORD.value)
    table_id = models.CharField("输出结果表", max_length=128)
    dst_vm_table_id = models.CharField("输出 VM RT", max_length=128)
    flow_config = JsonField("V4 Flow 配置", default=dict)
    content_hash = models.CharField("Flow 内容指纹", max_length=64)
    desired_status = models.CharField("期望状态", max_length=32, default=RecordRuleV4DesiredStatus.RUNNING.value)
    flow_status = models.CharField("Flow 实际状态", max_length=32, blank=True, default="")
    last_observed_at = models.DateTimeField("最近观测时间", null=True, blank=True)

    class Meta:
        verbose_name = "V4 预计算 Flow"
        verbose_name_plural = "V4 预计算 Flow"
        unique_together = (("resolved", "flow_key"),)
        ordering = ("id",)

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
        deployment_id: int | None
        flow_id: int | None

    rule = models.ForeignKey(RecordRuleV4, verbose_name="预计算规则组", related_name="events", on_delete=models.CASCADE)
    spec = models.ForeignKey(
        RecordRuleV4Spec, verbose_name="用户声明快照", null=True, blank=True, on_delete=models.SET_NULL
    )
    resolved = models.ForeignKey(
        RecordRuleV4Resolved, verbose_name="解析快照", null=True, blank=True, on_delete=models.SET_NULL
    )
    deployment = models.ForeignKey(
        RecordRuleV4Deployment, verbose_name="部署计划", null=True, blank=True, on_delete=models.SET_NULL
    )
    flow = models.ForeignKey(RecordRuleV4Flow, verbose_name="Flow", null=True, blank=True, on_delete=models.SET_NULL)
    generation = models.IntegerField("用户声明版本", default=0)
    event_type = models.CharField("事件类型", max_length=64)
    status = models.CharField("事件状态", max_length=32)
    source = models.CharField("来源", max_length=32, default="system")
    operator = models.CharField("操作人", max_length=128, blank=True, default="")
    reason = models.CharField("原因", max_length=128, blank=True, default="")
    message = models.TextField("消息", blank=True, default="")
    detail = JsonField("详情", default=dict)

    class Meta:
        verbose_name = "V4 预计算事件"
        verbose_name_plural = "V4 预计算事件"
        index_together = (("rule", "generation"), ("rule", "event_type"))

    def clean(self) -> None:
        """保存前统一校验事件类型、状态、关联对象和 detail 字段。"""

        self.validate_event_payload(
            event_type=self.event_type,
            status=self.status,
            reason=self.reason,
            spec=self.spec,
            resolved=self.resolved,
            deployment=self.deployment,
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
    def record_deployment_planned(
        cls,
        rule: RecordRuleV4,
        deployment: RecordRuleV4Deployment,
        source: str,
        operator: str,
        unchanged: bool = False,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            event_type=EVENT_TYPE_DEPLOYMENT_UNCHANGED if unchanged else EVENT_TYPE_DEPLOYMENT_PLANNED,
            status=EVENT_STATUS_SKIPPED if unchanged else EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_apply_started(
        cls, rule: RecordRuleV4, deployment: RecordRuleV4Deployment, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            event_type=EVENT_TYPE_APPLY_STARTED,
            status=EVENT_STATUS_STARTED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_apply_succeeded(
        cls, rule: RecordRuleV4, deployment: RecordRuleV4Deployment, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            event_type=EVENT_TYPE_APPLY_SUCCEEDED,
            status=EVENT_STATUS_SUCCEEDED,
            source=source,
            operator=operator,
        )

    @classmethod
    def record_apply_failed(
        cls,
        rule: RecordRuleV4,
        deployment: RecordRuleV4Deployment | None,
        source: str,
        operator: str,
        message: str,
        flow: RecordRuleV4Flow | None = None,
        stale: bool = False,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec if deployment else None,
            resolved=deployment.resolved if deployment else None,
            deployment=deployment,
            flow=flow,
            event_type=EVENT_TYPE_APPLY_FAILED,
            status=EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_STALE_DEPLOYMENT if stale else EVENT_REASON_APPLY_FAILED,
            message=message,
        )

    @classmethod
    def record_apply_failed_missing_deployment(
        cls, rule: RecordRuleV4, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            event_type=EVENT_TYPE_APPLY_FAILED,
            status=EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_DEPLOYMENT_MISSING,
            message="latest deployment is missing",
        )

    @classmethod
    def record_apply_skipped_stale_deployment(
        cls, rule: RecordRuleV4, deployment: RecordRuleV4Deployment, source: str, operator: str
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            event_type=EVENT_TYPE_APPLY_SKIPPED,
            status=EVENT_STATUS_SKIPPED,
            source=source,
            operator=operator,
            reason=EVENT_REASON_STALE_DEPLOYMENT,
            detail={
                "deployment_id": deployment.pk,
                "latest_deployment_id": rule.latest_deployment_id,
                "current_generation": rule.generation,
                "deployment_generation": deployment.generation,
            },
        )

    @classmethod
    def record_flow_action_started(
        cls,
        rule: RecordRuleV4,
        deployment: RecordRuleV4Deployment,
        flow: RecordRuleV4Flow,
        action_key: str,
        action_type: str,
        source: str,
        operator: str,
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_STARTED,
            status=EVENT_STATUS_STARTED,
            source=source,
            operator=operator,
            detail={"action_key": action_key, "action_type": action_type},
        )

    @classmethod
    def record_flow_action_result(
        cls,
        rule: RecordRuleV4,
        deployment: RecordRuleV4Deployment,
        flow: RecordRuleV4Flow,
        action_key: str,
        action_type: str,
        succeeded: bool,
        source: str,
        operator: str,
        message: str = "",
    ) -> RecordRuleV4Event:
        return cls.record(
            rule=rule,
            spec=deployment.spec,
            resolved=deployment.resolved,
            deployment=deployment,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_SUCCEEDED if succeeded else EVENT_TYPE_FLOW_ACTION_FAILED,
            status=EVENT_STATUS_SUCCEEDED if succeeded else EVENT_STATUS_FAILED,
            source=source,
            operator=operator,
            reason="" if succeeded else EVENT_REASON_APPLY_FAILED,
            message=message,
            detail={"action_key": action_key, "action_type": action_type},
        )

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
            deployment=rule.applied_deployment,
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
        deployment: RecordRuleV4Deployment | None = None,
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
            deployment=deployment,
            flow=flow,
            detail=detail,
        )
        generation = (
            spec.generation
            if spec
            else resolved.generation
            if resolved
            else deployment.generation
            if deployment
            else rule.generation
        )
        return cls.objects.create(
            rule=rule,
            spec=spec,
            resolved=resolved,
            deployment=deployment,
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
        deployment: RecordRuleV4Deployment | None,
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
            ("deployment", deployment),
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
