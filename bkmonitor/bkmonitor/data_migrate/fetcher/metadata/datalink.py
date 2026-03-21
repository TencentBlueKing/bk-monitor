from collections.abc import Sequence

from bkmonitor.data_migrate.fetcher.base import FetcherResultType
from metadata.models import BkBaseResultTable, DataBusConfig, DataIdConfig, DataLink
from metadata.models.data_link import (
    ConditionalSinkConfig,
    DorisStorageBindingConfig,
    ESStorageBindingConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)


def _normalize_table_ids(table_ids: Sequence[str] | None) -> list[str]:
    """将 table_id 输入规范化为列表。"""
    return list(table_ids or [])


def get_metadata_datalink_fetcher(table_ids: Sequence[str] | None) -> list[FetcherResultType]:
    """
    按 table_ids 获取 Metadata 中与 datalink 相关的表。

    收敛规则：
    - ``BkBaseResultTable`` 直接按 ``monitor_table_id`` 过滤
    - ``DataLink`` 通过 ``BkBaseResultTable.data_link_name`` 回查
    - 各组件配置统一按 ``data_link_name`` 过滤

    ``ClusterConfig`` 已并入集群层 fetcher，不在这里重复导出。
    """
    normalized_table_ids = _normalize_table_ids(table_ids)
    data_link_names = BkBaseResultTable.objects.filter(monitor_table_id__in=normalized_table_ids).values_list(
        "data_link_name", flat=True
    )

    return [
        (BkBaseResultTable, {"monitor_table_id__in": normalized_table_ids}, None),
        (DataLink, {"data_link_name__in": data_link_names}, None),
        (DataIdConfig, {"data_link_name__in": data_link_names}, None),
        (DataBusConfig, {"data_link_name__in": data_link_names}, None),
        (ResultTableConfig, {"data_link_name__in": data_link_names}, None),
        (ESStorageBindingConfig, {"data_link_name__in": data_link_names}, None),
        (VMStorageBindingConfig, {"data_link_name__in": data_link_names}, None),
        (DorisStorageBindingConfig, {"data_link_name__in": data_link_names}, None),
        (ConditionalSinkConfig, {"data_link_name__in": data_link_names}, None),
    ]
