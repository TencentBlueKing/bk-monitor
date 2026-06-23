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

import re
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

    import json

    try:
        result = diagnose_ts_metric_sync(
            data_id=int(data_id),
            metrics=metrics,
            window_seconds=params.get("window_seconds"),
            history_seconds=params.get("history_seconds"),
            redis_prefix=str(params.get("redis_prefix") or "BK_MONITOR_TRANSFER"),
        )
        # normalize datetime / Decimal / lazy objects to JSON-safe primitives
        return json.loads(json.dumps(result, default=str))
    except ValueError as exc:
        raise CustomException(message=str(exc)) from exc


@_register("get_effective_setting")
def _get_effective_setting(params: dict[str, Any]) -> dict[str, Any]:
    """读取某动态配置的「四源生效值」回显，定位三源不一致。

    动机：read-db-model 只能给出 GlobalConfig 的 DB 行；当 DB 无行时，真正生效的值
    由 DynamicSettings 回退到 settings 静态默认（config/default.py）决定——read-db-model
    给不出这个回退后的生效值。本命令一次性回显四个来源，让 agent 一眼看穿不一致：

      - effective_value   : getattr(settings, name)，经 DynamicSettings 解析的最终生效值
      - db_value          : GlobalConfig 表里该 key 的 DB 值（无行为 null）
      - static_default    : config/default.py 的静态默认（未经 DB 覆盖的 wrapped 原值）
      - serializer_default: global_config 注册表里该项 serializer 的 default

    典型事故（COMPATIBLE_ALARM_FORMAT）：config/default.py=True、serializer 默认=False、
    DB 行可能又另设——三源不一致时只看任一源都会误判生效值。
    """
    import json

    from django.conf import settings

    from bkmonitor.define import global_config
    from bkmonitor.models.config import GlobalConfig

    name = str(params.get("name") or "").strip()
    if not name:
        raise CustomException(message="params.name is required")

    # 白名单：动态配置名集合，与 DynamicSettings.__name_list__ 同源（global_config.GLOBAL_CONFIGS）。
    allowed_names = set(global_config.GLOBAL_CONFIGS)
    if name not in allowed_names:
        raise CustomException(
            message=(
                f"name '{name}' is not a known dynamic global config. "
                f"Allowed names come from bkmonitor.define.global_config.GLOBAL_CONFIGS ({len(allowed_names)} keys)."
            )
        )

    # 凭据脱敏：name 命中凭据类关键字时，所有值统一脱敏，规则与 db.py 的 GlobalConfig 行级脱敏同源。
    is_credential = bool(_CREDENTIAL_NAME_PATTERN.search(name))

    def _mask(value: Any) -> Any:
        return _MASKED_VALUE if is_credential else value

    # effective_value：经 DynamicSettings 解析的最终生效值。
    effective_value = _mask(getattr(settings, name))

    # db_row：GlobalConfig 表是否有该 key（key 字段见 models/config.py，unique）。
    db_conf = GlobalConfig.objects.filter(key=name).last()
    db_row_present = db_conf is not None
    db_value = _mask(db_conf.value) if db_row_present else None

    # static_default：config/default.py 的静态默认（未经 DB 覆盖的 wrapped 原值）。
    # settings._wrapped 在启用 USE_DYNAMIC_SETTINGS 时是 DynamicSettings 实例，
    # 其 ._wrapped 才是原始 settings（config/default.py 的值，DB 覆盖发生在 DynamicSettings.__getattr__）。
    # 未启用动态配置时无 DynamicSettings 包装层，拿不到「未经 DB 覆盖」的干净原值，标 unavailable。
    static_default = _read_static_default(settings, name)
    if static_default is not _UNAVAILABLE:
        static_default = _mask(static_default)

    # serializer_default：global_config 注册表（ADVANCED_OPTIONS / STANDARD_CONFIGS）里该项 serializer 的 default。
    serializer_default = _read_serializer_default(global_config, name)
    if serializer_default is not _UNAVAILABLE:
        serializer_default = _mask(serializer_default)

    result = {
        "name": name,
        "effective_value": effective_value,
        "db_row_present": db_row_present,
        "db_value": db_value,
        "static_default": static_default,
        "serializer_default": serializer_default,
        "resolved_source": "db_row" if db_row_present else "settings_default",
        "masked": is_credential,
    }
    # 与 commands.py 既有范式一致：即便有出口层根因钩子，这里也保留双保险归一。
    return json.loads(json.dumps(result, default=str))


# ── get_effective_setting 辅助 ────────────────────────────────────────────────

# 凭据类 name（含 token/secret/password/appsecret 等，大小写不敏感）一律脱敏。
# 规则与 db.py GlobalConfig 行级脱敏 (GLOBAL_CONFIG_SENSITIVE_KEY_PATTERN) 取并集，
# 这里命中 name 即脱敏（不依赖 value 形态，配置名已足够判定）。
_CREDENTIAL_NAME_PATTERN = re.compile(
    r"SECRET|TOKEN|PASSWORD|PASSWD|APPSECRET|APP_SECRET|PRIVATE|CREDENTIAL"
    r"|API_KEY|ACCESS_KEY|APP_KEY|AES|RSA|SALT|CIPHER",
    re.IGNORECASE,
)
_MASKED_VALUE = "***masked***"

# 哨兵：区分「取不到（unavailable）」与「值本身是 None」。
_UNAVAILABLE = "unavailable"


def _read_static_default(settings: Any, name: str) -> Any:
    """读取未经 DB 覆盖的静态默认（config/default.py 原值）。

    启用 USE_DYNAMIC_SETTINGS 时 settings._wrapped 是 DynamicSettings 包装层，
    其 ._wrapped 才是原始 settings；直接 getattr(原始 settings, name) 不走 DB 覆盖。
    未启用动态配置或拿不到包装层时返回 _UNAVAILABLE（哨兵），不瞎构造。
    """
    try:
        from bkmonitor.utils.dynamic_settings import DynamicSettings
    except Exception:
        return _UNAVAILABLE

    wrapped = getattr(settings, "_wrapped", None)
    if isinstance(wrapped, DynamicSettings):
        raw_settings = getattr(wrapped, "_wrapped", None)
        if raw_settings is not None and hasattr(raw_settings, name):
            return getattr(raw_settings, name)
    # 未启用动态配置（settings._wrapped 不是 DynamicSettings）时，
    # 无法区分「DB 覆盖后」与「静态默认」，故标 unavailable 而非返回可能已被覆盖的值。
    return _UNAVAILABLE


def _read_serializer_default(global_config: Any, name: str) -> Any:
    """读取 global_config 注册表里该项 serializer 的 default。

    name 注册在 ADVANCED_OPTIONS 或 STANDARD_CONFIGS（均为 {name: serializer} 的 OrderedDict）。
    DRF serializer 未显式声明 default 时其 .default 为 rest_framework.fields.empty（哨兵），
    此时标 _UNAVAILABLE。
    """
    from rest_framework.fields import empty

    serializer = None
    advanced = getattr(global_config, "ADVANCED_OPTIONS", {})
    standard = getattr(global_config, "STANDARD_CONFIGS", {})
    if name in advanced:
        serializer = advanced[name]
    elif name in standard:
        serializer = standard[name]
    if serializer is None:
        return _UNAVAILABLE

    default = getattr(serializer, "default", empty)
    if default is empty:
        return _UNAVAILABLE
    return default


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
