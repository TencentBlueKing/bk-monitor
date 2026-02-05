"""handle 内置处理函数集合。

该文件只包含“内置规则/默认处理”相关逻辑，避免与 handle 的核心 pipeline 机制耦合在一起。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_migration.config import BIZ_TENANT_ID_MAPPING, DEFAULT_TARGET_TENANT_ID
from data_migration.utils.types import RowDict

from .biz_filter import get_row_biz_id

_ENABLE_FIELD_RECORDS: list[dict[str, Any]] = []
_ENABLE_FIELD_RECORD_PATH: Path | None = None
_ENABLE_FIELD_HANDLED_AT: str | None = None
_ENABLE_FIELD_RECORDING_ENABLED = False


def configure_enable_field_recording(output_dir: Path | None, handled_at: str | None, enabled: bool) -> None:
    """配置 enable 字段记录开关。

    Args:
        output_dir: handle 输出目录
        handled_at: 处理时间（ISO8601）
        enabled: 是否启用记录
    """
    global _ENABLE_FIELD_RECORDS, _ENABLE_FIELD_RECORD_PATH, _ENABLE_FIELD_HANDLED_AT, _ENABLE_FIELD_RECORDING_ENABLED

    _ENABLE_FIELD_RECORDS = []
    _ENABLE_FIELD_RECORD_PATH = None
    _ENABLE_FIELD_HANDLED_AT = handled_at
    _ENABLE_FIELD_RECORDING_ENABLED = False

    if not enabled or output_dir is None:
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    _ENABLE_FIELD_RECORD_PATH = output_dir / "disable_enable_fields_enabled_rows.json"
    _ENABLE_FIELD_RECORDING_ENABLED = True


def flush_enable_field_records() -> None:
    """写出 enable 字段记录到 JSON 文件。"""
    if not _ENABLE_FIELD_RECORDING_ENABLED or _ENABLE_FIELD_RECORD_PATH is None:
        return

    payload = {
        "handled_at": _ENABLE_FIELD_HANDLED_AT,
        "total": len(_ENABLE_FIELD_RECORDS),
        "items": _ENABLE_FIELD_RECORDS,
    }
    _ENABLE_FIELD_RECORD_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_enable_field_row(model_label: str, row: RowDict, enabled_fields: dict[str, Any]) -> None:
    """记录原本启用的行数据。

    Args:
        model_label: 模型标签
        row: 原始行数据
        enabled_fields: 原本启用的字段映射
    """
    if not _ENABLE_FIELD_RECORDING_ENABLED:
        return
    _ENABLE_FIELD_RECORDS.append(
        {
            "model_label": model_label,
            "enabled_fields": enabled_fields,
            "row": dict(row),
        }
    )


# 内置数据源列表
# BUILTIN_DATASOURCES: dict[int, str] = {
#     # 监控平台运营数据
#     1100013: "2_bkm_statistics",
#     1100011: "2_custom_report_aggate_dataid",
#     1100012: "2_operation_data_custom_series",  # 已废弃
#     # bk-collector/bkm-operator
#     1100014: "2_datalink_stats",
#     # bkmonitorbeat 心跳及任务执行状态
#     1100001: "heartbeat_total",
#     1100002: "heartbeat_child",
#     1100017: "2_bkmonitorbeat_gather_up",
#     # 日志采集器
#     1100006: "bkunifylogbeat common metrics",
#     1100007: "bkunifylogbeat task metrics",
#     1100015: "2_bkunifylogbeat_k8s_common",
#     1100016: "2_bkunifylogbeat_k8s_task",
#     # 内置主机数据
#     1001: "snapshot",
#     # 内置事件
#     1100008: "gse_process_event_report",
#     1000: "base_alarm",
#     1100000: "cmd_report",
#     1100031: "system_base_events",
#     # 旧版内置插件
#     1002: "mysql",
#     1005: "nginx",
#     1004: "apache",
#     1003: "redis",
#     1006: "tomcat",
#     # 内置拨测数据源
#     1100005: "pingserver",
#     # 内置进程采集插件
#     1007: "process_perf",
#     1013: "process_port",
#     # 内置拨测数据源
#     1008: "uptimecheck_heartbeat",
#     1011: "uptimecheck_http",
#     1100003: "uptimecheck_icmp",
#     1009: "uptimecheck_tcp",
#     1010: "uptimecheck_udp",

# }


# def _get_builtin_table_ids() -> set[str]:
#     """获取内置结果表ID。

#     Returns:
#         内置结果表ID集合
#     """
#     from functools import lru_cache

#     @lru_cache(maxsize=1)
#     def _cached_get() -> set[str]:
#         from metadata.models import DataSourceResultTable

#         return set(
#             DataSourceResultTable.objects.filter(bk_data_id__in=list(BUILTIN_DATASOURCES.keys())).values_list(
#                 "table_id", flat=True
#             )
#         )

#     return _cached_get()


# def _get_builtin_datasource_ids() -> set[int]:
#     """获取内置数据源ID。

#     Returns:
#         内置数据源ID集合
#     """
#     return set(BUILTIN_DATASOURCES.keys())


# def filter_builtin_datasource(row: RowDict) -> RowDict | None:
#     """过滤内置数据源。

#     Args:
#         row: 原始数据行

#     Returns:
#         如果数据源是内置数据源，则返回 None，否则返回原始数据行
#     """
#     if row["bk_data_id"] in _get_builtin_datasource_ids():
#         return None
#     return row


# def filter_builtin_result_table(row: RowDict) -> RowDict | None:
#     """过滤内置结果表。

#     Args:
#         row: 原始数据行

#     Returns:
#         如果结果表是内置结果表，则返回 None，否则返回原始数据行
#     """
#     for table_field in ["table_id", "result_table_id", "monitor_table_id"]:
#         if table_field not in row:
#             continue
#         if row[table_field] in _get_builtin_table_ids():
#             return None
#     return row


def filter_is_deleted(rows: list[RowDict], model_label: str) -> list[RowDict]:
    """过滤 is_deleted 字段为 True 的数据。"""
    result: list[RowDict] = []
    for row in rows:
        # 如果没有 is_deleted 字段，则直接保留，字段名都相同，因此直接返回
        if "is_deleted" not in row:
            return rows
        if row["is_deleted"]:
            continue
        result.append(row)
    return result


def disable_enable_fields(rows: list[RowDict], model_label: str) -> list[RowDict]:
    """将 enable 字段置为 False。

    Args:
        rows: 原始数据行列表
        model_label: 模型标签（app_label.ModelName）

    Returns:
        处理后的数据行列表
    """
    enable_fields = ["enable", "is_enable", "is_enabled"]

    for row in rows:
        original_row = dict(row)
        enabled_fields: dict[str, Any] = {}
        for field in enable_fields:
            if field not in row:
                continue
            if row[field]:
                enabled_fields[field] = row[field]
                row[field] = False
        if enabled_fields:
            _record_enable_field_row(model_label, original_row, enabled_fields)
    return rows


def _resolve_tenant_id(biz_id: int | None) -> str:
    """根据业务ID解析租户ID。

    Args:
        biz_id: 业务ID

    Returns:
        目标租户ID
    """
    if biz_id is None:
        return DEFAULT_TARGET_TENANT_ID
    return BIZ_TENANT_ID_MAPPING.get(biz_id, DEFAULT_TARGET_TENANT_ID)


def replace_bk_tenant_id(rows: list[RowDict], model_label: str) -> list[RowDict]:
    """替换租户ID。

    Args:
        rows: 原始数据行列表
        model_label: 模型标签（app_label.ModelName）

    Returns:
        处理后的数据行列表
    """
    for row in rows:
        if "bk_tenant_id" not in row:
            continue
        biz_id = get_row_biz_id(row, model_label)
        row["bk_tenant_id"] = _resolve_tenant_id(biz_id)
    return rows


def replace_bk_tenant_id_for_biz(rows: list[RowDict], biz_id: int | None) -> list[RowDict]:
    """按业务替换租户ID。

    Args:
        rows: 原始数据行列表
        biz_id: 业务ID

    Returns:
        原始数据行列表
    """
    target_tenant_id = _resolve_tenant_id(biz_id)
    for row in rows:
        if "bk_tenant_id" not in row:
            continue
        row["bk_tenant_id"] = target_tenant_id
    return rows
