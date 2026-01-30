"""导出 Handler 定义

说明:
    - 表级 handlers: `TABLE_HANDLER_MAPPING`，按 model_label 配置（例如 `metadata.ResultTable`）
    - 通配 handlers: key='*'，会被追加到每张表 handlers 的最后执行
    - 全局 handlers: `GLOBAL_HANDLERS`，用于跨表处理
      - 必须通过 required_models 显式声明依赖的模型集合
      - 框架只会为被依赖模型收集内存数据，其他模型会直接落地
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from ...utils.types import RowDict, RowHandlerFn

# 表级别 Handler 映射
#
# key 支持两类：
# - "app_label.ModelName"：指定单张表的 handlers
# - "*"：通配 handlers，会被追加到每张表 handlers 的最后执行
TABLE_HANDLER_MAPPING: dict[str, list[RowHandlerFn]] = {}


class GlobalHandlerContext:
    """全局 handler 执行上下文

    说明：
        - 全局 handler 必须提前声明依赖的模型（required_models）
        - 框架只会为被依赖的模型收集内存数据，并通过 ctx.get/ctx.set 交互
        - ctx.set 覆盖整张表的数据，丢弃/过滤可在 handler 内自行完成
    """

    def __init__(self, data_by_model: dict[str, list[RowDict]], allowed_models: set[str]):
        self._data_by_model = data_by_model
        self._allowed_models = allowed_models

    def get(self, model_label: str) -> list[RowDict]:
        """获取某张表的导出数据"""
        if model_label not in self._allowed_models:
            raise KeyError(f"全局 handler 未声明依赖模型: {model_label}")
        return self._data_by_model.get(model_label, [])

    def set(self, model_label: str, rows: list[RowDict]) -> None:
        """覆盖某张表的导出数据"""
        if model_label not in self._allowed_models:
            raise KeyError(f"全局 handler 未声明依赖模型: {model_label}")
        self._data_by_model[model_label] = rows


class GlobalHandlerFn(Protocol):
    """全局 handler 函数签名"""

    def __call__(self, ctx: GlobalHandlerContext) -> None: ...


@dataclass(frozen=True)
class GlobalHandlerSpec:
    """全局 handler 定义"""

    name: str
    required_models: set[str]
    fn: GlobalHandlerFn


# 全局 handler 列表（按顺序执行）
GLOBAL_HANDLERS: list[GlobalHandlerSpec] = []


def disable_enable_fields(row: RowDict) -> RowDict | None:
    """将 enable/is_enable 字段置为 False

    Args:
        row: 原始数据行

    Returns:
        处理后的数据行
    """

    if "enable" not in row and "is_enable" not in row:
        return row
    if row.get("enable") is False and row.get("is_enable") is False:
        return row
    updated = dict(row)
    if "enable" in updated:
        updated["enable"] = False
    if "is_enable" in updated:
        updated["is_enable"] = False
    return updated


# 内置数据源列表
BUILTIN_DATASOURCES: dict[int, str] = {
    # 监控平台运营数据
    1100013: "2_bkm_statistics",
    1100011: "2_custom_report_aggate_dataid",
    1100012: "2_operation_data_custom_series",  # 已废弃
    # bk-collector/bkm-operator
    1100014: "2_datalink_stats",
    # bkmonitorbeat 心跳及任务执行状态
    1100001: "heartbeat_total",
    1100002: "heartbeat_child",
    1100017: "2_bkmonitorbeat_gather_up",
    # 日志采集器
    1100006: "bkunifylogbeat common metrics",
    1100007: "bkunifylogbeat task metrics",
    1100015: "2_bkunifylogbeat_k8s_common",
    1100016: "2_bkunifylogbeat_k8s_task",
    # 内置主机数据
    1001: "snapshot",
    # 内置事件
    1100008: "gse_process_event_report",
    1000: "base_alarm",
    1100000: "cmd_report",
    # 旧版内置插件
    1002: "mysql",
    1005: "nginx",
    1004: "apache",
    1003: "redis",
    1006: "tomcat",
    # 内置拨测数据源
    1100005: "pingserver",
    # 内置进程采集插件
    1007: "process_perf",
    1013: "process_port",
    # 内置拨测数据源
    1008: "uptimecheck_heartbeat",
    1011: "uptimecheck_http",
    1100003: "uptimecheck_icmp",
    1009: "uptimecheck_tcp",
    1010: "uptimecheck_udp",
}


@lru_cache(maxsize=1)
def get_builtin_table_ids() -> set[str]:
    from metadata.models import DataSourceResultTable

    return set(
        DataSourceResultTable.objects.filter(bk_data_id__in=list(BUILTIN_DATASOURCES.keys())).values_list(
            "table_id", flat=True
        )
    )


def filter_builtin_datasource(row: RowDict) -> RowDict | None:
    """过滤内置数据源

    Args:
        row: 原始数据行

    Returns:
        如果数据源是内置数据源，则返回 None，否则返回原始数据行
    """
    if row["bk_data_id"] in BUILTIN_DATASOURCES:
        return None
    return row


def filter_builtin_result_table(row: RowDict) -> RowDict | None:
    """过滤内置结果表

    Args:
        row: 原始数据行

    Returns:
        如果结果表是内置结果表，则返回 None，否则返回原始数据行
    """
    for table_field in ["table_id", "result_table_id"]:
        if table_field not in row:
            continue
        if row[table_field] in get_builtin_table_ids():
            return None
    return row


TABLE_HANDLER_MAPPING.update(
    {
        "metadata.DataSource": [filter_builtin_datasource, disable_enable_fields],
        "metadata.DataSourceOption": [filter_builtin_datasource],
        "metadata.DataSourceResultTable": [filter_builtin_datasource],
        "metadata.ResultTable": [filter_builtin_result_table, disable_enable_fields],
        "metadata.ResultTableOption": [filter_builtin_result_table],
        "metadata.ResultTableField": [filter_builtin_result_table],
        "metadata.ResultTableFieldOption": [filter_builtin_result_table],
        "metadata.TimeSeriesGroup": [filter_builtin_result_table],
        "metadata.TimeSeriesMetric": [filter_builtin_result_table],
    }
)
