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

import logging
from typing import Any, NamedTuple

from django.conf import settings
from django.db.models import Q

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.apm import (
    _load_apm_datasource_maps,
    _load_service_count_map,
    _serialize_application_summary,
)
from kernel_api.rpc.functions.admin.common import (
    REQUIRED_TENANT_SCHEMA,
    build_response,
    get_bk_tenant_id,
)
from kernel_api.rpc.functions.admin.custom_report import (
    REPORT_TYPE_EVENT,
    REPORT_TYPE_LOG,
    REPORT_TYPE_METRIC,
    _serialize_event_group,
    _serialize_log_datasource,
    _serialize_time_series_group,
)


class _LazyApmModels:
    def __getattr__(self, name: str) -> Any:
        from apm import models as apm_models

        return getattr(apm_models, name)


class _LazyMetadataModels:
    def __getattr__(self, name: str) -> Any:
        from metadata import models as metadata_models

        return getattr(metadata_models, name)


apm_models = _LazyApmModels()
metadata_models = _LazyMetadataModels()

logger = logging.getLogger(__name__)

FUNC_TOKEN_RESOLVE = "admin.token.resolve"

KIND_APM = "apm"
KIND_CUSTOM_METRIC = REPORT_TYPE_METRIC
KIND_CUSTOM_EVENT = REPORT_TYPE_EVENT
KIND_CUSTOM_LOG = REPORT_TYPE_LOG


class ParsedApmToken(NamedTuple):
    """APM SDK token AES 解密后的载荷。

    SDK 历史上有两个版本：
        v0：metric / trace / log / bk_biz_id / app_name（4 个 salt 分隔符，5 个字段）
        v1：v1 / metric / trace / log / profile / bk_biz_id / app_name（6 个分隔符，7 个字段）

    任意 *_data_id 字段为 -1 表示该信号未启用，反查时需要忽略掉。
    """

    version: str  # "v0" 或 "v1"
    metric_data_id: int
    trace_data_id: int
    log_data_id: int
    profile_data_id: int
    bk_biz_id: int
    app_name: str


def parse_apm_token(token: str) -> ParsedApmToken | None:
    """尝试用 BK_DATA_TOKEN_SALT 解密 APM SDK token。失败时返回 None。

    解密 + 解析失败属于 expected error path：错误的 token、错误的密钥都会触发；
    日志降到 debug 级别避免噪音。
    """
    from bkmonitor.utils.cipher import AESCipher, get_bk_data_token_aes_key

    try:
        aes_key = get_bk_data_token_aes_key()
        cipher = AESCipher(aes_key, settings.BK_DATA_AES_IV)
        decrypted = cipher.decrypt(token)
    except Exception as exc:  # noqa: BLE001 — 解密失败属于预期路径，吞掉返回 None
        logger.debug("parse_apm_token: decrypt failed for token prefix=%r: %s", token[:6], exc)
        return None

    salt = settings.BK_DATA_TOKEN_SALT
    parts = decrypted.split(salt)

    try:
        if parts and parts[0] == "v1" and len(parts) >= 7:
            return ParsedApmToken(
                version="v1",
                metric_data_id=int(parts[1]),
                trace_data_id=int(parts[2]),
                log_data_id=int(parts[3]),
                profile_data_id=int(parts[4]),
                bk_biz_id=int(parts[5]),
                # app_name 内可能含分隔符 "bk"，把后续片段重新拼回去。
                app_name=salt.join(parts[6:]),
            )
        if len(parts) >= 5:
            return ParsedApmToken(
                version="v0",
                metric_data_id=int(parts[0]),
                trace_data_id=int(parts[1]),
                log_data_id=int(parts[2]),
                profile_data_id=-1,
                bk_biz_id=int(parts[3]),
                app_name=salt.join(parts[4:]),
            )
    except (TypeError, ValueError) as exc:
        logger.debug("parse_apm_token: parse failed (parts=%r): %s", parts, exc)
        return None

    logger.debug("parse_apm_token: unrecognized layout (parts=%r)", parts)
    return None


def _resolve_apm_application_from_parsed_token(bk_tenant_id: str, parsed: ParsedApmToken) -> Any | None:
    """根据解密结果反查 ApmApplication：先用 (bk_biz_id, app_name) 精确匹配，命中即返回；
    否则按任一非空 data_id 在 APM DataSource 表上反查 (bk_biz_id, app_name)。

    仅在 token 携带 trace_data_id 时调用 —— trace 存在表示这是一个 APM 应用，不是自定义上报。
    """
    queryset = apm_models.ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id)

    if parsed.app_name:
        primary = (
            queryset.filter(bk_biz_id=parsed.bk_biz_id, app_name=parsed.app_name).order_by("id").first()
        )
        if primary is not None:
            return primary

    candidate_data_ids = [
        data_id
        for data_id in (
            parsed.metric_data_id,
            parsed.trace_data_id,
            parsed.log_data_id,
            parsed.profile_data_id,
        )
        if isinstance(data_id, int) and data_id > 0
    ]
    if not candidate_data_ids:
        return None

    # MetricDataSource / TraceDataSource / LogDataSource / ProfileDataSource 都挂在同一个
    # apm_models 命名空间下，分别有 (bk_biz_id, app_name) 联合索引。任意一个命中都能定位回应用。
    datasource_class_names = (
        "MetricDataSource",
        "TraceDataSource",
        "LogDataSource",
        "ProfileDataSource",
    )
    for class_name in datasource_class_names:
        try:
            datasource_cls = getattr(apm_models, class_name)
        except AttributeError:
            continue
        ds = (
            datasource_cls.objects.filter(bk_data_id__in=candidate_data_ids).order_by("bk_data_id").first()
        )
        if ds is None:
            continue
        application = (
            queryset.filter(bk_biz_id=ds.bk_biz_id, app_name=ds.app_name).order_by("id").first()
        )
        if application is not None:
            return application

    return None


def _resolve_time_series_group_by_data_id(bk_tenant_id: str, bk_data_id: int) -> Any | None:
    return (
        metadata_models.TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, is_delete=False, bk_data_id=bk_data_id
        )
        .order_by("time_series_group_id")
        .first()
    )


def _resolve_log_group_by_data_id(bk_tenant_id: str, bk_data_id: int) -> Any | None:
    return (
        metadata_models.LogGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, is_delete=False, bk_data_id=bk_data_id
        )
        .order_by("log_group_id")
        .first()
    )


def _empty_payload(token: str, *, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "matched": False,
        "kind": None,
        "token": token,
        "apm_application": None,
        "custom_report": None,
        "warnings": warnings or [],
    }


def _serialize_apm_application_with_token(application: Any) -> dict[str, Any]:
    datasource_maps = _load_apm_datasource_maps([application])
    service_count_map = _load_service_count_map([application])
    summary = _serialize_application_summary(application, datasource_maps, service_count_map)
    summary["app_token"] = getattr(application, "token", None) or None
    return summary


def _resolve_apm_application(bk_tenant_id: str, token: str) -> Any | None:
    return (
        apm_models.ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id, token=token)
        .order_by("id")
        .first()
    )


def _resolve_time_series_group(bk_tenant_id: str, token: str) -> Any | None:
    return (
        metadata_models.TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, is_delete=False, token=token
        )
        .order_by("time_series_group_id")
        .first()
    )


def _serialize_time_series_with_token(group: Any) -> dict[str, Any]:
    summary = _serialize_time_series_group(group, metric_counts={})
    summary["token"] = getattr(group, "token", None) or None
    return summary


def _resolve_event_group(bk_tenant_id: str, token: str) -> Any | None:
    return (
        metadata_models.EventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, is_delete=False, token=token
        )
        .order_by("event_group_id")
        .first()
    )


def _serialize_event_with_token(group: Any) -> dict[str, Any]:
    summary = _serialize_event_group(group)
    summary["token"] = getattr(group, "token", None) or None
    return summary


def _resolve_log_group(bk_tenant_id: str, token: str) -> Any | None:
    # LogGroup 主字段 token 来自 CustomGroupBase；老数据可能仅写入了 bk_data_token，因此一并兜底。
    return (
        metadata_models.LogGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False)
        .filter(Q(token=token) | Q(bk_data_token=token))
        .order_by("log_group_id")
        .first()
    )


def _serialize_log_with_token(group: Any) -> dict[str, Any]:
    datasource = (
        metadata_models.DataSource.objects.filter(
            bk_tenant_id=group.bk_tenant_id, bk_data_id=group.bk_data_id
        ).first()
    )
    if datasource is None:
        # 没有关联 DataSource 时，提供尽量完整的兜底数据（沿用 CustomReportSummary 字段）。
        summary: dict[str, Any] = {
            "report_type": REPORT_TYPE_LOG,
            "group_id": group.bk_data_id,
            "group_name": group.log_group_name,
            "bk_tenant_id": group.bk_tenant_id,
            "bk_biz_id": group.bk_biz_id,
            "bk_data_id": group.bk_data_id,
            "table_id": group.table_id,
            "data_label": None,
            "created_from": None,
            "is_enable": group.is_enable,
            "metric_count": 0,
            "field_count": 0,
            "last_modify_time": (
                group.last_modify_time.strftime("%Y-%m-%d %H:%M:%S") if group.last_modify_time else None
            ),
        }
    else:
        summary = _serialize_log_datasource(datasource)
        # 用 LogGroup 的 group_name 覆盖 DataSource.data_name，避免与列表语义割裂。
        summary["group_name"] = group.log_group_name
        summary["table_id"] = group.table_id or summary.get("table_id")
        summary["bk_biz_id"] = group.bk_biz_id

    summary["token"] = getattr(group, "token", None) or getattr(group, "bk_data_token", None) or None
    return summary


@KernelRPCRegistry.register(
    FUNC_TOKEN_RESOLVE,
    summary="Admin 通过 SDK Token 反查所属资源",
    description=(
        "按租户精确匹配 ApmApplication.token / TimeSeriesGroup.token / EventGroup.token / "
        "LogGroup.token (兼容老字段 bk_data_token)；DB 全部 miss 时再 AES 解密 token，"
        "按 data_id 形态判定：trace → APM 应用、仅 metric → 自定义指标、仅 log → 自定义日志。"
        "返回首个命中的资源摘要。"
    ),
    params_schema={
        "bk_tenant_id": REQUIRED_TENANT_SCHEMA,
        "token": "必填，SDK 上报使用的 Token 字符串",
    },
    example_params={"bk_tenant_id": "system", "token": "9b3a4f8d3c1241eaa1f7c2d4e5b6a7c8"},
)
def resolve_token(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    raw_token = params.get("token")
    token = raw_token.strip() if isinstance(raw_token, str) else ""

    if not token:
        # 不抛 422，让前端能稳定地拿到 matched=false 渲染“未命中”，复合 read 语义。
        return build_response(
            operation="token.resolve",
            func_name=FUNC_TOKEN_RESOLVE,
            bk_tenant_id=bk_tenant_id,
            data=_empty_payload("", warnings=["token 为空"]),
        )

    apm_application = _resolve_apm_application(bk_tenant_id, token)
    if apm_application is not None:
        return build_response(
            operation="token.resolve",
            func_name=FUNC_TOKEN_RESOLVE,
            bk_tenant_id=bk_tenant_id,
            data={
                "matched": True,
                "kind": KIND_APM,
                "token": token,
                "apm_application": _serialize_apm_application_with_token(apm_application),
                "custom_report": None,
                "warnings": [],
            },
        )

    time_series_group = _resolve_time_series_group(bk_tenant_id, token)
    if time_series_group is not None:
        return build_response(
            operation="token.resolve",
            func_name=FUNC_TOKEN_RESOLVE,
            bk_tenant_id=bk_tenant_id,
            data={
                "matched": True,
                "kind": KIND_CUSTOM_METRIC,
                "token": token,
                "apm_application": None,
                "custom_report": _serialize_time_series_with_token(time_series_group),
                "warnings": [],
            },
        )

    event_group = _resolve_event_group(bk_tenant_id, token)
    if event_group is not None:
        return build_response(
            operation="token.resolve",
            func_name=FUNC_TOKEN_RESOLVE,
            bk_tenant_id=bk_tenant_id,
            data={
                "matched": True,
                "kind": KIND_CUSTOM_EVENT,
                "token": token,
                "apm_application": None,
                "custom_report": _serialize_event_with_token(event_group),
                "warnings": [],
            },
        )

    log_group = _resolve_log_group(bk_tenant_id, token)
    if log_group is not None:
        return build_response(
            operation="token.resolve",
            func_name=FUNC_TOKEN_RESOLVE,
            bk_tenant_id=bk_tenant_id,
            data={
                "matched": True,
                "kind": KIND_CUSTOM_LOG,
                "token": token,
                "apm_application": None,
                "custom_report": _serialize_log_with_token(log_group),
                "warnings": [],
            },
        )

    # DB 字段全部 miss，尝试 AES 解密反查（兼容历史动态 token）。
    # 解析失败 → unmatched；
    # 解析成功后按 data_id 形态判定资源类型：
    #   - 含 trace_data_id → APM 应用（trace 存在即认为是 APM）
    #   - 仅含 metric_data_id（无 trace 无 log）→ 自定义指标 (TimeSeriesGroup by bk_data_id)
    #   - 仅含 log_data_id（无 trace 无 metric）→ 自定义日志 (LogGroup by bk_data_id)
    #   - 其他组合（含混合且无 trace）→ unmatched
    parsed = parse_apm_token(token)
    if parsed is not None:
        has_metric = isinstance(parsed.metric_data_id, int) and parsed.metric_data_id > 0
        has_trace = isinstance(parsed.trace_data_id, int) and parsed.trace_data_id > 0
        has_log = isinstance(parsed.log_data_id, int) and parsed.log_data_id > 0
        warning = "命中来源：AES 反向解析"

        if has_trace:
            application = _resolve_apm_application_from_parsed_token(bk_tenant_id, parsed)
            if application is not None:
                return build_response(
                    operation="token.resolve",
                    func_name=FUNC_TOKEN_RESOLVE,
                    bk_tenant_id=bk_tenant_id,
                    data={
                        "matched": True,
                        "kind": KIND_APM,
                        "token": token,
                        "apm_application": _serialize_apm_application_with_token(application),
                        "custom_report": None,
                        "warnings": [warning],
                    },
                )
        elif has_metric and not has_log:
            ts_group = _resolve_time_series_group_by_data_id(bk_tenant_id, parsed.metric_data_id)
            if ts_group is not None:
                return build_response(
                    operation="token.resolve",
                    func_name=FUNC_TOKEN_RESOLVE,
                    bk_tenant_id=bk_tenant_id,
                    data={
                        "matched": True,
                        "kind": KIND_CUSTOM_METRIC,
                        "token": token,
                        "apm_application": None,
                        "custom_report": _serialize_time_series_with_token(ts_group),
                        "warnings": [warning],
                    },
                )
        elif has_log and not has_metric:
            log_group = _resolve_log_group_by_data_id(bk_tenant_id, parsed.log_data_id)
            if log_group is not None:
                return build_response(
                    operation="token.resolve",
                    func_name=FUNC_TOKEN_RESOLVE,
                    bk_tenant_id=bk_tenant_id,
                    data={
                        "matched": True,
                        "kind": KIND_CUSTOM_LOG,
                        "token": token,
                        "apm_application": None,
                        "custom_report": _serialize_log_with_token(log_group),
                        "warnings": [warning],
                    },
                )

    return build_response(
        operation="token.resolve",
        func_name=FUNC_TOKEN_RESOLVE,
        bk_tenant_id=bk_tenant_id,
        data=_empty_payload(token),
    )
