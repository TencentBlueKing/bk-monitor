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


def _normalize_exact_names(params: dict[str, Any], key: str, *, minimum: int, maximum: int) -> list[str]:
    """校验 exact 字段名列表，并按输入顺序去重，不改写原始字段名。"""

    raw_names = params.get(key)
    if raw_names is None and minimum == 0:
        return []
    if not isinstance(raw_names, list):
        raise CustomException(message=f"params.{key} must be a list")
    if not minimum <= len(raw_names) <= maximum:
        raise CustomException(message=f"params.{key} must contain {minimum} to {maximum} items")

    names: list[str] = []
    seen: set[str] = set()
    for name in raw_names:
        if not isinstance(name, str):
            raise CustomException(message=f"params.{key} items must be strings")
        if not name.strip():
            raise CustomException(message=f"params.{key} items must be non-empty")
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _serialize_result_table_field(field: dict[str, Any] | None) -> dict[str, Any]:
    """返回 ResultTableField 的固定安全投影。"""

    if field is None:
        return {"exists": False}
    return {
        "exists": True,
        "field_name": field["field_name"],
        "field_type": field["field_type"],
        "tag": field["tag"],
        "is_disabled": field["is_disabled"],
        "last_modify_time": field["last_modify_time"],
    }


def _metric_structural_alignment_state(
    *,
    has_tsm: bool,
    result_table_field: dict[str, Any] | None,
) -> str:
    if result_table_field is not None and result_table_field["is_disabled"]:
        return "rtf_disabled"
    if result_table_field is not None and result_table_field["tag"] != "metric":
        return "rtf_not_metric"
    if has_tsm and result_table_field is not None:
        return "aligned"
    if has_tsm:
        return "tsm_only"
    if result_table_field is not None:
        return "rtf_only"
    return "missing_both"


def _metric_effective_registration_state(
    *,
    selected_rows: list[dict[str, Any]],
    effective_rows: list[dict[str, Any]],
    result_table_field: dict[str, Any] | None,
    exact_scope: bool,
    group_is_enable: bool,
) -> str:
    if exact_scope and not selected_rows:
        return "metric_not_found_in_scope"
    if not group_is_enable:
        return "group_disabled"
    if selected_rows and not effective_rows:
        if all(not row["is_active"] for row in selected_rows):
            return "tsm_inactive"
        return "scope_disabled"
    structural_state = _metric_structural_alignment_state(
        has_tsm=bool(effective_rows),
        result_table_field=result_table_field,
    )
    return "effective" if structural_state == "aligned" else structural_state


def _dimension_consistency_state(
    *,
    evaluable: bool,
    effective_metric_scope_count: int,
    effective_present_scope_count: int,
    result_table_field: dict[str, Any] | None,
) -> str:
    if not evaluable:
        return "not_evaluable"
    if result_table_field is not None and result_table_field["is_disabled"]:
        return "rtf_disabled"
    if result_table_field is not None and result_table_field["tag"] != "dimension":
        return "rtf_not_dimension"
    if effective_present_scope_count and result_table_field is not None:
        if effective_present_scope_count < effective_metric_scope_count:
            return "partially_aligned"
        return "aligned"
    if effective_present_scope_count:
        return "tsm_only"
    if result_table_field is not None:
        return "rtf_only"
    return "missing_both"


@_register("inspect_ts_metric_metadata")
def _inspect_ts_metric_metadata(params: dict[str, Any]) -> dict[str, Any]:
    """按 data_id 与原始字段名做有界、纯 ORM 的时序 Metadata 登记取证。"""

    import json

    from metadata import models

    raw_data_id = params.get("data_id")
    if raw_data_id in (None, ""):
        raise CustomException(message="params.data_id is required")
    if isinstance(raw_data_id, (bool, float)):
        raise CustomException(message="params.data_id must be an integer")
    try:
        data_id = int(raw_data_id)
    except (TypeError, ValueError) as exc:
        raise CustomException(message="params.data_id must be an integer") from exc

    metrics = _normalize_exact_names(params, "metrics", minimum=1, maximum=20)
    dimensions = _normalize_exact_names(params, "dimensions", minimum=0, maximum=20)
    if len(metrics) * max(1, len(dimensions)) > 100:
        raise CustomException(message="params.metrics x max(1, dimensions) must be less than or equal to 100")

    field_scope: str | None = None
    if params.get("field_scope") is not None:
        raw_field_scope = params["field_scope"]
        if not isinstance(raw_field_scope, str):
            raise CustomException(message="params.field_scope must be a string")
        if not raw_field_scope.strip():
            raise CustomException(message="params.field_scope must be non-empty")
        field_scope = raw_field_scope

    groups = list(
        models.TimeSeriesGroup.objects.filter(bk_data_id=data_id, is_delete=False).order_by("time_series_group_id")[:2]
    )
    if not groups:
        raise CustomException(message=f"TimeSeriesGroup not found: data_id={data_id}")
    if len(groups) > 1:
        raise CustomException(
            message=f"TimeSeriesGroup integrity conflict: multiple non-deleted groups for data_id={data_id}"
        )
    group = groups[0]

    metric_queryset = models.TimeSeriesMetric.objects.filter(
        group_id=group.time_series_group_id,
        field_name__in=metrics,
    )
    if field_scope is not None:
        metric_queryset = metric_queryset.filter(field_scope=field_scope)
    metric_queryset = metric_queryset.order_by("field_name", "field_scope", "table_id", "field_id").values(
        "field_name",
        "field_scope",
        "table_id",
        "scope_id",
        "is_active",
        "last_modify_time",
        "tag_list",
    )
    metric_rows = list(metric_queryset if field_scope is not None else metric_queryset[:101])
    if field_scope is None and len(metric_rows) > 100:
        raise CustomException(
            message="inspect_ts_metric_metadata matched more than 100 TimeSeriesMetric rows; provide params.field_scope"
        )

    rows_by_metric: dict[str, list[dict[str, Any]]] = {metric: [] for metric in metrics}
    for row in metric_rows:
        rows_by_metric[row["field_name"]].append(row)

    requested_fields = list(dict.fromkeys([*metrics, *dimensions]))
    result_table_fields = {
        field["field_name"]: field
        for field in models.ResultTableField.objects.filter(
            bk_tenant_id=group.bk_tenant_id,
            table_id=group.table_id,
            field_name__in=requested_fields,
        ).values("field_name", "field_type", "tag", "is_disabled", "last_modify_time")
    }

    metric_results = []
    for metric in metrics:
        selected_rows = rows_by_metric[metric]
        effective_rows = [row for row in selected_rows if row["is_active"] and row["scope_id"] != 0]
        result_table_field = result_table_fields.get(metric)
        dimension_results = []
        for dimension in dimensions:
            dimension_field = result_table_fields.get(dimension)
            structural_present_scope_count = sum(dimension in (row["tag_list"] or []) for row in selected_rows)
            effective_present_scope_count = sum(dimension in (row["tag_list"] or []) for row in effective_rows)
            if effective_rows:
                membership = {
                    "evaluation": "evaluated",
                    "state": "present" if effective_present_scope_count else "missing",
                    "structural_metric_scope_count": len(selected_rows),
                    "effective_metric_scope_count": len(effective_rows),
                    "structural_present_scope_count": structural_present_scope_count,
                    "effective_present_scope_count": effective_present_scope_count,
                    "present_in_all_effective_scopes": effective_present_scope_count == len(effective_rows),
                }
            else:
                membership = {
                    "evaluation": "not_evaluable",
                    "state": "unknown",
                    "structural_metric_scope_count": len(selected_rows),
                    "effective_metric_scope_count": 0,
                    "structural_present_scope_count": structural_present_scope_count,
                    "effective_present_scope_count": 0,
                    "present_in_all_effective_scopes": None,
                }
            dimension_results.append(
                {
                    "field_name": dimension,
                    "membership": membership,
                    "result_table_field": _serialize_result_table_field(dimension_field),
                    "consistency_state": _dimension_consistency_state(
                        evaluable=bool(effective_rows),
                        effective_metric_scope_count=len(effective_rows),
                        effective_present_scope_count=effective_present_scope_count,
                        result_table_field=dimension_field,
                    ),
                }
            )

        metric_results.append(
            {
                "field_name": metric,
                "time_series_metric": {
                    "structural_record_count": len(selected_rows),
                    "effective_record_count": len(effective_rows),
                    "inactive_record_count": sum(not row["is_active"] for row in selected_rows),
                    "scope_disabled_record_count": sum(row["scope_id"] == 0 for row in selected_rows),
                    "records": [
                        {
                            "field_scope": row["field_scope"],
                            "table_id": row["table_id"],
                            "is_active": row["is_active"],
                            "is_scope_disabled": row["scope_id"] == 0,
                            "is_effective": row["is_active"] and row["scope_id"] != 0,
                            "last_modify_time": row["last_modify_time"],
                        }
                        for row in selected_rows
                    ],
                },
                "result_table_field": _serialize_result_table_field(result_table_field),
                "structural_alignment_state": _metric_structural_alignment_state(
                    has_tsm=bool(selected_rows),
                    result_table_field=result_table_field,
                ),
                "effective_registration_state": _metric_effective_registration_state(
                    selected_rows=selected_rows,
                    effective_rows=effective_rows,
                    result_table_field=result_table_field,
                    exact_scope=field_scope is not None,
                    group_is_enable=group.is_enable,
                ),
                "dimensions": dimension_results,
            }
        )

    result = {
        "context": {
            "data_id": group.bk_data_id,
            "bk_biz_id": group.bk_biz_id,
            "bk_tenant_id": group.bk_tenant_id,
            "time_series_group_id": group.time_series_group_id,
            "table_id": group.table_id,
            "group_is_enable": group.is_enable,
            "group_is_delete": group.is_delete,
            "scope_mode": "exact" if field_scope is not None else "all_bounded",
            "field_scope": field_scope,
        },
        "metrics": metric_results,
    }
    return json.loads(json.dumps(result, default=str))


@_register("get_effective_setting")
def _get_effective_setting(params: dict[str, Any]) -> dict[str, Any]:
    """读取某动态配置的「四源生效值」回显，定位三源不一致。

    动机：read-db-model 只能给出 GlobalConfig 的 DB 行；当 DB 无行时，真正生效的值
    由 DynamicSettings 回退到 settings 层默认值决定——read-db-model 给不出这个回退后的
    生效值。本命令一次性回显四个来源，让 agent 一眼看穿不一致：

      - effective_value   : getattr(settings, name)，经 DynamicSettings 解析的最终生效值
      - db_value          : GlobalConfig 表里该 key 的 DB 值（无行为 null）
      - settings_default  : settings 层解析值（config + env/role 覆盖后、DB 覆盖前；不必等于字面 config/default.py）
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

    # settings_default：Django settings 层解析值（config/default.py + 环境/角色 config 覆盖后、
    # DynamicSettings DB 覆盖前）。settings._wrapped 在启用 USE_DYNAMIC_SETTINGS 时是 DynamicSettings
    # 实例，其 ._wrapped 才是原始 settings（DB 覆盖发生在 DynamicSettings.__getattr__）。
    # 注意：这是部署生效的 settings 层值，不必等于字面 config/default.py——部署常按环境覆盖
    # （如某环境把 COMPATIBLE_ALARM_FORMAT 覆盖为 False）。未启用动态配置时无包装层、拿不到该层原值，标 unavailable。
    settings_default = _read_settings_default(settings, name)
    if settings_default is not _UNAVAILABLE:
        settings_default = _mask(settings_default)

    # serializer_default：global_config 注册表（ADVANCED_OPTIONS / STANDARD_CONFIGS）里该项 serializer 的 default。
    serializer_default = _read_serializer_default(global_config, name)
    if serializer_default is not _UNAVAILABLE:
        serializer_default = _mask(serializer_default)

    result = {
        "name": name,
        "effective_value": effective_value,
        "db_row_present": db_row_present,
        "db_value": db_value,
        "settings_default": settings_default,
        "serializer_default": serializer_default,
        "resolved_source": "db_row" if db_row_present else "settings_default",
        "masked": is_credential,
    }
    # 与 commands.py 既有范式一致：即便有出口层根因钩子，这里也保留双保险归一。
    return json.loads(json.dumps(result, default=str))


@_register("get_report_token")
def _get_report_token(params: dict[str, Any]) -> dict[str, Any]:
    """回显自定义上报 dataid 对应的上报凭证（bk.data.token），只读，支持两种上报格式。

    动机：自定义指标上报有两条格式各用不同 token，配置推送客户端时要取对的那个：
      - **prometheus**（pushgateway / remotewrite / OTLP，header X-BK-TOKEN）：aes256 自描述
        token，由 dataid(s)+biz 经平台 AES 密钥**确定性算出**
        （bkmonitor.utils.cipher.transform_data_id_to_token / _v1_token）。
      - **json**（`/v2/push` body 的 access_token）：随机 uuid token，**存在 `DataSource.token`**
        （metadata），只能按 bk_data_id **读取**、不可推导。
    本命令只读回显，免手工推导 / 翻库。

    约束：
      - token 是「按 dataid 隔离的上报凭证」，非租户安全边界；命令只读、无副作用。
      - AES 密钥仅用于计算、不回显。
      - token_version=v0（默认）走 transform_data_id_to_token；v1 走 transform_data_id_to_v1_token
        （多 profile_data_id 维度，bk-collector aes256Decoder 兼容解析 v0/v1）；仅对 prometheus 生效。

    params：
      - format：prometheus | json | all（默认 all；prom/otlp→prometheus、proxy/v2push→json）。
      - metric_data_id/trace_data_id/log_data_id/bk_biz_id(int, 默认 -1)；prometheus 需至少一个 dataid；
        json 需 metric_data_id（作 DataSource 读取键）。
      - profile_data_id(int, 默认 -1，仅 prometheus+v1)；app_name(str, 默认 "")；token_version(v0|v1, 默认 v0)。
    返回 tokens：{"prometheus": <aes256>, "json": <uuid>}（按请求的 format 子集）。
    """
    import json

    from bkmonitor.utils.cipher import transform_data_id_to_token, transform_data_id_to_v1_token

    def _to_int(key: str, default: int = -1) -> int:
        raw = params.get(key, default)
        if raw in (None, ""):
            return default
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise CustomException(message=f"params.{key} must be an integer") from exc

    # format 归一 + 别名
    fmt = str(params.get("format") or "all").strip().lower()
    fmt = {"prom": "prometheus", "otlp": "prometheus", "proxy": "json", "v2push": "json"}.get(fmt, fmt)
    if fmt not in ("prometheus", "json", "all"):
        raise CustomException(message="params.format must be 'prometheus', 'json' or 'all'")
    want_prom = fmt in ("prometheus", "all")
    want_json = fmt in ("json", "all")

    token_version = str(params.get("token_version") or "v0").strip().lower()
    if token_version not in ("v0", "v1"):
        raise CustomException(message="params.token_version must be 'v0' or 'v1'")

    # profile_data_id 仅 prometheus+v1 有意义；其余情形传入即拒绝，避免静默丢弃。
    if params.get("profile_data_id") not in (None, "") and not (want_prom and token_version == "v1"):
        raise CustomException(
            message="params.profile_data_id is only valid with format prometheus/all and token_version='v1'"
        )

    # prometheus：至少提供一个 dataid（v1 含 profile），否则各 id 全落默认 -1、aes256 token 无隔离意义。
    if want_prom:
        id_keys = ("metric_data_id", "trace_data_id", "log_data_id")
        if token_version == "v1":
            id_keys += ("profile_data_id",)
        if all(params.get(k) in (None, "") for k in id_keys):
            raise CustomException(
                message="at least one of metric_data_id / trace_data_id / log_data_id "
                "(or profile_data_id when token_version='v1') is required for prometheus format"
            )
    # json：token 存于 DataSource，按 metric_data_id（bk_data_id）读取，故必须给 metric_data_id。
    if want_json and params.get("metric_data_id") in (None, ""):
        raise CustomException(message="params.metric_data_id is required for json format (DataSource lookup key)")

    metric_data_id = _to_int("metric_data_id")
    trace_data_id = _to_int("trace_data_id")
    log_data_id = _to_int("log_data_id")
    bk_biz_id = _to_int("bk_biz_id")
    app_name = str(params.get("app_name") or "")

    result: dict[str, Any] = {
        "format": fmt,
        "token_version": token_version,
        "metric_data_id": metric_data_id,
        "trace_data_id": trace_data_id,
        "log_data_id": log_data_id,
        "bk_biz_id": bk_biz_id,
        "app_name": app_name,
        "tokens": {},
    }

    if want_prom:
        if token_version == "v1":
            profile_data_id = _to_int("profile_data_id")
            result["profile_data_id"] = profile_data_id
            result["tokens"]["prometheus"] = transform_data_id_to_v1_token(
                metric_data_id=metric_data_id,
                trace_data_id=trace_data_id,
                log_data_id=log_data_id,
                profile_data_id=profile_data_id,
                bk_biz_id=bk_biz_id,
                app_name=app_name,
            )
        else:
            result["tokens"]["prometheus"] = transform_data_id_to_token(
                metric_data_id=metric_data_id,
                trace_data_id=trace_data_id,
                log_data_id=log_data_id,
                bk_biz_id=bk_biz_id,
                app_name=app_name,
            )

    if want_json:
        # json/proxy token = DataSource.token（uuid，随机存储、不可推导），按 bk_data_id 只读读取。
        # 注意 token 字段 default=""：系统/内建（非自定义）dataid 的行存在但 token 为空。
        from metadata.models.data_source import DataSource

        data_source = DataSource.objects.filter(bk_data_id=metric_data_id).first()
        json_token = data_source.token if data_source is not None else ""
        if json_token:
            result["tokens"]["json"] = json_token
        else:
            reason = (
                f"DataSource for bk_data_id={metric_data_id} not found"
                if data_source is None
                else f"DataSource bk_data_id={metric_data_id} has empty token (typically a non-custom/system data source)"
            )
            if fmt == "json":
                # 用户显式点名 json → 严格失败，不返回空 token。
                raise CustomException(message=f"json/proxy token unavailable: {reason}")
            # format=all → 尽力而为：json 置 null + 记 note，不丢弃已算出的 prometheus token。
            result["tokens"]["json"] = None
            result.setdefault("notes", []).append(f"json token unavailable: {reason}")

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


def _read_settings_default(settings: Any, name: str) -> Any:
    """读取 Django settings 层值（config + 环境/角色 config 覆盖后、DB 覆盖前）。

    启用 USE_DYNAMIC_SETTINGS 时 settings._wrapped 是 DynamicSettings 包装层，
    其 ._wrapped 才是原始 settings；直接 getattr(原始 settings, name) 不走 DB 覆盖。
    注意：这是部署生效的 settings 层值，不必等于字面 config/default.py（部署常按环境覆盖）。
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
    # 无法区分「DB 覆盖后」与「settings 层值」，故标 unavailable 而非返回可能已被覆盖的值。
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
