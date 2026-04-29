"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

bkm-cli django-readonly-command 服务桥后端实现。

op_id: django-readonly-command
func_name: bkm_cli.run_readonly_command

该函数是白名单分发器，不接受任意 shell / Python snippet，
只允许调用 _REGISTRY 中明确注册的只读诊断函数。
"""

from __future__ import annotations

from typing import Any
from collections.abc import Callable

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry

_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def _register(command_id: str) -> Callable:
    """注册只读诊断命令到白名单。"""

    def decorator(fn: Callable) -> Callable:
        _REGISTRY[command_id] = fn
        return fn

    return decorator


# ── 白名单诊断函数 ────────────────────────────────────────────────────────────


@_register("diagnose_ts_metric_sync")
def _diagnose_ts_metric_sync(params: dict[str, Any]) -> dict[str, Any]:
    """自定义时序指标同步分层诊断。"""
    from bkmonitor.utils.ts_metric_diagnosis import diagnose_ts_metric_sync

    data_id = params.get("data_id")
    metrics_raw = params.get("metrics")
    if not data_id:
        raise CustomException(message="params.data_id is required")
    if not metrics_raw:
        raise CustomException(message="params.metrics is required and must be non-empty")

    metrics: list[str] = metrics_raw if isinstance(metrics_raw, list) else [str(metrics_raw)]
    metrics = [m.strip() for m in metrics if str(m).strip()]
    if not metrics:
        raise CustomException(message="params.metrics must contain at least one non-empty metric name")

    try:
        return diagnose_ts_metric_sync(
            data_id=int(data_id),
            metrics=metrics,
            window_seconds=params.get("window_seconds"),
            history_seconds=params.get("history_seconds"),
            redis_prefix=str(params.get("redis_prefix") or "BK_MONITOR_TRANSFER"),
        )
    except ValueError as exc:
        raise CustomException(message=str(exc)) from exc


@_register("strategy_check")
def _strategy_check(params: dict[str, Any]) -> dict[str, Any]:
    raise CustomException(message="strategy_check is not yet implemented")


@_register("context_preview")
def _context_preview(params: dict[str, Any]) -> dict[str, Any]:
    raise CustomException(message="context_preview is not yet implemented")


@_register("check_bcs_cluster_status")
def _check_bcs_cluster_status(params: dict[str, Any]) -> dict[str, Any]:
    raise CustomException(message="check_bcs_cluster_status is not yet implemented")


# ── 分发器 ────────────────────────────────────────────────────────────────────


def run_readonly_command(params: dict[str, Any]) -> dict[str, Any]:
    """bkm_cli.run_readonly_command — 白名单只读诊断命令分发器。

    接收 command_id + params，路由到对应的只读诊断实现。
    不接受任意 shell / Python snippet，不允许修复类命令。
    """
    command_id = str(params.get("command_id") or "").strip()
    if not command_id:
        raise CustomException(message="command_id is required")
    if command_id not in _REGISTRY:
        raise CustomException(
            message=f"command_id '{command_id}' is not in the readonly whitelist. Allowed: {sorted(_REGISTRY)}"
        )

    handler = _REGISTRY[command_id]
    command_params = params.get("params") or {}
    if not isinstance(command_params, dict):
        raise CustomException(message="params must be an object")

    result = handler(command_params)
    return {"command_id": command_id, **result}


# ── 注册 ──────────────────────────────────────────────────────────────────────

KernelRPCRegistry.register_function(
    func_name="bkm_cli.run_readonly_command",
    summary="只读诊断命令分发器",
    description=(
        "bkm-cli django-readonly-command 后端函数。"
        "接收 command_id + params，路由到白名单内的只读诊断实现。"
        f"当前白名单: {sorted(_REGISTRY)}"
    ),
    handler=run_readonly_command,
    params_schema={
        "command_id": f"白名单命令 ID，可选值: {sorted(_REGISTRY)}",
        "params": "命令参数对象，字段因 command_id 而异",
    },
    example_params={
        "command_id": "diagnose_ts_metric_sync",
        "params": {"data_id": 1579347, "metrics": ["wea_agent_http_request"]},
    },
)

BkmCliOpRegistry.register(
    op_id="django-readonly-command",
    func_name="bkm_cli.run_readonly_command",
    summary="只读诊断命令分发器",
    description=(
        "通过 monitor-api 服务桥执行白名单内的只读诊断命令或注册函数。"
        "不接受任意 shell / Python snippet，不允许修复类命令。"
    ),
    capability_level="readonly",
    risk_level="medium",
    requires_confirmation=False,
    audit_tags=["command", "readonly", "diagnostic"],
    params_schema={
        "command_id": "string",
        "params": "object",
    },
    example_params={
        "command_id": "diagnose_ts_metric_sync",
        "params": {"data_id": 1579347, "metrics": ["wea_agent_http_request"]},
    },
)
