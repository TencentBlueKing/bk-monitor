"""
bkm-cli assignment / notice inspection helpers.

These functions intentionally expose business-level read-only views instead of
adding raw FTA models to read-db-model.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

GLOBAL_BIZ_ID = 0


def _to_int(value: Any, field: str) -> int:
    if value in (None, ""):
        raise CustomException(message=f"{field} is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CustomException(message=f"{field} must be an integer: {value}") from exc


def _optional_int(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    return _to_int(value, field)


def _bool_param(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _list_ints(value: Any, field: str) -> list[int]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise CustomException(message=f"{field} must be an integer array")
    return [_to_int(item, field) for item in value]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, set | frozenset):
        return sorted((_json_safe(item) for item in value), key=repr)
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    # Decimal / UUID / enum — 显式转换，不依赖 json.dumps 测试
    # （Django 环境 json 模块被 patch 为 ujson，行为与标准库不同）
    from decimal import Decimal
    from enum import Enum
    from uuid import UUID

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _json_safe(value.value)
    # 其他未知类型 — str 兜底
    return str(value)


def _serialize_model(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _json_safe(getattr(obj, field, None)) for field in fields}


ACTION_FIELDS = [
    "id",
    "bk_biz_id",
    "strategy_id",
    "strategy_relation_id",
    "signal",
    "status",
    "real_status",
    "failure_type",
    "alert_level",
    "alerts",
    "action_config_id",
    "is_parent_action",
    "parent_action_id",
    "sub_actions",
    "assignee",
    "inputs",
    "outputs",
    "create_time",
    "update_time",
    "end_time",
    "is_polled",
    "need_poll",
    "execute_times",
    "generate_uuid",
]


def inspect_action_detail(params: dict[str, Any]) -> dict[str, Any]:
    from bkmonitor.models import ActionInstance

    action_id = _to_int(params.get("action_id"), "action_id")
    try:
        action = ActionInstance.objects.get(id=action_id)
    except ActionInstance.DoesNotExist:
        return {
            "source_state": "current_db_state",
            "lookup_mode": "action_id",
            "exists": False,
            "action_id": action_id,
            "action": None,
            "next_actions": ["确认 action_id 是否来自目标通知批次；inspect-action-detail 不接受 alert_id。"],
        }
    return {
        "source_state": "current_db_state",
        "lookup_mode": "action_id",
        "exists": True,
        "action_id": action_id,
        "action": _serialize_model(action, ACTION_FIELDS),
    }


GROUP_FIELDS = [
    "id",
    "bk_biz_id",
    "name",
    "priority",
    "is_builtin",
    "is_enabled",
    "settings",
    "source",
    "update_user",
    "update_time",
]
RULE_FIELDS = [
    "id",
    "bk_biz_id",
    "assign_group_id",
    "is_enabled",
    "user_groups",
    "user_type",
    "conditions",
    "actions",
    "alert_severity",
    "additional_tags",
]
USER_GROUP_FIELDS = [
    "id",
    "bk_biz_id",
    "name",
    "timezone",
    "need_duty",
    "channels",
    "mention_list",
    "alert_notice",
    "action_notice",
    "duty_notice",
    "duty_rules",
    "update_user",
    "update_time",
]
DUTY_FIELDS = [
    "id",
    "user_group_id",
    "duty_rule_id",
    "work_time",
    "users",
    "duty_users",
    "group_type",
    "group_number",
    "need_rotation",
    "effective_time",
    "handoff_time",
    "duty_time",
    "order",
    "backups",
]


def inspect_assign_config(params: dict[str, Any]) -> dict[str, Any]:
    from bkmonitor.models import AlertAssignGroup, AlertAssignRule, UserGroup

    bk_biz_id = _to_int(params.get("bk_biz_id"), "bk_biz_id")
    include_global = _bool_param(params.get("include_global"), True)
    include_user_groups = _bool_param(params.get("include_user_groups"), True)
    only_enabled = _bool_param(params.get("only_enabled"), False)
    biz_ids = [bk_biz_id, GLOBAL_BIZ_ID] if include_global else [bk_biz_id]

    group_queryset = AlertAssignGroup.objects.filter(bk_biz_id__in=biz_ids)
    assign_group_id = _optional_int(params.get("assign_group_id"), "assign_group_id")
    if assign_group_id is not None:
        group_queryset = group_queryset.filter(id=assign_group_id)
    if only_enabled:
        group_queryset = group_queryset.filter(is_enabled=True)
    groups = list(group_queryset.order_by("-priority", "id"))
    group_ids = [group.id for group in groups]

    rule_id = _optional_int(params.get("rule_id"), "rule_id")
    if (assign_group_id is not None or only_enabled) and not group_ids:
        rules = []
    else:
        rule_queryset = AlertAssignRule.objects.filter(bk_biz_id__in=biz_ids)
        if group_ids:
            rule_queryset = rule_queryset.filter(assign_group_id__in=group_ids)
        if assign_group_id is not None:
            rule_queryset = rule_queryset.filter(assign_group_id=assign_group_id)
        if rule_id is not None:
            rule_queryset = rule_queryset.filter(id=rule_id)
        if only_enabled:
            rule_queryset = rule_queryset.filter(is_enabled=True)
        rules = list(rule_queryset.order_by("assign_group_id", "id"))

    user_group_ids = sorted({user_group_id for rule in rules for user_group_id in (rule.user_groups or [])})
    user_groups = []
    if include_user_groups and user_group_ids:
        user_groups = [
            _serialize_model(user_group, USER_GROUP_FIELDS)
            for user_group in UserGroup.objects.filter(id__in=user_group_ids).order_by("id")
        ]

    return {
        "source_state": "current_db_state",
        "bk_biz_id": bk_biz_id,
        "include_global": include_global,
        "exists": bool(groups or rules),
        "groups": [_serialize_model(group, GROUP_FIELDS) for group in groups],
        "rules": [_serialize_model(rule, RULE_FIELDS) for rule in rules],
        "user_groups": user_groups,
        "missing_user_group_ids": sorted(set(user_group_ids) - {group["id"] for group in user_groups}),
    }


def inspect_notice_target(params: dict[str, Any]) -> dict[str, Any]:
    from bkmonitor.models import DutyArrange, UserGroup

    user_group_ids = _list_ints(params.get("user_group_ids"), "user_group_ids")
    if not user_group_ids:
        raise CustomException(message="user_group_ids is required")
    include_duty = _bool_param(params.get("include_duty"), True)

    groups = list(UserGroup.objects.filter(id__in=user_group_ids).order_by("id"))
    duty_by_group: dict[int, list[dict[str, Any]]] = defaultdict(list)
    if include_duty and groups:
        arranges = DutyArrange.objects.filter(user_group_id__in=[group.id for group in groups]).order_by(
            "user_group_id", "order", "id"
        )
        for arrange in arranges:
            duty_by_group[arrange.user_group_id].append(_serialize_model(arrange, DUTY_FIELDS))

    return {
        "source_state": "current_db_state",
        "exists": bool(groups),
        "count": len(groups),
        "user_groups": [
            {
                **_serialize_model(group, USER_GROUP_FIELDS),
                "duty_arranges": duty_by_group.get(group.id, []),
            }
            for group in groups
        ],
        "missing_user_group_ids": sorted(set(user_group_ids) - {group.id for group in groups}),
    }


def replay_assign_match(params: dict[str, Any]) -> dict[str, Any]:
    from alarm_backends.core.cache.assign import AssignCacheManager
    from alarm_backends.service.fta_action.tasks.alert_assign import BackendAssignMatchManager
    from bkmonitor.documents import AlertDocument
    from bkmonitor.utils.local import local
    from constants.action import AssignMode

    alert_id = str(params.get("alert_id") or "").strip()
    if not alert_id:
        raise CustomException(message="alert_id is required")
    assign_mode = params.get("assign_mode") or [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
    if not isinstance(assign_mode, list):
        raise CustomException(message="assign_mode must be an array")

    alerts = AlertDocument.mget(ids=[alert_id])
    if not alerts:
        return {
            "source_state": "current_runtime_state",
            "history_guarantee": "current_cache_only_not_historical",
            "exists": False,
            "alert_id": alert_id,
            "matched": False,
            "next_actions": ["确认 alert_id 是否存在且未过期；如需历史 action，请用 action_id 查询。"],
        }

    # AssignCacheManager 依赖 local.assign_cache（threading.local），
    # 但该属性仅在 alarm_backends 模块导入线程中通过 setattr 初始化。
    # kernel_api 请求线程可能从未初始化过，访问时会 KeyError / AttributeError。
    # 此处按需初始化，finally 中清理，不污染已有状态。
    had_assign_cache = hasattr(local, "assign_cache")
    if not had_assign_cache:
        local.assign_cache = {}

    try:
        alert = alerts[0]
        manager = BackendAssignMatchManager(
            alert,
            notice_users=getattr(alert, "assignee", None) or [],
            assign_mode=assign_mode,
        )
        manager.run_match()
        return {
            "source_state": "current_runtime_state",
            "history_guarantee": "current_cache_only_not_historical",
            "alert_id": alert_id,
            "exists": True,
            "matched": bool(manager.matched_rules),
            "matched_rule_ids": [rule.rule_id for rule in manager.matched_rules],
            "matched_rule_info": _json_safe(manager.matched_rule_info),
            "match_dimensions": _json_safe(manager.dimensions),
            "assign_mode": assign_mode,
            "next_actions": [
                "此 replay 基于当前 DB/cache，不能证明历史 action 创建时也使用同一规则。",
                "如需解释已发送通知，请用目标 action_id 调用 inspect-action-detail 查看 inputs.notify_info/notice_receiver。",
            ],
        }
    finally:
        if not had_assign_cache:
            AssignCacheManager.clear()
            del local.assign_cache


def _register_op(
    op_id: str, func_name: str, summary: str, params_schema: dict[str, Any], example_params: dict[str, Any]
):
    KernelRPCRegistry.register_function(
        func_name=func_name,
        summary=summary,
        description=f"bkm-cli {summary}",
        handler={
            "bkm_cli.inspect_action_detail": inspect_action_detail,
            "bkm_cli.inspect_assign_config": inspect_assign_config,
            "bkm_cli.inspect_notice_target": inspect_notice_target,
            "bkm_cli.replay_assign_match": replay_assign_match,
        }[func_name],
        params_schema=params_schema,
        example_params=example_params,
    )
    BkmCliOpRegistry.register(
        op_id=op_id,
        func_name=func_name,
        summary=summary,
        description=summary,
        capability_level="inspect",
        risk_level="low",
        requires_confirmation=False,
        audit_tags=["fta", "assignment", "notice", "readonly"],
        params_schema=params_schema,
        example_params=example_params,
    )


_register_op(
    "inspect-action-detail",
    "bkm_cli.inspect_action_detail",
    "通过 action_id 读取通知 action 详情",
    {
        "action_id": "integer，必填；inspect-action-detail 不接受 alert_id",
    },
    {"action_id": 6885950371},
)

_register_op(
    "inspect-assign-config",
    "bkm_cli.inspect_assign_config",
    "读取 DB 当前分派组和分派规则配置",
    {
        "bk_biz_id": "integer，必填",
        "assign_group_id": "integer，可选",
        "rule_id": "integer，可选",
        "include_global": "boolean，默认 true",
        "include_user_groups": "boolean，默认 true",
        "only_enabled": "boolean，默认 false",
    },
    {"bk_biz_id": -4220780, "assign_group_id": 1595, "include_user_groups": True},
)

_register_op(
    "inspect-notice-target",
    "bkm_cli.inspect_notice_target",
    "解析用户组通知配置和值班配置",
    {
        "user_group_ids": "integer[]，必填",
        "include_duty": "boolean，默认 true",
    },
    {"user_group_ids": [95671, 94872], "include_duty": True},
)

_register_op(
    "replay-assign-match",
    "bkm_cli.replay_assign_match",
    "基于当前运行态 cache 复现分派匹配",
    {
        "alert_id": "string，必填",
        "assign_mode": "string[]，默认 ['only_notice', 'by_rule']",
    },
    {"alert_id": "1778250641315430329", "assign_mode": ["only_notice", "by_rule"]},
)
