import re
from collections.abc import Sequence

from metadata.models.custom_report import Event, EventGroup, LogGroup, TimeSeriesGroup, TimeSeriesMetric
from metadata.models.data_source import DataSource, DataSourceOption, DataSourceResultTable
from metadata.models.result_table import ResultTable, ResultTableField, ResultTableFieldOption, ResultTableOption
from metadata.models.storage import KafkaTopicInfo
from monitor_web.data_migrate.fetcher.base import FetcherResultType

_BKLOG_TABLE_ID_RE = re.compile(r"^(\d+_bklog)\.(.+)$")


def _normalize_data_ids(data_ids: Sequence[int] | None) -> list[int]:
    """将 data_id 输入规范化为列表。"""
    return list(data_ids or [])


def _normalize_table_ids(table_ids: Sequence[str] | None) -> list[str]:
    """将 table_id 输入规范化为列表。"""
    return list(table_ids or [])


def _to_log_group_table_ids(table_ids: list[str]) -> list[str]:
    """将 ResultTable 格式的 table_id 转换为 LogGroup 兼容的格式。

    LogGroup.make_table_id 生成的 table_id 使用下划线分隔（如 ``19078_bklog_test``），
    而 ResultTable 的 table_id 使用点号分隔（如 ``19078_bklog.test``）。
    本函数同时保留两种格式，确保 LogGroup 查询能命中。
    """
    result: list[str] = list(table_ids)
    for table_id in table_ids:
        m = _BKLOG_TABLE_ID_RE.match(table_id)
        if m:
            result.append(f"{m.group(1)}_{m.group(2)}")
    return result


def get_metadata_data_source_fetcher(data_ids: Sequence[int] | None) -> list[FetcherResultType]:
    """
    按 data_ids 获取 metadata 中 data source 这一层相关表。

    - ``DataSource`` / ``DataSourceOption`` / ``KafkaTopicInfo`` 直接按 ``bk_data_id`` 过滤
    - ``DataSourceResultTable`` 也按 ``bk_data_id`` 过滤
    """
    normalized_data_ids = _normalize_data_ids(data_ids)

    return [
        (DataSource, {"bk_data_id__in": normalized_data_ids}, None),
        (DataSourceOption, {"bk_data_id__in": normalized_data_ids}, None),
        (KafkaTopicInfo, {"bk_data_id__in": normalized_data_ids}, None),
        (DataSourceResultTable, {"bk_data_id__in": normalized_data_ids}, None),
    ]


def get_metadata_result_table_fetcher(table_ids: Sequence[str] | None) -> list[FetcherResultType]:
    """
    按 table_ids 获取 metadata 中 result table 这一层相关表。

    这里覆盖两类表：
    - 结果表本身及其字段/选项
    - 以 ``table_id`` 为根的 custom report 表
    """
    normalized_table_ids = _normalize_table_ids(table_ids)
    time_series_group_ids = TimeSeriesGroup.objects.filter(table_id__in=normalized_table_ids).values_list(
        "time_series_group_id", flat=True
    )
    event_group_ids = EventGroup.objects.filter(table_id__in=normalized_table_ids).values_list(
        "event_group_id", flat=True
    )

    log_group_table_ids = _to_log_group_table_ids(normalized_table_ids)

    return [
        (ResultTable, {"table_id__in": normalized_table_ids}, None),
        (ResultTableOption, {"table_id__in": normalized_table_ids}, None),
        (ResultTableField, {"table_id__in": normalized_table_ids}, None),
        (ResultTableFieldOption, {"table_id__in": normalized_table_ids}, None),
        (TimeSeriesGroup, {"table_id__in": normalized_table_ids}, None),
        (TimeSeriesMetric, {"group_id__in": time_series_group_ids}, None),
        (EventGroup, {"table_id__in": normalized_table_ids}, None),
        (Event, {"event_group_id__in": event_group_ids}, None),
        (LogGroup, {"table_id__in": log_group_table_ids}, None),
    ]
