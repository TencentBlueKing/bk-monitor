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
from typing import Any

from core.drf_resource import api
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_BKBASE_NAMESPACE,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowActionType,
    RecordRuleV4FlowStatus,
)
from metadata.models.record_rule.v4.models import (
    CONDITION_FALSE,
    CONDITION_FLOW_HEALTHY,
    CONDITION_RECONCILED,
    CONDITION_TRUE,
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Flow,
    RecordRuleV4Resolved,
    now,
)

logger = logging.getLogger("metadata")


class RecordRuleV4Runner:
    """维护单个目标 Flow，并负责 apply / delete / observe。

    Runner 不解释用户 spec，也不调用 unify-query；它只消费 resolved 快照，
    生成唯一的目标 Flow，并把这个 Flow 下发到 bkbase。
    """

    def __init__(self, rule: RecordRuleV4, source: str = "system", operator: str = "") -> None:
        self.rule = rule
        self.source = source
        self.operator = operator

    @property
    def actor(self) -> str:
        return self.operator or self.source

    def reload_rule(self, for_update: bool = False) -> RecordRuleV4:
        """重新加载 rule，避免长流程中沿用旧指针。"""

        queryset = RecordRuleV4.objects
        if for_update:
            queryset = queryset.select_for_update()
        self.rule = queryset.get(pk=self.rule.pk)
        return self.rule

    def prepare_flow(self, resolved: RecordRuleV4Resolved | None = None) -> RecordRuleV4Flow | None:
        """将 resolved 快照持久化成唯一目标 Flow。"""

        self.reload_rule()
        resolved = resolved or self.rule.get_latest_resolved()
        if resolved is None:
            return None

        flow_payload = RecordRuleV4Flow.compose_for_resolved(rule=self.rule, resolved=resolved)
        flow, _ = RecordRuleV4Flow.objects.update_or_create(
            resolved=resolved,
            defaults={
                "rule": self.rule,
                "bk_tenant_id": self.rule.bk_tenant_id,
                "flow_name": flow_payload["flow_name"],
                "flow_config": self.with_desired_status(flow_payload["flow_config"], self.rule.desired_status),
                "content_hash": flow_payload["content_hash"],
                "creator": self.actor,
                "updater": self.actor,
            },
        )
        self.rule.mark_flow_ready(flow)
        return flow

    def apply(self) -> bool:
        """执行当前声明：普通配置下发 latest Flow，删除声明则删除 applied Flow。"""

        self.reload_rule()
        if self.rule.desired_status == RecordRuleV4DesiredStatus.DELETED.value:
            return self.delete_applied_flow()

        flow = self.rule.get_latest_flow()
        resolved = self.rule.get_latest_resolved()
        if flow is None and resolved:
            flow = self.prepare_flow(resolved)
        if flow is None:
            self.rule.set_condition(CONDITION_RECONCILED, CONDITION_FALSE, "FlowMissing")
            self.rule.sync_phase()
            self.rule.save(update_fields=["conditions", "status", "updated_at"])
            RecordRuleV4Event.record_apply_failed_missing_flow(self.rule, source=self.source, operator=self.operator)
            return False
        if not self.is_flow_current(flow):
            RecordRuleV4Event.record_apply_skipped_stale_flow(
                self.rule, flow, source=self.source, operator=self.operator
            )
            return False

        applied_resolved = self.rule.applied_resolved
        action_type = (
            RecordRuleV4FlowActionType.CREATE.value
            if applied_resolved is None
            else RecordRuleV4FlowActionType.UPDATE.value
        )
        return self.apply_target_flow(flow=flow, action_type=action_type)

    def apply_target_flow(self, *, flow: RecordRuleV4Flow, action_type: str) -> bool:
        """下发 create/update，并用事件记录完整执行过程。"""

        RecordRuleV4Event.record_apply_started(self.rule, flow, source=self.source, operator=self.operator)
        RecordRuleV4Event.record_flow_action_started(
            self.rule, flow, action_type=action_type, source=self.source, operator=self.operator
        )
        try:
            flow_config = self.with_desired_status(flow.flow_config, self.rule.desired_status)
            self.apply_flow(flow_config)
            flow.flow_config = flow_config
            flow.save(update_fields=["flow_config", "updated_at"])
        except Exception as err:
            self.mark_apply_failed(flow=flow, err=err)
            RecordRuleV4Event.record_flow_action_result(
                self.rule,
                flow,
                action_type=action_type,
                succeeded=False,
                source=self.source,
                operator=self.operator,
                message=str(err),
            )
            logger.exception("RecordRuleV4 apply flow failed, id: %s, flow_id: %s", self.rule.pk, flow.pk)
            return False

        RecordRuleV4Event.record_flow_action_result(
            self.rule,
            flow,
            action_type=action_type,
            succeeded=True,
            source=self.source,
            operator=self.operator,
        )
        self.rule.mark_flow_applied(flow)
        RecordRuleV4Event.record_apply_succeeded(self.rule, flow, source=self.source, operator=self.operator)
        return True

    def delete_applied_flow(self) -> bool:
        """删除当前已经成功下发的 Flow。"""

        flow = self.rule.get_applied_flow()
        RecordRuleV4Event.record_apply_started(self.rule, flow, source=self.source, operator=self.operator)
        if flow is None:
            self.rule.mark_delete_applied()
            RecordRuleV4Event.record_apply_succeeded(self.rule, None, source=self.source, operator=self.operator)
            return True

        action_type = RecordRuleV4FlowActionType.DELETE.value
        RecordRuleV4Event.record_flow_action_started(
            self.rule, flow, action_type=action_type, source=self.source, operator=self.operator
        )
        try:
            self.delete_flow(self.rule.flow_name, ignore_not_found=True)
        except Exception as err:
            self.mark_apply_failed(flow=flow, err=err)
            RecordRuleV4Event.record_flow_action_result(
                self.rule,
                flow,
                action_type=action_type,
                succeeded=False,
                source=self.source,
                operator=self.operator,
                message=str(err),
            )
            logger.exception("RecordRuleV4 delete flow failed, id: %s, flow_id: %s", self.rule.pk, flow.pk)
            return False

        RecordRuleV4Event.record_flow_action_result(
            self.rule,
            flow,
            action_type=action_type,
            succeeded=True,
            source=self.source,
            operator=self.operator,
        )
        self.rule.mark_delete_applied()
        RecordRuleV4Event.record_apply_succeeded(self.rule, flow, source=self.source, operator=self.operator)
        return True

    def mark_apply_failed(self, *, flow: RecordRuleV4Flow | None, err: Exception | str) -> None:
        """把下发失败同步到 group 当前状态。"""

        self.rule.set_condition(CONDITION_RECONCILED, CONDITION_FALSE, "ApplyFailed", str(err))
        self.rule.sync_phase()
        self.rule.save(update_fields=["conditions", "status", "updated_at"])
        RecordRuleV4Event.record_apply_failed(
            self.rule,
            source=self.source,
            operator=self.operator,
            message=str(err),
            flow=flow,
        )

    def apply_desired_status(self, desired_status: str) -> bool:
        """直接下发 running/stopped 运行态，不生成新的 resolved/flow。"""

        self.reload_rule()
        flow = self.rule.get_applied_flow()
        if flow is None:
            self.rule.set_condition(CONDITION_RECONCILED, CONDITION_FALSE, "FlowMissing")
            self.rule.sync_phase()
            self.rule.save(update_fields=["conditions", "status", "updated_at"])
            RecordRuleV4Event.record_apply_failed_missing_flow(self.rule, source=self.source, operator=self.operator)
            return False

        action_type = self.compose_runtime_action_type(desired_status)
        RecordRuleV4Event.record_apply_started(self.rule, flow, source=self.source, operator=self.operator)
        RecordRuleV4Event.record_flow_action_started(
            self.rule, flow, action_type=action_type, source=self.source, operator=self.operator
        )
        try:
            flow_config = self.with_desired_status(flow.flow_config, desired_status)
            self.apply_flow(flow_config)
            flow.flow_config = flow_config
            flow.save(update_fields=["flow_config", "updated_at"])
        except Exception as err:
            self.mark_apply_failed(flow=flow, err=err)
            RecordRuleV4Event.record_flow_action_result(
                self.rule,
                flow,
                action_type=action_type,
                succeeded=False,
                source=self.source,
                operator=self.operator,
                message=str(err),
            )
            logger.exception("RecordRuleV4 apply desired status failed, id: %s", self.rule.pk)
            return False

        RecordRuleV4Event.record_flow_action_result(
            self.rule,
            flow,
            action_type=action_type,
            succeeded=True,
            source=self.source,
            operator=self.operator,
        )
        self.rule.mark_desired_status_applied(desired_status)
        RecordRuleV4Event.record_apply_succeeded(self.rule, flow, source=self.source, operator=self.operator)
        return True

    @staticmethod
    def compose_runtime_action_type(desired_status: str) -> str:
        """把 running/stopped 运行态映射成事件中的 Flow action 类型。"""

        if desired_status == RecordRuleV4DesiredStatus.STOPPED.value:
            return RecordRuleV4FlowActionType.STOP.value
        return RecordRuleV4FlowActionType.START.value

    @staticmethod
    def with_desired_status(flow_config: dict[str, Any], desired_status: str) -> dict[str, Any]:
        """给 Flow 配置注入运行态 desired_status，并保持原配置不可变。"""

        next_config = copy.deepcopy(flow_config)
        next_config.setdefault("spec", {})["desired_status"] = desired_status
        return next_config

    def is_flow_current(self, flow: RecordRuleV4Flow) -> bool:
        """确认待下发 Flow 仍是当前声明对应的 latest flow。"""

        self.reload_rule()
        current_spec = self.rule.current_spec
        if current_spec is None:
            return False
        return (
            self.rule.current_spec_id == flow.resolved.spec_id
            and current_spec.latest_resolved_id == flow.resolved_id
            and self.rule.generation == flow.resolved.generation
        )

    def apply_flow(self, flow_config: dict[str, Any]) -> Any:
        """调用 bkbase v4 apply 接口创建或更新 Flow。

        这里只提交 Flow payload；output ResultTable / VmStorageBinding 已在
        Operator.prepare_output_resources 阶段由 RecordRuleV4OutputResources 下发。
        """

        response = api.bkdata.apply_data_link(bk_tenant_id=self.rule.bk_tenant_id, config=[flow_config])
        self.rule.last_refresh_time = now()
        return response

    def delete_flow(self, flow_name: str, ignore_not_found: bool = False) -> Any:
        """调用 bkbase 删除 Flow；可把 Not Found 视为删除成功。"""

        try:
            return api.bkdata.delete_data_link(
                bk_tenant_id=self.rule.bk_tenant_id,
                namespace=RECORD_RULE_V4_BKBASE_NAMESPACE,
                kind="flows",
                name=flow_name,
            )
        except Exception as err:
            if ignore_not_found and self.is_not_found_error(err):
                return {"status": RecordRuleV4FlowStatus.NOT_FOUND.value}
            raise

    def refresh_flow_health(self) -> str:
        """观测 applied Flow 的实际状态并同步到 group condition。"""

        self.reload_rule()
        flow = self.rule.get_applied_flow()
        if flow is None:
            self.rule.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_FALSE, "FlowMissing")
            self.rule.sync_phase()
            self.rule.save(update_fields=["conditions", "status", "updated_at"])
            return RecordRuleV4FlowStatus.ABNORMAL.value

        try:
            flow_info = api.bkdata.get_data_link(
                bk_tenant_id=self.rule.bk_tenant_id,
                namespace=RECORD_RULE_V4_BKBASE_NAMESPACE,
                kind="flows",
                name=flow.flow_name,
            )
            status = self.extract_flow_status(flow_info or {})
            message = ""
            observe_succeeded = status == RecordRuleV4FlowStatus.OK.value
        except Exception as err:
            status = (
                RecordRuleV4FlowStatus.NOT_FOUND.value
                if self.is_not_found_error(err)
                else RecordRuleV4FlowStatus.ABNORMAL.value
            )
            message = str(err)
            observe_succeeded = False

        flow.mark_flow_observed(status)
        RecordRuleV4Event.record_flow_observed(
            self.rule,
            status,
            source=self.source,
            operator=self.operator,
            flow=flow,
            message=message,
            observe_succeeded=observe_succeeded,
        )

        condition_status = CONDITION_TRUE if status == RecordRuleV4FlowStatus.OK.value else CONDITION_FALSE
        self.rule.set_condition(CONDITION_FLOW_HEALTHY, condition_status, status)
        self.rule.sync_phase()
        self.rule.save(update_fields=["conditions", "status", "updated_at"])
        return status

    @staticmethod
    def is_not_found_error(err: Exception) -> bool:
        """粗略识别 bkbase Not Found 类错误。"""

        message = str(err).lower()
        return "not found" in message or "404" in message

    @staticmethod
    def extract_flow_status(flow_info: dict[str, Any]) -> str:
        """把 bkbase 返回的多种状态结构归一成 ok / abnormal。"""

        status_info = flow_info.get("status") or {}
        if isinstance(status_info, str):
            return (
                RecordRuleV4FlowStatus.OK.value
                if status_info.lower() == "ok"
                else RecordRuleV4FlowStatus.ABNORMAL.value
            )
        if isinstance(status_info, dict):
            for key in ["status", "phase", "state"]:
                value = status_info.get(key)
                if value:
                    return (
                        RecordRuleV4FlowStatus.OK.value
                        if str(value).lower() == "ok"
                        else RecordRuleV4FlowStatus.ABNORMAL.value
                    )
        return RecordRuleV4FlowStatus.ABNORMAL.value
