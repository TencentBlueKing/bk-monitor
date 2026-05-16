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
from collections.abc import Callable
from typing import Any, TypeVar
from uuid import uuid4

from django.db import transaction

from bkmonitor.utils.tenant import space_uid_to_bk_tenant_id
from metadata.models.record_rule.constants import (
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
)
from metadata.models.record_rule.v4.models import (
    RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH,
    RECORD_RULE_V4_TABLE_ID_SUFFIX,
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Resolved,
    RecordRuleV4Spec,
    normalize_labels,
)
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver
from metadata.models.record_rule.v4.runner import RecordRuleV4Runner
from metadata.models.record_rule.v4.spec import RecordRuleV4SpecBuilder
from metadata.models.record_rule.v4.types import RecordRuleV4RecordInput

T = TypeVar("T")


class RecordRuleV4Operator:
    """串联 V4 预计算 group 的声明态、解析态和部署态。

    Operator 只负责流程编排和操作锁，不直接拼 Flow 配置，也不直接解释
    unify-query 响应。具体解析与部署细节分别交给 Resolver 和
    RecordRuleV4Runner。
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
    def create(
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
        auto_refresh: bool = True,
        source: str = "user",
        operator: str = "",
        apply_immediately: bool = True,
    ) -> RecordRuleV4:
        """创建 group，并按 create -> resolve -> flow -> apply 的顺序初始化。

        raw_config 是调用方提交的完整原始配置快照，主要用于审计、回显和
        排查；执行链路只消费 records / interval / labels 这些规范字段。
        """

        RecordRuleV4.validate_interval(interval)
        group_labels = normalize_labels(labels)
        name = str(name or "")
        description = str(description or "")
        data_label = str(data_label or "")
        bk_tenant_id = bk_tenant_id or space_uid_to_bk_tenant_id(f"{space_type}__{space_id}")
        output_created = False
        metric_fields_created = False

        with transaction.atomic():
            temp_suffix = uuid4().hex[:RECORD_RULE_V4_NAME_RANDOM_SUFFIX_LENGTH]
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
            # 输出 RT / VM 映射是 group 级资源，创建 rule 后立刻准备，
            # 避免等到第一次 apply 才补 metadata。
            output_created = RecordRuleV4OutputResources.ensure_group_output(rule)
            instance = cls(rule, source=source, operator=operator)
            # 调用方不传 raw_config 时，保存一份由规范字段组成的最小快照；
            # 这样 spec.raw_config 永远可用于回看“用户当时提交了什么”。
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
            metric_fields_created = RecordRuleV4OutputResources.ensure_spec_metric_fields(rule, spec)
            RecordRuleV4Event.record_user_create(rule, spec, source=source, operator=operator)

        # 路由刷新必须在事务提交后执行，避免 Redis 读取到未提交或回滚的数据。
        if output_created:
            RecordRuleV4OutputResources.push_output_route(rule)
        elif metric_fields_created:
            RecordRuleV4OutputResources.push_table_id_detail(rule)

        resolved = instance.resolver.resolve_current(force=True)
        if resolved:
            instance.runner.prepare_flow(resolved=resolved)
        if apply_immediately and resolved:
            instance.apply()
        instance.rule.refresh_from_db()
        return instance.rule

    def update_spec(
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
        apply_immediately: bool = True,
    ) -> RecordRuleV4:
        """更新用户声明或运行态。

        records/interval/labels 会进入新的 spec/resolved/flow 链路；
        running/stopped/deleted 只改变 group 运行态 desired_status，
        不推进 generation。删除通过 runner 直接删除当前 applied Flow。
        raw_config 本身不是 resolver 的输入真值源，只在创建新 spec 时
        作为原始配置快照保存；单独传 raw_config 不会推进 generation。
        """

        spec: RecordRuleV4Spec | None = None
        records_changed = False
        desired_status_changed = False
        requested_desired_status: str | None = None
        previous_resolved_id: int | None = None
        output_created = False
        output_detail_changed = False
        metric_fields_created = False

        with transaction.atomic():
            self.reload_rule(for_update=True)
            current_spec = self.require_current_spec()
            previous_resolved_id = current_spec.latest_resolved_id
            # 先把所有输入归一成下一份声明需要的候选值，后面再判断哪些是真正
            # 的定义态变更，哪些只是运行态启停。
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

            records_changed = records is not None
            interval_changed = interval is not None and next_interval != current_spec.interval
            labels_changed = labels is not None and next_labels != current_spec.labels
            desired_status_changed = (
                requested_desired_status is not None and requested_desired_status != self.rule.desired_status
            )
            if desired_status_changed and requested_desired_status:
                # 运行态不生成 spec，因此事件也不挂 spec/resolved/flow。
                self.rule.set_desired_status(requested_desired_status)
                RecordRuleV4Event.record_user_desired_status_changed(
                    self.rule, source=self.source, operator=self.operator
                )

            result_table_metadata_changed = bool("data_label" in metadata_changed_fields and self.rule.data_label)
            if metadata_changed_fields:
                self.rule.sync_phase()
                self.rule.save(update_fields=[*metadata_changed_fields, "status", "updated_at"])
                RecordRuleV4Event.record_user_metadata_changed(
                    self.rule,
                    source=self.source,
                    operator=self.operator,
                    changed_fields=metadata_changed_fields,
                )

            changed_fields: list[str] = []
            if records_changed:
                changed_fields.append("records")
            if interval_changed:
                changed_fields.append("interval")
            if labels_changed:
                changed_fields.append("labels")

            if not changed_fields:
                if auto_refresh_changed:
                    self.rule.sync_phase()
                    self.rule.save(update_fields=["auto_refresh", "status", "updated_at"])
                    RecordRuleV4Event.record_user_auto_refresh_changed(
                        self.rule, source=self.source, operator=self.operator
                    )
                if result_table_metadata_changed:
                    RecordRuleV4OutputResources.ensure_group_output(self.rule)
                    output_detail_changed = True
                if not desired_status_changed and not metadata_changed_fields:
                    return self.rule
            else:
                if auto_refresh_changed:
                    self.rule.save(update_fields=["auto_refresh", "updated_at"])
                    RecordRuleV4Event.record_user_auto_refresh_changed(
                        self.rule, source=self.source, operator=self.operator
                    )
                # 只有计算定义变化才创建新 spec。这样 stop/start 不会污染
                # generation 和后续 resolved 对比。
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
                output_created = RecordRuleV4OutputResources.ensure_group_output(self.rule)
                output_detail_changed = result_table_metadata_changed
                metric_fields_created = RecordRuleV4OutputResources.ensure_spec_metric_fields(self.rule, spec)
                RecordRuleV4Event.record_user_spec_changed(
                    self.rule,
                    spec,
                    source=self.source,
                    operator=self.operator,
                    changed_fields=changed_fields,
                )

        # 路由刷新放到事务外，保证 Redis 使用的是已提交后的 metadata。
        if output_created:
            RecordRuleV4OutputResources.push_output_route(self.rule)
        elif metric_fields_created or output_detail_changed:
            RecordRuleV4OutputResources.push_table_id_detail(self.rule)

        # 事务外执行外部 check / flow 准备，避免长时间持有数据库行锁。
        if spec and (records_changed or interval_changed or labels_changed):
            resolved = self.refresh_resolved(force=False)
            self.reload_rule()
            if resolved and resolved.pk != previous_resolved_id:
                self.runner.prepare_flow(resolved=resolved)

        self.reload_rule()
        if apply_immediately and (spec or desired_status_changed):
            if self.rule.desired_status == RecordRuleV4DesiredStatus.DELETED.value or self.has_unapplied_resolved():
                self.apply()
            elif desired_status_changed and requested_desired_status:
                # Runtime-only 的启停没有新 Flow，直接把 desired_status
                # 注入已落地的 Flow 配置并下发。
                self.runner.apply_desired_status(requested_desired_status)
        self.reload_rule()
        return self.rule

    def delete(self, apply_immediately: bool = True) -> RecordRuleV4:
        """声明删除 group，并删除已落地 Flow。"""

        return self.update_spec(
            desired_status=RecordRuleV4DesiredStatus.DELETED.value,
            apply_immediately=apply_immediately,
        )

    def manual_refresh(self) -> RecordRuleV4Resolved | None:
        """用户主动刷新解析结果；只标记待更新，不自动下发。"""

        return self.run_with_operation_lock(
            "manual_refresh",
            self.manual_refresh_unlocked,
            None,
        )

    def manual_refresh_unlocked(self) -> RecordRuleV4Resolved | None:
        """不带操作锁的手动刷新实现，便于 reconcile 复用相同语义。"""

        current_spec = self.require_current_spec()
        previous_resolved_id = current_spec.latest_resolved_id
        resolved = self.refresh_resolved(force=False)
        if resolved and resolved.pk != previous_resolved_id:
            self.reload_rule()
            self.runner.prepare_flow(resolved=resolved)
        return resolved

    def reconcile(self, auto_apply: bool | None = None) -> bool:
        """后台周期入口：检查 resolved 漂移，并按 auto_refresh 决定是否下发。"""

        return self.run_with_operation_lock(
            "reconcile",
            lambda: self.reconcile_unlocked(auto_apply=auto_apply),
            False,
        )

    def reconcile_unlocked(self, auto_apply: bool | None = None) -> bool:
        """不带操作锁的 reconcile 主流程。"""

        current_spec = self.require_current_spec()
        previous_resolved_id = current_spec.latest_resolved_id
        resolved = self.refresh_resolved(force=False)
        changed = bool(resolved and resolved.pk != previous_resolved_id)
        if changed and resolved:
            self.reload_rule()
            self.runner.prepare_flow(resolved=resolved)
        self.reload_rule()
        should_apply = self.rule.auto_refresh if auto_apply is None else auto_apply
        if should_apply and self.has_unapplied_resolved():
            self.runner.apply()
        return changed

    def refresh_resolved(self, force: bool = False) -> RecordRuleV4Resolved | None:
        """重新调用 Resolver，返回当前最新解析快照。"""

        return self.resolver.resolve_current(force=force)

    def apply(self) -> bool:
        """下发 latest flow，或按删除声明删除 applied flow。"""

        return self.run_with_operation_lock(
            "apply",
            self.runner.apply,
            False,
        )

    def refresh_flow_health(self) -> str:
        """观测 applied flow 对应的实际状态。"""

        return self.run_with_operation_lock(
            "refresh_flow_health",
            self.runner.refresh_flow_health,
            RecordRuleV4FlowStatus.ABNORMAL.value,
        )
