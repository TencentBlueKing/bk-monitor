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

from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    PAGE_LIST_TENANT_SCHEMA,
    SAFETY_LEVEL_WRITE,
    build_response,
    filter_by_bk_tenant_id,
    get_bk_tenant_id,
    get_page_list_bk_tenant_id,
    normalize_optional_bool,
    normalize_ordering,
    normalize_pagination,
    paginate_queryset,
    serialize_value,
)
from metadata.models.record_rule.constants import RecordRuleV4DesiredStatus
from metadata.models.record_rule.v4.models import (
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Flow,
    RecordRuleV4Resolved,
    RecordRuleV4ResolvedRecord,
    RecordRuleV4Spec,
    RecordRuleV4SpecRecord,
)
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator

FUNC_RECORD_RULE_V4_LIST = "admin.record_rule_v4.list"
FUNC_RECORD_RULE_V4_DETAIL = "admin.record_rule_v4.detail"
FUNC_RECORD_RULE_V4_VERSION_LIST = "admin.record_rule_v4.version_list"
FUNC_RECORD_RULE_V4_EVENT_LIST = "admin.record_rule_v4.event_list"
FUNC_RECORD_RULE_V4_MANUAL_REFRESH = "admin.record_rule_v4.manual_refresh"
FUNC_RECORD_RULE_V4_APPLY = "admin.record_rule_v4.apply"
FUNC_RECORD_RULE_V4_SET_DESIRED_STATUS = "admin.record_rule_v4.set_desired_status"
FUNC_RECORD_RULE_V4_REFRESH_FLOW_HEALTH = "admin.record_rule_v4.refresh_flow_health"

OPERATION_RECORD_RULE_V4_LIST = "record_rule_v4.list"
OPERATION_RECORD_RULE_V4_DETAIL = "record_rule_v4.detail"
OPERATION_RECORD_RULE_V4_VERSION_LIST = "record_rule_v4.version_list"
OPERATION_RECORD_RULE_V4_EVENT_LIST = "record_rule_v4.event_list"
OPERATION_RECORD_RULE_V4_MANUAL_REFRESH = "record_rule_v4.manual_refresh"
OPERATION_RECORD_RULE_V4_APPLY = "record_rule_v4.apply"
OPERATION_RECORD_RULE_V4_SET_DESIRED_STATUS = "record_rule_v4.set_desired_status"
OPERATION_RECORD_RULE_V4_REFRESH_FLOW_HEALTH = "record_rule_v4.refresh_flow_health"

RULE_ORDERING_FIELDS = {
    "id",
    "space_type",
    "space_id",
    "name",
    "table_id",
    "generation",
    "status",
    "desired_status",
    "last_check_time",
    "last_refresh_time",
    "updated_at",
    "created_at",
}
EVENT_ORDERING_FIELDS = {"id", "generation", "event_type", "status", "source", "created_at", "updated_at"}


def _normalize_int(value: Any, field_name: str, *, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数") from error


def _normalize_text(value: Any, field_name: str, *, required: bool = False) -> str | None:
    if value in (None, ""):
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    text = str(value).strip()
    if not text:
        if required:
            raise CustomException(message=f"{field_name} 为必填项")
        return None
    return text


def _normalize_desired_status(value: Any) -> str:
    desired_status = _normalize_text(value, "desired_status", required=True)
    allowed = {RecordRuleV4DesiredStatus.RUNNING.value, RecordRuleV4DesiredStatus.STOPPED.value}
    if desired_status not in allowed:
        raise CustomException(message="desired_status 只允许 running 或 stopped")
    return desired_status


def _serialize_time_fields(instance: Any) -> dict[str, Any]:
    return {
        "creator": getattr(instance, "creator", ""),
        "created_at": serialize_value(getattr(instance, "created_at", None)),
        "updater": getattr(instance, "updater", ""),
        "updated_at": serialize_value(getattr(instance, "updated_at", None)),
    }


def _serialize_rule(rule: RecordRuleV4) -> dict[str, Any]:
    latest_flow = rule.get_latest_flow()
    applied_flow = rule.get_applied_flow()
    return {
        **rule.to_dict(),
        "last_check_time": serialize_value(rule.last_check_time),
        "last_refresh_time": serialize_value(rule.last_refresh_time),
        "deleted_at": serialize_value(rule.deleted_at),
        "operation_lock_expires_at": serialize_value(rule.operation_lock_expires_at),
        "operation_lock": {
            "owner": rule.operation_lock_owner,
            "reason": rule.operation_lock_reason,
            "expires_at": serialize_value(rule.operation_lock_expires_at),
            "locked": bool(rule.operation_lock_token),
        },
        "latest_flow_id": latest_flow.pk if latest_flow else None,
        "applied_flow_id": applied_flow.pk if applied_flow else None,
        "latest_flow_status": latest_flow.flow_status if latest_flow else "",
        "applied_flow_status": applied_flow.flow_status if applied_flow else "",
        **_serialize_time_fields(rule),
    }


def _serialize_spec_record(record: RecordRuleV4SpecRecord) -> dict[str, Any]:
    return {
        "id": record.pk,
        "spec_id": record.spec_id,
        "record_key": record.record_key,
        "content_hash": record.content_hash,
        "source_index": record.source_index,
        "input_type": record.input_type,
        "input_config": record.input_config,
        "metric_name": record.metric_name,
        "labels": record.labels,
        **_serialize_time_fields(record),
    }


def _serialize_spec(spec: RecordRuleV4Spec | None, *, include_records: bool = False) -> dict[str, Any] | None:
    if spec is None:
        return None
    data = {
        "id": spec.pk,
        "rule_id": spec.rule_id,
        "bk_tenant_id": spec.bk_tenant_id,
        "generation": spec.generation,
        "raw_config": spec.raw_config,
        "interval": spec.interval,
        "labels": spec.labels,
        "content_hash": spec.content_hash,
        "source": spec.source,
        "operator": spec.operator,
        "latest_resolved_id": spec.latest_resolved_id,
        **_serialize_time_fields(spec),
    }
    if include_records:
        data["records"] = [_serialize_spec_record(record) for record in spec.get_records()]
    return data


def _serialize_resolved_record(record: RecordRuleV4ResolvedRecord) -> dict[str, Any]:
    return {
        "id": record.pk,
        "resolved_id": record.resolved_id,
        "spec_record_id": record.spec_record_id,
        "record_key": record.record_key,
        "content_hash": record.content_hash,
        "metricql": record.metricql,
        "labels": record.labels,
        "src_vm_table_ids": record.src_vm_table_ids,
        "src_result_table_configs": record.src_result_table_configs,
        **_serialize_time_fields(record),
    }


def _serialize_resolved(
    resolved: RecordRuleV4Resolved | None, *, include_records: bool = False
) -> dict[str, Any] | None:
    if resolved is None:
        return None
    data = {
        "id": resolved.pk,
        "rule_id": resolved.rule_id,
        "spec_id": resolved.spec_id,
        "bk_tenant_id": resolved.bk_tenant_id,
        "generation": resolved.generation,
        "resolve_version": resolved.resolve_version,
        "resolved_config": resolved.resolved_config,
        "content_hash": resolved.content_hash,
        "source": resolved.source,
        **_serialize_time_fields(resolved),
    }
    if include_records:
        data["records"] = [_serialize_resolved_record(record) for record in resolved.get_records()]
    return data


def _serialize_flow(flow: RecordRuleV4Flow | None) -> dict[str, Any] | None:
    if flow is None:
        return None
    return {
        "id": flow.pk,
        "rule_id": flow.rule_id,
        "resolved_id": flow.resolved_id,
        "bk_tenant_id": flow.bk_tenant_id,
        "flow_name": flow.flow_name,
        "flow_config": flow.flow_config,
        "content_hash": flow.content_hash,
        "flow_status": flow.flow_status,
        "last_observed_at": serialize_value(flow.last_observed_at),
        **_serialize_time_fields(flow),
    }


def _serialize_event(event: RecordRuleV4Event | None) -> dict[str, Any] | None:
    if event is None:
        return None
    return {
        "id": event.pk,
        "rule_id": event.rule_id,
        "bk_tenant_id": event.bk_tenant_id,
        "spec_id": event.spec_id,
        "resolved_id": event.resolved_id,
        "flow_id": event.flow_id,
        "generation": event.generation,
        "event_type": event.event_type,
        "status": event.status,
        "source": event.source,
        "operator": event.operator,
        "reason": event.reason,
        "message": event.message,
        "detail": event.detail,
        **_serialize_time_fields(event),
    }


def _build_rule_queryset(params: dict[str, Any], bk_tenant_id: str | None):
    queryset = filter_by_bk_tenant_id(RecordRuleV4.objects.all(), bk_tenant_id).select_related(
        "current_spec", "applied_resolved"
    )
    include_deleted = normalize_optional_bool(params.get("include_deleted"), "include_deleted")
    if not include_deleted:
        queryset = queryset.filter(deleted_at__isnull=True)

    rule_id = _normalize_int(params.get("id") or params.get("rule_id"), "id")
    if rule_id is not None:
        queryset = queryset.filter(pk=rule_id)
    for field in ["space_type", "space_id", "status", "desired_status"]:
        value = _normalize_text(params.get(field), field)
        if value:
            queryset = queryset.filter(**{field: value})
    space_uid = _normalize_text(params.get("space_uid"), "space_uid")
    if space_uid and "__" in space_uid:
        space_type, space_id = space_uid.split("__", 1)
        queryset = queryset.filter(space_type=space_type, space_id=space_id)
    name = _normalize_text(params.get("name"), "name")
    if name:
        queryset = queryset.filter(name__icontains=name)
    table_id = _normalize_text(params.get("table_id"), "table_id")
    if table_id:
        queryset = queryset.filter(table_id__icontains=table_id)
    dst_vm_table_id = _normalize_text(params.get("dst_vm_table_id"), "dst_vm_table_id")
    if dst_vm_table_id:
        queryset = queryset.filter(dst_vm_table_id__icontains=dst_vm_table_id)
    return queryset


def _get_rule_or_raise(params: dict[str, Any], bk_tenant_id: str) -> RecordRuleV4:
    rule_id = _normalize_int(params.get("id") or params.get("rule_id"), "id", required=True)
    try:
        return RecordRuleV4.objects.select_related("current_spec", "applied_resolved").get(
            bk_tenant_id=bk_tenant_id, pk=rule_id
        )
    except RecordRuleV4.DoesNotExist as error:
        raise CustomException(message=f"RecordRuleV4 不存在: {rule_id}") from error


def _latest_event(rule: RecordRuleV4) -> RecordRuleV4Event | None:
    return rule.events.order_by("-id").first()


def _build_action_response(
    *,
    operation: str,
    func_name: str,
    bk_tenant_id: str,
    rule: RecordRuleV4,
    before: dict[str, Any],
    action: str,
    succeeded: bool,
    result: Any = None,
) -> dict[str, Any]:
    rule.refresh_from_db()
    return build_response(
        operation=operation,
        func_name=func_name,
        bk_tenant_id=bk_tenant_id,
        data={
            "rule": _serialize_rule(rule),
            "action": action,
            "succeeded": succeeded,
            "result": result,
            "before": before,
            "after": _serialize_rule(rule),
            "latest_event": _serialize_event(_latest_event(rule)),
        },
        safety_level=SAFETY_LEVEL_WRITE,
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_LIST,
    summary="Admin 查询 RecordRule V4 列表",
    description="分页查询 V4 预计算规则组，返回轻量状态、版本和 Flow 摘要字段。",
    params_schema={
        "bk_tenant_id": PAGE_LIST_TENANT_SCHEMA,
        "id": "可选，规则组 ID",
        "space_uid": "可选，空间 UID，例如 bkcc__2",
        "space_type": "可选，空间类型",
        "space_id": "可选，空间 ID",
        "name": "可选，名称包含匹配",
        "table_id": "可选，输出 table_id 包含匹配",
        "dst_vm_table_id": "可选，目标 VM table_id 包含匹配",
        "status": "可选，聚合状态",
        "desired_status": "可选，期望状态",
        "include_deleted": "可选，是否包含已删除记录",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(RULE_ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "space_uid": "bkcc__2", "page": 1, "page_size": 20},
)
def list_record_rule_v4(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_page_list_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), RULE_ORDERING_FIELDS, default="-updated_at")
    queryset = _build_rule_queryset(params, bk_tenant_id).order_by(ordering, "id")
    rules, total = paginate_queryset(queryset, page=page, page_size=page_size)
    return build_response(
        operation=OPERATION_RECORD_RULE_V4_LIST,
        func_name=FUNC_RECORD_RULE_V4_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_rule(rule) for rule in rules],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_DETAIL,
    summary="Admin 查询 RecordRule V4 详情",
    description="按 ID 查询 V4 预计算规则组详情，包含当前 spec、latest/applied resolved 和 Flow 对照。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，规则组 ID"},
    example_params={"bk_tenant_id": "system", "id": 1},
)
def get_record_rule_v4_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    latest_resolved = rule.get_latest_resolved()
    return build_response(
        operation=OPERATION_RECORD_RULE_V4_DETAIL,
        func_name=FUNC_RECORD_RULE_V4_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data={
            "rule": _serialize_rule(rule),
            "current_spec": _serialize_spec(rule.current_spec, include_records=True),
            "latest_resolved": _serialize_resolved(latest_resolved, include_records=True),
            "applied_resolved": _serialize_resolved(rule.applied_resolved, include_records=True),
            "latest_flow": _serialize_flow(rule.get_latest_flow()),
            "applied_flow": _serialize_flow(rule.get_applied_flow()),
        },
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_VERSION_LIST,
    summary="Admin 查询 RecordRule V4 版本历史",
    description="按 generation 展示 spec / resolved 历史；Flow 是 group 维度唯一目标，不在版本列表里展开。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，规则组 ID",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
    },
    example_params={"bk_tenant_id": "system", "id": 1, "page": 1, "page_size": 20},
)
def list_record_rule_v4_versions(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    page, page_size = normalize_pagination(params)
    queryset = rule.specs.order_by("-generation", "-id")
    specs, total = paginate_queryset(queryset, page=page, page_size=page_size)
    items = []
    for spec in specs:
        resolved_items = []
        for resolved in spec.resolved.order_by("-resolve_version", "-id"):
            resolved_items.append(
                {
                    "resolved": _serialize_resolved(resolved, include_records=True),
                    "is_latest_resolved": resolved.pk == spec.latest_resolved_id,
                    "is_applied_resolved": resolved.pk == rule.applied_resolved_id,
                }
            )
        items.append(
            {
                "generation": spec.generation,
                "spec": _serialize_spec(spec, include_records=True),
                "resolved_items": resolved_items,
                "is_current_spec": spec.pk == rule.current_spec_id,
            }
        )
    return build_response(
        operation=OPERATION_RECORD_RULE_V4_VERSION_LIST,
        func_name=FUNC_RECORD_RULE_V4_VERSION_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_EVENT_LIST,
    summary="Admin 查询 RecordRule V4 事件流",
    description="分页查询 V4 预计算规则组事件，支持按 generation、event_type 和 status 过滤。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，规则组 ID",
        "generation": "可选，用户声明版本",
        "event_type": "可选，事件类型",
        "status": "可选，事件状态",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(EVENT_ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "id": 1, "event_type": "apply.failed"},
)
def list_record_rule_v4_events(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), EVENT_ORDERING_FIELDS, default="-id")
    queryset = rule.events.order_by(ordering, "-id")
    generation = _normalize_int(params.get("generation"), "generation")
    if generation is not None:
        queryset = queryset.filter(generation=generation)
    event_type = _normalize_text(params.get("event_type"), "event_type")
    if event_type:
        queryset = queryset.filter(event_type=event_type)
    status = _normalize_text(params.get("status"), "status")
    if status:
        queryset = queryset.filter(status=status)
    events, total = paginate_queryset(queryset, page=page, page_size=page_size)
    return build_response(
        operation=OPERATION_RECORD_RULE_V4_EVENT_LIST,
        func_name=FUNC_RECORD_RULE_V4_EVENT_LIST,
        bk_tenant_id=bk_tenant_id,
        data={
            "items": [_serialize_event(event) for event in events],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_MANUAL_REFRESH,
    summary="Admin 手动刷新 RecordRule V4 解析结果",
    description="调用 RecordRuleV4Operator.refresh_resolved，只刷新解析结果，不准备 Flow、不自动下发。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，规则组 ID", "operator": "可选，操作人"},
    example_params={"bk_tenant_id": "system", "id": 1, "operator": "admin"},
)
def manual_refresh_record_rule_v4(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    before = _serialize_rule(rule)
    resolved = RecordRuleV4Operator(
        rule, source="manual", operator=_normalize_text(params.get("operator"), "operator") or "admin"
    ).refresh_resolved()
    rule.refresh_from_db()
    latest = _latest_event(rule)
    succeeded = bool(latest and latest.status not in {"failed", "skipped"})
    return _build_action_response(
        operation=OPERATION_RECORD_RULE_V4_MANUAL_REFRESH,
        func_name=FUNC_RECORD_RULE_V4_MANUAL_REFRESH,
        bk_tenant_id=bk_tenant_id,
        rule=rule,
        before=before,
        action="manual_refresh",
        succeeded=succeeded,
        result={"resolved": _serialize_resolved(resolved, include_records=True)},
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_APPLY,
    summary="Admin 执行 RecordRule V4 当前声明",
    description=(
        "调用 RecordRuleV4Operator.execute_declaration(auto_apply=True)，完成输出资源、解析、Flow 准备和下发；"
        "force_output_apply=true 时强制重试 output 下发。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，规则组 ID",
        "operator": "可选，操作人",
        "force_output_apply": "可选，是否强制重试 output 资源下发，默认 false",
    },
    example_params={"bk_tenant_id": "system", "id": 1, "operator": "admin", "force_output_apply": False},
)
def apply_record_rule_v4(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    before = _serialize_rule(rule)
    force_output_apply = bool(normalize_optional_bool(params.get("force_output_apply"), "force_output_apply"))
    ok = RecordRuleV4Operator(
        rule, source="manual", operator=_normalize_text(params.get("operator"), "operator") or "admin"
    ).execute_declaration(auto_apply=True, force_output_apply=force_output_apply)
    return _build_action_response(
        operation=OPERATION_RECORD_RULE_V4_APPLY,
        func_name=FUNC_RECORD_RULE_V4_APPLY,
        bk_tenant_id=bk_tenant_id,
        rule=rule,
        before=before,
        action="execute_declaration",
        succeeded=ok,
        result={"ok": ok, "force_output_apply": force_output_apply},
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_SET_DESIRED_STATUS,
    summary="Admin 设置 RecordRule V4 运行期望状态",
    description="只允许 running / stopped，先 update_declaration(desired_status=...)，再 execute_declaration(auto_apply=True)。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "id": "必填，规则组 ID",
        "desired_status": "必填，running 或 stopped",
        "operator": "可选，操作人",
    },
    example_params={"bk_tenant_id": "system", "id": 1, "desired_status": "stopped", "operator": "admin"},
)
def set_record_rule_v4_desired_status(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    desired_status = _normalize_desired_status(params.get("desired_status"))
    before = _serialize_rule(rule)
    operator = RecordRuleV4Operator(
        rule, source="manual", operator=_normalize_text(params.get("operator"), "operator") or "admin"
    )
    operator.update_declaration(desired_status=desired_status)
    operator.execute_declaration(auto_apply=True)
    rule.refresh_from_db()
    succeeded = rule.desired_status == desired_status and rule.applied_desired_status == desired_status
    return _build_action_response(
        operation=OPERATION_RECORD_RULE_V4_SET_DESIRED_STATUS,
        func_name=FUNC_RECORD_RULE_V4_SET_DESIRED_STATUS,
        bk_tenant_id=bk_tenant_id,
        rule=rule,
        before=before,
        action="set_desired_status",
        succeeded=succeeded,
        result={"desired_status": desired_status},
    )


@KernelRPCRegistry.register(
    FUNC_RECORD_RULE_V4_REFRESH_FLOW_HEALTH,
    summary="Admin 观测 RecordRule V4 Flow 健康状态",
    description="调用 refresh_flow_health 读取 bkbase Flow 实际状态，并写回 Flow 状态和 group conditions。",
    params_schema={"bk_tenant_id": "可选，租户 ID", "id": "必填，规则组 ID", "operator": "可选，操作人"},
    example_params={"bk_tenant_id": "system", "id": 1, "operator": "admin"},
)
def refresh_record_rule_v4_flow_health(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    rule = _get_rule_or_raise(params, bk_tenant_id)
    before = _serialize_rule(rule)
    status = RecordRuleV4Operator(
        rule, source="manual", operator=_normalize_text(params.get("operator"), "operator") or "admin"
    ).refresh_flow_health()
    rule.refresh_from_db()
    latest = _latest_event(rule)
    succeeded = bool(latest and latest.event_type == "flow.observed" and latest.status != "failed")
    return _build_action_response(
        operation=OPERATION_RECORD_RULE_V4_REFRESH_FLOW_HEALTH,
        func_name=FUNC_RECORD_RULE_V4_REFRESH_FLOW_HEALTH,
        bk_tenant_id=bk_tenant_id,
        rule=rule,
        before=before,
        action="refresh_flow_health",
        succeeded=succeeded,
        result={"flow_status": status},
    )
