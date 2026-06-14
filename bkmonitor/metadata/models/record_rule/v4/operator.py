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
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

from django.db import transaction

from bkmonitor.utils.tenant import space_uid_to_bk_tenant_id
from metadata.models.record_rule.constants import (
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
)
from metadata.models.record_rule.v4.models import (
    CONDITION_FALSE,
    CONDITION_FLOW_READY,
    CONDITION_RECONCILED,
    RECORD_RULE_V4_TABLE_ID_SUFFIX,
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Resolved,
    RecordRuleV4Spec,
    normalize_labels,
    stable_hash,
)
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver
from metadata.models.record_rule.v4.runner import RecordRuleV4Runner
from metadata.models.record_rule.v4.spec import RecordRuleV4SpecBuilder
from metadata.models.record_rule.v4.types import RecordRuleV4RecordInput

T = TypeVar("T")
logger = logging.getLogger("metadata")


@dataclass
class RecordRuleV4DeclarationExecutionResult:
    """声明执行链路的内部结果，公开方法按各自语义折叠成 bool。"""

    resolved: RecordRuleV4Resolved | None = None
    resolved_changed: bool = False
    flow_prepared: bool = False
    apply_attempted: bool = False
    apply_succeeded: bool = False
    succeeded: bool = True

    @property
    def changed(self) -> bool:
        return self.resolved_changed or self.flow_prepared


class RecordRuleV4Operator:
    """串联 V4 预计算 group 的声明态、解析态和部署态。

    Operator 只负责流程编排和操作锁，不直接拼 Flow 配置，也不直接解释
    unify-query 响应。具体解析与部署细节分别交给 Resolver 和
    RecordRuleV4Runner。

    入口语义分两层：
    * declare / update_declaration 只落声明数据，没有外部副作用；
    * execute_declaration / reconcile 是执行链路，会先 ensure output，再
      resolve 和 prepare flow，最后按 auto_apply 决定是否 apply Flow。
    """

    def __init__(self, rule: RecordRuleV4, source: str = "system", operator: str = "") -> None:
        self.rule = rule
        self.source = source
        self.operator = operator

    @property
    def actor(self) -> str:
        return self.operator or self.source

    @property
    def spec_builder(self) -> RecordRuleV4SpecBuilder:
        return RecordRuleV4SpecBuilder(self.rule, source=self.source, operator=self.operator)

    @property
    def resolver(self) -> RecordRuleV4Resolver:
        return RecordRuleV4Resolver(self.rule, source=self.source, operator=self.operator)

    @property
    def runner(self) -> RecordRuleV4Runner:
        return RecordRuleV4Runner(self.rule, source=self.source, operator=self.operator)

    @staticmethod
    def compose_raw_config_snapshot(
        *,
        records: list[RecordRuleV4RecordInput],
        interval: str,
        labels: list[dict[str, Any]],
        description: str = "",
        data_label: str = "",
        raw_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成 spec.raw_config 快照。

        raw_config 是调用方的原始完整配置，只有在 spec 因规范字段变化而
        新建时才会被保存；调用方不传时落一个由规范字段组成的最小快照。
        """

        if raw_config is not None:
            return copy.deepcopy(raw_config)
        return {
            "records": copy.deepcopy(records),
            "interval": interval,
            "labels": copy.deepcopy(labels),
            "description": description,
            "data_label": data_label,
        }

    def reload_rule(self, for_update: bool = False) -> RecordRuleV4:
        """重新加载 rule；需要互斥写入时可带行锁。"""

        queryset = RecordRuleV4.objects
        if for_update:
            queryset = queryset.select_for_update()
        self.rule = queryset.get(pk=self.rule.pk)
        return self.rule

    def require_current_spec(self) -> RecordRuleV4Spec:
        """获取当前 spec，缺失时视为数据异常。"""

        spec = self.rule.current_spec
        if spec is None:
            raise ValueError("current spec is missing")
        return spec

    def has_unapplied_resolved(self) -> bool:
        """内部判断当前 latest resolved 是否尚未成功下发。"""

        latest_resolved = self.rule.get_latest_resolved()
        return bool(latest_resolved and latest_resolved.pk != self.rule.applied_resolved_id)

    @staticmethod
    def validate_initial_desired_status(desired_status: str) -> None:
        """声明创建只允许运行/停止；删除必须通过 delete_declaration 声明。"""

        allowed_statuses = {RecordRuleV4DesiredStatus.RUNNING.value, RecordRuleV4DesiredStatus.STOPPED.value}
        if desired_status not in allowed_statuses:
            raise ValueError(f"unsupported desired_status: {desired_status}")

    def run_with_operation_lock(self, reason: str, callback: Callable[[], T], locked_result: T) -> T:
        """围绕关键下发 / 刷新操作加轻量操作锁，避免后台与手动操作竞态。"""

        token = self.rule.acquire_operation_lock(owner=self.actor, reason=reason)
        if not token:
            self.reload_rule()
            RecordRuleV4Event.record_operation_locked(
                self.rule, operation=reason, source=self.source, operator=self.operator
            )
            return locked_result

        try:
            self.reload_rule()
            return callback()
        finally:
            self.rule.release_operation_lock(token)

    @classmethod
    def declare(
        cls,
        *,
        space_type: str,
        space_id: str,
        name: str,
        records: list[RecordRuleV4RecordInput],
        raw_config: dict[str, Any] | None = None,
        description: str = "",
        data_label: str = "",
        interval: str = "1min",
        labels: list[dict[str, Any]] | None = None,
        bk_tenant_id: str | None = None,
        desired_status: str = RecordRuleV4DesiredStatus.RUNNING.value,
        auto_refresh: bool = True,
        source: str = "user",
        operator: str = "",
    ) -> RecordRuleV4:
        """创建一份声明态 group。

        声明阶段只写 RecordRuleV4 / Spec / SpecRecord / raw_config / event；
        不做输出资源准备、不调用 unify-query、不创建 Flow、不下发 bkbase。
        """

        RecordRuleV4.validate_interval(interval)
        cls.validate_initial_desired_status(desired_status)
        group_labels = normalize_labels(labels)
        name = str(name or "")
        description = str(description or "")
        data_label = str(data_label or "")
        bk_tenant_id = bk_tenant_id or space_uid_to_bk_tenant_id(f"{space_type}__{space_id}")

        with transaction.atomic():
            temp_suffix = uuid4().hex
            rule = RecordRuleV4.objects.create(
                bk_tenant_id=bk_tenant_id,
                space_type=space_type,
                space_id=space_id,
                name=name,
                description=description,
                data_label=data_label,
                flow_name=f"pending_rr_{temp_suffix}",
                table_id=f"pending_rr_{temp_suffix}{RECORD_RULE_V4_TABLE_ID_SUFFIX}",
                dst_vm_table_id=f"pending_rr_{temp_suffix}",
                desired_status=desired_status,
                auto_refresh=auto_refresh,
                creator=operator or source,
                updater=operator or source,
            )
            table_id = RecordRuleV4.compose_table_id(pk=rule.pk, name=name)
            flow_name = RecordRuleV4.compose_group_flow_name(pk=rule.pk, name=name, table_id=table_id)
            result_table_config_name = RecordRuleV4OutputResources.compose_result_table_config_name(table_id)
            dst_vm_table_id = RecordRuleV4OutputResources.compose_vm_result_table_id(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=RecordRuleV4.resolve_bk_biz_id(space_type, space_id),
                result_table_config_name=result_table_config_name,
            )
            rule.table_id = table_id
            rule.flow_name = flow_name
            rule.dst_vm_table_id = dst_vm_table_id
            rule.save(update_fields=["table_id", "flow_name", "dst_vm_table_id", "updated_at"])

            instance = cls(rule, source=source, operator=operator)
            spec = instance.spec_builder.create_spec(
                records=records,
                raw_config=cls.compose_raw_config_snapshot(
                    records=records,
                    interval=interval,
                    labels=group_labels,
                    description=description,
                    data_label=data_label,
                    raw_config=raw_config,
                ),
                interval=interval,
                labels=group_labels,
            )
            rule.use_spec(spec)
            RecordRuleV4Event.record_user_create(rule, spec, source=source, operator=operator)
        return rule

    def update_declaration(
        self,
        *,
        records: list[RecordRuleV4RecordInput] | None = None,
        raw_config: dict[str, Any] | None = None,
        description: str | None = None,
        data_label: str | None = None,
        interval: str | None = None,
        labels: list[dict[str, Any]] | None = None,
        desired_status: str | None = None,
        auto_refresh: bool | None = None,
    ) -> RecordRuleV4:
        """更新声明态，不触发 resolve / flow / apply。

        records/interval/labels 的语义指纹变化才会创建新 spec；metadata、
        desired_status、auto_refresh 只更新 group 主表。
        """

        with transaction.atomic():
            self.reload_rule(for_update=True)
            current_spec = self.require_current_spec()
            next_records: list[RecordRuleV4RecordInput] = (
                RecordRuleV4SpecBuilder.dump_spec_records(current_spec) if records is None else list(records)
            )
            next_interval = current_spec.interval if interval is None else str(interval)
            if interval is not None:
                RecordRuleV4.validate_interval(next_interval)
            next_labels = copy.deepcopy(current_spec.labels) if labels is None else normalize_labels(labels)

            requested_desired_status = None if desired_status is None else str(desired_status)
            if requested_desired_status is not None:
                RecordRuleV4.validate_desired_status(requested_desired_status)

            metadata_changed_fields: list[str] = []
            if description is not None and str(description) != self.rule.description:
                self.rule.description = str(description)
                metadata_changed_fields.append("description")
            if data_label is not None and str(data_label) != self.rule.data_label:
                self.rule.data_label = str(data_label)
                metadata_changed_fields.append("data_label")

            auto_refresh_changed = auto_refresh is not None and bool(auto_refresh) != self.rule.auto_refresh
            if auto_refresh_changed:
                self.rule.auto_refresh = bool(auto_refresh)

            desired_status_changed = (
                requested_desired_status is not None and requested_desired_status != self.rule.desired_status
            )
            if desired_status_changed and requested_desired_status:
                self.rule.set_desired_status(requested_desired_status)
                RecordRuleV4Event.record_user_desired_status_changed(
                    self.rule, source=self.source, operator=self.operator
                )

            spec_fields_touched = records is not None or interval is not None or labels is not None
            next_content_hash = self.compose_spec_content_hash(
                records=next_records,
                interval=next_interval,
                labels=next_labels,
            )
            spec_changed = spec_fields_touched and next_content_hash != current_spec.content_hash

            if metadata_changed_fields or auto_refresh_changed:
                self.rule.sync_phase()
                update_fields = [*metadata_changed_fields, "status", "updated_at"]
                if auto_refresh_changed:
                    update_fields.append("auto_refresh")
                self.rule.save(update_fields=update_fields)

            if metadata_changed_fields:
                RecordRuleV4Event.record_user_metadata_changed(
                    self.rule,
                    source=self.source,
                    operator=self.operator,
                    changed_fields=metadata_changed_fields,
                )
            if auto_refresh_changed:
                RecordRuleV4Event.record_user_auto_refresh_changed(
                    self.rule, source=self.source, operator=self.operator
                )

            if spec_changed:
                changed_fields: list[str] = []
                if records is not None:
                    changed_fields.append("records")
                if interval is not None and next_interval != current_spec.interval:
                    changed_fields.append("interval")
                if labels is not None and next_labels != current_spec.labels:
                    changed_fields.append("labels")
                spec = self.spec_builder.create_spec(
                    records=next_records,
                    raw_config=self.compose_raw_config_snapshot(
                        records=next_records,
                        interval=next_interval,
                        labels=next_labels,
                        description=self.rule.description,
                        data_label=self.rule.data_label,
                        raw_config=raw_config,
                    ),
                    interval=next_interval,
                    labels=next_labels,
                )
                self.rule.use_spec(spec)
                RecordRuleV4Event.record_user_spec_changed(
                    self.rule,
                    spec,
                    source=self.source,
                    operator=self.operator,
                    changed_fields=changed_fields or ["records"],
                )
        self.reload_rule()
        return self.rule

    def delete_declaration(self) -> RecordRuleV4:
        """只声明删除，外部 Flow 由 execute_declaration / reconcile 执行删除。"""

        return self.update_declaration(desired_status=RecordRuleV4DesiredStatus.DELETED.value)

    def compose_spec_content_hash(
        self,
        *,
        records: list[RecordRuleV4RecordInput],
        interval: str,
        labels: list[dict[str, Any]],
    ) -> str:
        normalized_records = [self.spec_builder.normalize_record_payload(record) for record in records]
        return stable_hash(
            {
                "records": [RecordRuleV4SpecBuilder.record_content_payload(record) for record in normalized_records],
                "interval": interval,
                "labels": normalize_labels(labels),
            }
        )

    def refresh_resolved(self, force: bool = False) -> RecordRuleV4Resolved | None:
        """手动刷新解析结果；不准备输出、不准备 Flow、不下发。"""

        return self.run_with_operation_lock(
            "refresh_resolved",
            lambda: self._refresh_resolved_unlocked(force=force),
            None,
        )

    def _refresh_resolved_unlocked(self, force: bool = False) -> RecordRuleV4Resolved | None:
        return self.resolver.resolve_current(force=force)

    def execute_declaration(self, auto_apply: bool | None = True, force_output_apply: bool = False) -> bool:
        """执行当前声明：准备输出资源、resolve、准备 Flow，并按需 apply/delete。

        auto_apply 只控制 Flow 的 apply/delete，不阻止 output 资源准备。
        ensure_group_output 本身保持“必要时下发输出 RT / VM binding”的语义；
        force_output_apply=True 用于管理员显式重试 output 下发。
        """

        result = self.run_with_operation_lock(
            "execute_declaration",
            lambda: self._execute_declaration_unlocked(
                auto_apply=auto_apply,
                force_apply=True,
                force_output_apply=force_output_apply,
            ),
            RecordRuleV4DeclarationExecutionResult(succeeded=False),
        )
        return result.succeeded

    def reconcile(self, auto_apply: bool | None = None) -> bool:
        """后台调谐入口，复用声明执行链路，默认尊重 rule.auto_refresh。

        与 execute_declaration 一样，reconcile 会执行 output 准备；本地 output
        配置已存在时不会重复 apply。auto_apply=None 表示是否 apply Flow 由
        rule.auto_refresh 决定。
        """

        result = self.run_with_operation_lock(
            "reconcile",
            lambda: self._execute_declaration_unlocked(
                auto_apply=auto_apply,
                force_apply=False,
                force_output_apply=False,
            ),
            RecordRuleV4DeclarationExecutionResult(succeeded=False),
        )
        return result.changed or (result.apply_attempted and result.apply_succeeded)

    def _execute_declaration_unlocked(
        self,
        *,
        auto_apply: bool | None,
        force_apply: bool,
        force_output_apply: bool = False,
    ) -> RecordRuleV4DeclarationExecutionResult:
        result = RecordRuleV4DeclarationExecutionResult()
        self.reload_rule()
        # should_apply 只代表是否把当前目标 Flow 应用到 bkbase；output 准备
        # 是执行链路的一部分，不受这个布尔值影响。
        should_apply = self.rule.auto_refresh if auto_apply is None else bool(auto_apply)

        if self.rule.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            result.apply_attempted = True
            result.apply_succeeded = self.runner.apply()
            result.succeeded = result.apply_succeeded
            return result

        try:
            # prepare_output_resources 会确保输出侧 ResultTable / VM binding 的
            # 本地配置存在，并在首次缺失或强制重试时 apply output。
            self.prepare_output_resources(force_output_apply=force_output_apply)
        except Exception as err:  # pylint: disable=broad-except
            self.record_prepare_failure(
                condition_type=CONDITION_RECONCILED,
                reason="PrepareOutputFailed",
                err=err,
            )
            return RecordRuleV4DeclarationExecutionResult(succeeded=False)

        current_spec = self.require_current_spec()
        if (
            current_spec.latest_resolved_id
            and self.rule.applied_resolved_id == current_spec.latest_resolved_id
            and self.rule.desired_status != self.rule.applied_desired_status
        ):
            if should_apply:
                result.apply_attempted = True
                result.apply_succeeded = self.runner.apply_desired_status(self.rule.desired_status)
                result.succeeded = result.apply_succeeded
            return result

        previous_resolved_id = current_spec.latest_resolved_id
        resolved = self._refresh_resolved_unlocked(force=False)
        result.resolved = resolved
        if resolved is None:
            result.succeeded = False
            return result
        result.resolved_changed = resolved.pk != previous_resolved_id

        self.reload_rule()
        latest_flow = self.rule.get_latest_flow()
        if latest_flow is None or latest_flow.resolved_id != resolved.pk:
            try:
                flow = self.runner.prepare_flow(resolved=resolved)
            except Exception as err:  # pylint: disable=broad-except
                self.record_prepare_failure(
                    condition_type=CONDITION_FLOW_READY,
                    reason="FlowPrepareFailed",
                    err=err,
                )
                return RecordRuleV4DeclarationExecutionResult(resolved=resolved, succeeded=False)
            result.flow_prepared = flow is not None

        self.reload_rule()
        if not should_apply:
            # 到这里说明 output、resolved、flow 快照都已准备好，但调用方希望
            # 先停在“可下发”状态，等待后续 execute_declaration(auto_apply=True)。
            return result

        if self.has_unapplied_resolved():
            result.apply_attempted = True
            result.apply_succeeded = self.runner.apply()
            result.succeeded = result.apply_succeeded
        elif self.rule.desired_status != self.rule.applied_desired_status:
            result.apply_attempted = True
            result.apply_succeeded = self.runner.apply_desired_status(self.rule.desired_status)
            result.succeeded = result.apply_succeeded
        elif force_apply:
            result.apply_attempted = True
            result.apply_succeeded = self.runner.apply()
            result.succeeded = result.apply_succeeded
        return result

    def prepare_output_resources(self, force_output_apply: bool = False) -> None:
        """准备 output RT / VM binding / metric fields，并刷新必要的 Redis 路由。

        这里的 ensure_group_output 会在必要时下发 output 侧 bkbase 资源；本地
        配置已存在时跳过重复 apply。metric fields 仍只维护本地 metadata，
        供查询路由和导出查看使用。
        """

        from metadata import models as metadata_models

        current_spec = self.require_current_spec()
        output_table = metadata_models.ResultTable.objects.filter(
            table_id=self.rule.table_id,
            bk_tenant_id=self.rule.bk_tenant_id,
        ).first()
        previous_data_label = output_table.data_label if output_table else ""
        output_created = RecordRuleV4OutputResources.ensure_group_output(
            self.rule,
            force_apply=force_output_apply,
        )
        self.reload_rule()
        metric_fields_created = RecordRuleV4OutputResources.ensure_spec_metric_fields(self.rule, current_spec)
        output_detail_changed = bool(self.rule.data_label and previous_data_label != self.rule.data_label)
        if output_created:
            RecordRuleV4OutputResources.push_output_route(self.rule)
        elif metric_fields_created or output_detail_changed:
            RecordRuleV4OutputResources.push_table_id_detail(self.rule)

    def record_prepare_failure(self, *, condition_type: str, reason: str, err: Exception) -> None:
        """执行准备阶段失败时只写 condition，不回滚已经提交的声明。"""

        self.reload_rule()
        self.rule.set_condition(condition_type, CONDITION_FALSE, reason, str(err))
        self.rule.sync_phase()
        self.rule.save(update_fields=["conditions", "status", "updated_at"])
        logger.exception("RecordRuleV4 declaration execute failed, id: %s, reason: %s", self.rule.pk, reason)

    def refresh_flow_health(self) -> str:
        """观测 applied flow 对应的实际状态。"""

        return self.run_with_operation_lock(
            "refresh_flow_health",
            self.runner.refresh_flow_health,
            RecordRuleV4FlowStatus.ABNORMAL.value,
        )
