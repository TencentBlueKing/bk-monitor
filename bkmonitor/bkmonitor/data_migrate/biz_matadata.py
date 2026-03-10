"""
查询业务下关联的结果表和数据ID

可以通过DataSourceResultTable对结果表和数据ID进行关联查询

1. 自定义指标 CustomTSTable，全局数据也能归属到业务下，不能归属到业务0
2. 自定义事件 CustomEventGroup, 全局数据也能归属到业务下，不能归属到业务0
3. 采集插件 需要分类讨论，全局插件属于业务0 可以参考 data_access.py
4. 日志平台数据，bk_flat_batch类的ResultTable(需要排查apm trace)，都可以归属到业务下
5. 容器采集 BCSClusterInfo，都可以归属的业务下
6. 服务拨测 uptimechecktask， 参考UptimecheckDataAccessor，部分业务存在业务独立的结果表和数据ID，内置的拨测结果表和数据ID不需要处理，不需要归入业务0
7. APM ApmApplication 根据apm的接入表查询，都能按业务区分，不存在业务0
"""

from collections.abc import Iterable

from apm.models import LogDataSource, MetricDataSource, ProfileDataSource, TraceDataSource
from metadata.migration_util import filter_apm_log_table_ids
from metadata.models import BCSClusterInfo, DataSource, DataSourceResultTable, ResultTable
from monitor.models import UptimeCheckTask
from monitor_web.constants import EVENT_TYPE
from monitor_web.models import CollectorPluginMeta, CustomEventGroup, CustomTSTable, PluginVersionHistory
from monitor_web.plugin.constant import PluginType


INVALID_DATA_ID_VALUES = {None, 0, -1}
INVALID_TABLE_ID_VALUES = {None, ""}


def _add_data_ids(container: set[int], values: Iterable[int | None]) -> None:
    for value in values:
        if value not in INVALID_DATA_ID_VALUES:
            container.add(value)


def _add_table_ids(container: set[str], values: Iterable[str | None]) -> None:
    for value in values:
        if value not in INVALID_TABLE_ID_VALUES:
            container.add(value)


def _add_dsrt_table_ids(container: set[str], data_ids: Iterable[int]) -> None:
    _add_table_ids(
        container,
        DataSourceResultTable.objects.filter(bk_data_id__in=list(data_ids))
        .values_list("table_id", flat=True)
        .distinct(),
    )


def _collect_custom_report_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    if bk_biz_id == 0:
        return

    _add_table_ids(
        container=table_ids, values=CustomTSTable.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True)
    )
    _add_data_ids(
        container=data_ids,
        values=CustomTSTable.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True),
    )
    _add_table_ids(
        container=table_ids,
        values=CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True),
    )
    _add_data_ids(
        container=data_ids,
        values=CustomEventGroup.objects.filter(bk_biz_id=bk_biz_id).values_list("bk_data_id", flat=True),
    )


def _collect_normal_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    virtual_plugin_types = [
        PluginType.K8S,
        PluginType.PROCESS,
        PluginType.LOG,
        PluginType.SNMP_TRAP,
    ]
    plugins = CollectorPluginMeta.objects.filter(bk_biz_id=bk_biz_id).exclude(plugin_type__in=virtual_plugin_types)
    plugin_data_name_map = {
        f"{plugin.plugin_type}_{plugin.plugin_id}".lower(): plugin
        for plugin in plugins.only("plugin_type", "plugin_id", "bk_biz_id", "bk_tenant_id")
    }
    if not plugin_data_name_map:
        return

    ds_records = list(
        DataSource.objects.filter(data_name__in=list(plugin_data_name_map.keys())).values_list(
            "data_name", "bk_data_id"
        )
    )
    for data_name, bk_data_id in ds_records:
        plugin = plugin_data_name_map.get(data_name)
        if plugin is None:
            continue
        _add_data_ids(data_ids, [bk_data_id])
        table_id = PluginVersionHistory.get_result_table_id(plugin, "__default__").lower()
        _add_table_ids(table_ids, [table_id])


def _collect_event_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    event_group_qs = CustomEventGroup.objects.filter(
        bk_biz_id=bk_biz_id,
        type=EVENT_TYPE.KEYWORDS,
        name__in=[
            f"{PluginType.LOG}_{plugin_id}"
            for plugin_id in CollectorPluginMeta.objects.filter(
                bk_biz_id=bk_biz_id, plugin_type__in=[PluginType.LOG, PluginType.SNMP_TRAP]
            ).values_list("plugin_id", flat=True)
        ]
        + [
            f"{PluginType.SNMP_TRAP}_{plugin_id}"
            for plugin_id in CollectorPluginMeta.objects.filter(
                bk_biz_id=bk_biz_id, plugin_type__in=[PluginType.LOG, PluginType.SNMP_TRAP]
            ).values_list("plugin_id", flat=True)
        ],
    )
    _add_table_ids(table_ids, event_group_qs.values_list("table_id", flat=True))
    _add_data_ids(data_ids, event_group_qs.values_list("bk_data_id", flat=True))


def _collect_k8s_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    cluster_values = BCSClusterInfo.objects.filter(bk_biz_id=bk_biz_id).values_list(
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
    )
    k8s_data_ids: set[int] = set()
    for k8s_metric_data_id, custom_metric_data_id, k8s_event_data_id, custom_event_data_id in cluster_values:
        _add_data_ids(k8s_data_ids, [k8s_metric_data_id, custom_metric_data_id])
        if k8s_event_data_id not in INVALID_DATA_ID_VALUES:
            k8s_data_ids.add(k8s_event_data_id)
        if custom_event_data_id not in INVALID_DATA_ID_VALUES:
            k8s_data_ids.add(custom_event_data_id)

    _add_data_ids(data_ids, k8s_data_ids)
    _add_dsrt_table_ids(table_ids, k8s_data_ids)


def _collect_process_plugin_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    process_data_names = [
        f"{bk_biz_id}_custom_time_series_process_perf",
        f"{bk_biz_id}_custom_time_series_process_port",
    ]
    process_data_ids = set(
        DataSource.objects.filter(data_name__in=process_data_names).values_list("bk_data_id", flat=True).distinct()
    )
    _add_data_ids(data_ids, process_data_ids)
    _add_dsrt_table_ids(table_ids, process_data_ids)


def _collect_bk_flat_batch_log_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    biz_table_ids = set(ResultTable.objects.filter(bk_biz_id=bk_biz_id).values_list("table_id", flat=True))
    if not biz_table_ids:
        return

    flat_batch_data_ids = DataSource.objects.filter(etl_config="bk_flat_batch").values_list("bk_data_id", flat=True)
    apm_log_tables = set(filter_apm_log_table_ids(DataSource, DataSourceResultTable)["apm"])
    dsrt_queryset = DataSourceResultTable.objects.filter(table_id__in=biz_table_ids, bk_data_id__in=flat_batch_data_ids)
    dsrt_queryset = dsrt_queryset.exclude(table_id__in=apm_log_tables)
    _add_table_ids(table_ids, dsrt_queryset.values_list("table_id", flat=True).distinct())
    _add_data_ids(data_ids, dsrt_queryset.values_list("bk_data_id", flat=True).distinct())


def _collect_uptimecheck_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    protocols = (
        UptimeCheckTask.objects.filter(bk_biz_id=bk_biz_id, indepentent_dataid=True)
        .values_list("protocol", flat=True)
        .distinct()
    )
    data_names = [f"uptimecheck_{protocol.lower()}_{bk_biz_id}" for protocol in protocols]
    if not data_names:
        return

    uptimecheck_data_ids = set(DataSource.objects.filter(data_name__in=data_names).values_list("bk_data_id", flat=True))
    _add_data_ids(data_ids, uptimecheck_data_ids)
    _add_dsrt_table_ids(table_ids, uptimecheck_data_ids)


def _collect_apm_data(bk_biz_id: int, table_ids: set[str], data_ids: set[int]) -> None:
    for model in (MetricDataSource, TraceDataSource, LogDataSource, ProfileDataSource):
        queryset = model.objects.filter(bk_biz_id=bk_biz_id)
        _add_data_ids(data_ids, queryset.values_list("bk_data_id", flat=True))
        _add_table_ids(table_ids, queryset.values_list("result_table_id", flat=True))


def find_biz_table_and_data_id(bk_biz_id: int) -> tuple[list[str], list[int]]:
    """查询业务下关联的结果表和数据ID

    Args:
        bk_biz_id: 业务ID

    Returns:
        tuple[list[str], list[int]]: 结果表列表和数据ID列表
    """
    table_ids: set[str] = set()
    data_ids: set[int] = set()

    _collect_custom_report_data(bk_biz_id, table_ids, data_ids)
    _collect_normal_plugin_data(bk_biz_id, table_ids, data_ids)
    _collect_event_plugin_data(bk_biz_id, table_ids, data_ids)
    if bk_biz_id != 0:
        _collect_k8s_plugin_data(bk_biz_id, table_ids, data_ids)
        _collect_process_plugin_data(bk_biz_id, table_ids, data_ids)
        _collect_bk_flat_batch_log_data(bk_biz_id, table_ids, data_ids)
        _collect_uptimecheck_data(bk_biz_id, table_ids, data_ids)
        _collect_apm_data(bk_biz_id, table_ids, data_ids)

    return sorted(table_ids), sorted(data_ids)
