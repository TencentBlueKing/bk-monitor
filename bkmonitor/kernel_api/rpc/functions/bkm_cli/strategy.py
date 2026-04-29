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

from bkmonitor.models.strategy import StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

OPERATION_DETAIL = "detail"
OPERATION_LIST_BY_PRIORITY_GROUP = "list_by_priority_group"
ALLOWED_OPERATIONS = {OPERATION_DETAIL, OPERATION_LIST_BY_PRIORITY_GROUP}


def inspect_strategy_config(params: dict[str, Any]) -> dict[str, Any]:
    operation = str(params.get("operation") or OPERATION_DETAIL).strip()
    if operation not in ALLOWED_OPERATIONS:
        raise CustomException(message=f"不支持的 inspect-strategy-config operation: {operation}")

    bk_biz_id = _required_int(params, "bk_biz_id")
    if operation == OPERATION_DETAIL:
        return _inspect_strategy_detail(params, bk_biz_id)
    return _list_by_priority_group(params, bk_biz_id)


def _inspect_strategy_detail(params: dict[str, Any], bk_biz_id: int) -> dict[str, Any]:
    strategy_id = _required_int(params, "strategy_id")
    include_user_groups = bool(params.get("include_user_groups", False))
    include_raw_model_ids = bool(params.get("include_raw_model_ids", False))

    try:
        strategy_model = StrategyModel.objects.get(bk_biz_id=bk_biz_id, id=strategy_id)
    except StrategyModel.DoesNotExist as error:
        raise CustomException(message=f"策略不存在: bk_biz_id={bk_biz_id}, strategy_id={strategy_id}") from error

    strategy_config = _build_strategy_config(strategy_model, include_user_groups=include_user_groups)
    return {
        "operation": OPERATION_DETAIL,
        "bk_biz_id": bk_biz_id,
        "strategy_id": strategy_id,
        "strategy": _select_strategy_config(strategy_config, include_raw_model_ids=include_raw_model_ids),
    }


def _list_by_priority_group(params: dict[str, Any], bk_biz_id: int) -> dict[str, Any]:
    priority_group_key = str(params.get("priority_group_key") or "").strip()
    if not priority_group_key:
        raise CustomException(message="operation=list_by_priority_group 必须提供 priority_group_key")

    include_disabled = bool(params.get("include_disabled", False))
    include_invalid = bool(params.get("include_invalid", False))

    queryset = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, priority_group_key=priority_group_key)
    if not include_disabled:
        queryset = queryset.filter(is_enabled=True)
    if not include_invalid:
        queryset = queryset.filter(is_invalid=False)
    queryset = queryset.order_by("priority", "id")

    strategies = [_summarize_strategy_model(strategy) for strategy in queryset]
    return {
        "operation": OPERATION_LIST_BY_PRIORITY_GROUP,
        "bk_biz_id": bk_biz_id,
        "priority_group_key": priority_group_key,
        "count": len(strategies),
        "strategies": strategies,
    }


def _build_strategy_config(strategy_model: StrategyModel, *, include_user_groups: bool) -> dict[str, Any]:
    try:
        strategy_obj = Strategy.from_models([strategy_model])[0]
        strategy_obj.restore()
        config = strategy_obj.to_dict()
    except Exception as error:
        raise CustomException(message=f"策略配置解析失败: strategy_id={strategy_model.id}, 原因: {error}") from error

    if include_user_groups:
        try:
            Strategy.fill_user_groups([config])
        except Exception as error:
            raise CustomException(
                message=f"策略通知组填充失败: strategy_id={strategy_model.id}, 原因: {error}"
            ) from error
    return config


def _select_strategy_config(config: dict[str, Any], *, include_raw_model_ids: bool) -> dict[str, Any]:
    selected_keys = [
        "id",
        "bk_biz_id",
        "name",
        "source",
        "scenario",
        "type",
        "is_enabled",
        "is_invalid",
        "invalid_type",
        "priority",
        "priority_group_key",
        "items",
        "detects",
        "actions",
        "notice",
        "labels",
        "issue_config",
        "update_time",
        "update_user",
        "create_time",
        "create_user",
    ]
    selected = {key: config.get(key) for key in selected_keys if key in config}
    if include_raw_model_ids:
        selected["raw_model_ids"] = _extract_raw_model_ids(config)
    return selected


def _extract_raw_model_ids(config: dict[str, Any]) -> dict[str, list[int]]:
    return {
        "items": _extract_ids(config.get("items")),
        "detects": _extract_ids(config.get("detects")),
        "actions": _extract_ids(config.get("actions")),
        "notice": _extract_ids([config.get("notice")] if isinstance(config.get("notice"), dict) else []),
    }


def _extract_ids(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_id = value.get("id")
        if isinstance(raw_id, int):
            result.append(raw_id)
    return result


def _summarize_strategy_model(strategy: StrategyModel) -> dict[str, Any]:
    return {
        "id": strategy.id,
        "bk_biz_id": strategy.bk_biz_id,
        "name": strategy.name,
        "scenario": strategy.scenario,
        "type": strategy.type,
        "source": strategy.source,
        "is_enabled": strategy.is_enabled,
        "is_invalid": strategy.is_invalid,
        "invalid_type": strategy.invalid_type,
        "priority": strategy.priority,
        "priority_group_key": strategy.priority_group_key,
        "update_time": str(strategy.update_time) if strategy.update_time is not None else None,
        "update_user": strategy.update_user,
    }


def _required_int(params: dict[str, Any], field_name: str) -> int:
    value = params.get(field_name)
    if value in (None, ""):
        raise CustomException(message=f"inspect-strategy-config 必须提供 {field_name}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是整数: {value}") from error


KernelRPCRegistry.register_function(
    func_name="bkm_cli.inspect_strategy_config",
    summary="读取策略聚合配置",
    description="bkm-cli inspect-strategy-config 后端函数，复用策略聚合逻辑读取策略详情或同优先级分组策略摘要。",
    handler=inspect_strategy_config,
    params_schema={
        "operation": "detail | list_by_priority_group",
        "bk_biz_id": "integer",
        "strategy_id": "operation=detail 必填",
        "priority_group_key": "operation=list_by_priority_group 必填",
        "include_user_groups": "boolean",
        "include_raw_model_ids": "boolean",
        "include_disabled": "boolean",
        "include_invalid": "boolean",
    },
    example_params={
        "operation": "detail",
        "bk_biz_id": 7,
        "strategy_id": 121950,
        "include_user_groups": True,
    },
)

BkmCliOpRegistry.register(
    op_id="inspect-strategy-config",
    func_name="bkm_cli.inspect_strategy_config",
    summary="读取策略聚合配置",
    description="通过 monitor-api 服务桥读取策略完整配置或同 priority_group_key 策略摘要。",
    capability_level="inspect",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["db", "strategy", "inspect"],
    params_schema={
        "operation": "detail | list_by_priority_group",
        "bk_biz_id": "integer",
        "strategy_id": "integer",
        "priority_group_key": "string",
        "include_user_groups": "boolean",
        "include_raw_model_ids": "boolean",
        "include_disabled": "boolean",
        "include_invalid": "boolean",
    },
    example_params={
        "operation": "detail",
        "bk_biz_id": 7,
        "strategy_id": 121950,
        "include_user_groups": True,
    },
)
