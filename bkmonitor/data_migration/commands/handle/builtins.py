"""handle 内置处理函数集合。

该文件只包含“内置规则/默认处理”相关逻辑，避免与 handle 的核心 pipeline 机制耦合在一起。
"""

from __future__ import annotations

from data_migration.config import BIZ_TENANT_ID_MAPPING, DEFAULT_TARGET_TENANT_ID, EXCLUDED_BIZ_IDS

from ...utils.types import RowDict
from .biz_filter import get_row_biz_id

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
        for field in enable_fields:
            if field not in row:
                continue
            if row[field]:
                row[field] = False
    return rows


def replace_bk_tenant_id(rows: list[RowDict], model_label: str) -> list[RowDict]:
    """替换租户ID，并根据业务ID过滤数据。

    处理逻辑：
    1. 跳过 metadata 表（由 filter_metadata_by_biz 专门处理）
    2. 排除指定业务（EXCLUDED_BIZ_IDS）的数据
    3. 根据业务ID映射（BIZ_TENANT_ID_MAPPING）决定租户ID
    4. 默认使用 DEFAULT_TARGET_TENANT_ID

    Args:
        rows: 原始数据行列表
        model_label: 模型标签（app_label.ModelName）

    Returns:
        处理后的数据行列表（已过滤排除业务的数据）

    Note:
        metadata 表的 bk_biz_id 字段可能不正确，需要通过关联链路推导业务归属，
        因此由 filter_metadata_by_biz 函数专门处理。
    """
    # 跳过 metadata 表，由专门的 filter_metadata_by_biz 处理
    if model_label.startswith("metadata."):
        return rows

    result: list[RowDict] = []

    for row in rows:
        # 检测业务ID（传入 model_label 以支持关联推导）
        biz_id = get_row_biz_id(row, model_label)

        # 排除指定业务的数据
        if biz_id in EXCLUDED_BIZ_IDS:
            continue

        # 如果没有 bk_tenant_id 字段，仅做过滤，直接保留
        if "bk_tenant_id" not in row:
            result.append(row)
            continue

        # 如果业务ID为空，则使用默认租户ID
        if biz_id is None:
            row["bk_tenant_id"] = DEFAULT_TARGET_TENANT_ID
            result.append(row)
            continue

        # 确定租户ID
        row["bk_tenant_id"] = BIZ_TENANT_ID_MAPPING.get(biz_id, DEFAULT_TARGET_TENANT_ID)
        result.append(row)

    return result
