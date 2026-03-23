from core.drf_resource import resource
from metadata.models import (
    DataSource,
    DataSourceResultTable,
    EventGroup,
    ResultTable,
    ResultTableOption,
    TimeSeriesGroup,
)
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, BKBASE_NAMESPACE_BK_MONITOR
from metadata.models.space.constants import EtlConfigs
from metadata.task.tasks import check_bkcc_space_builtin_datalink
from monitor_web.commons.data_access import PluginDataAccessor, UptimecheckDataAccessor
from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.models.uptime_check import UptimeCheckTask
from monitor_web.plugin.manager.process import ProcessPluginManager


def rebuild_system_data(bk_tenant_id: str, bk_biz_id: int):
    """重建内置系统数据

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    # 检查并重新接入系统数据
    check_bkcc_space_builtin_datalink([(bk_tenant_id, bk_biz_id)])


def rebuild_collect_plugins(bk_tenant_id: str, bk_biz_id: int, collect_config_ids: list[int]):
    """重建采集插件

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        collect_config_ids (list[int]): 采集配置ID列表
    """

    collect_configs = CollectConfigMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id__in=collect_config_ids
    )
    plugin_ids = list(set(collect_configs.values_list("plugin_id", flat=True)))

    # 获取插件，顺便检查插件是否存在
    plugins = CollectorPluginMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids
    )
    exists_plugin_ids = plugins.values_list("id", flat=True)
    if len(exists_plugin_ids) != len(plugin_ids):
        missing_plugin_ids = set(plugin_ids) - set(exists_plugin_ids)
        raise ValueError(f"插件不存在: {missing_plugin_ids}")

    # 获取插件对应的数据源/结果表/自定义上报
    for plugin in plugins:
        if plugin.plugin_type in [CollectorPluginMeta.PluginType.SNMP_TRAP, CollectorPluginMeta.PluginType.LOG]:
            event_group = EventGroup.objects.get(event_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}")
            rebuild_event_group(bk_tenant_id, bk_biz_id, [event_group.event_group_id])
        elif plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
            group_ids = list(
                TimeSeriesGroup.objects.filter(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    time_series_group_name__in=["process_perf", "process_port"],
                ).values_list("time_series_group_id", flat=True)
            )
            if group_ids:
                rebuild_time_series_group(bk_tenant_id, bk_biz_id, group_ids)
            else:
                ProcessPluginManager(plugin, operator="system").touch(bk_biz_id)
        else:
            accessor = PluginDataAccessor(plugin.current_version, operator="system")
            data_source = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=accessor.get_data_id())

            time_series_group = TimeSeriesGroup.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=data_source.bk_data_id
            ).first()
            if time_series_group:
                rebuild_time_series_group(bk_tenant_id, bk_biz_id, [time_series_group.time_series_group_id])
            else:
                accessor.access()

    # 启用采集配置
    for collect_config in collect_configs:
        resource.collecting.toggle_collect_config_status(
            bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, id=collect_config.pk, action="enable"
        )


def rebuild_uptime_check(bk_tenant_id: str, bk_biz_id: int, task_ids: list[int] | None = None):
    """重建拨测数据
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    tasks = UptimeCheckTask.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if task_ids:
        tasks = tasks.filter(task_id__in=task_ids)
    if not tasks.exists():
        return

    # 启用独立数据源模式
    tasks.update(indepentent_dataid=True)

    # 启用或重建自定义上
    accessor = UptimecheckDataAccessor(tasks[0])
    accessor.access()

    # 部署任务
    for task in tasks:
        task.deploy()


def rebuild_time_series_group(bk_tenant_id: str, bk_biz_id: int, time_series_group_ids: list[int] | None = None):
    """重建时序分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        time_series_group_ids (list[int]): 时序分组ID列表
    """
    time_series_groups = TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if time_series_group_ids:
        time_series_groups = time_series_groups.filter(time_series_group_id__in=time_series_group_ids)

    data_ids = list(time_series_groups.values_list("bk_data_id", flat=True))
    table_ids = list(time_series_groups.values_list("table_id", flat=True))

    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    for data_source in data_sources:
        if not data_source.register_to_gse():
            raise ValueError(f"数据源{data_source.bk_data_id}注册到gse失败")
        data_source.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=BKBASE_NAMESPACE_BK_MONITOR)

    TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, time_series_group_id__in=time_series_group_ids).update(
        is_enable=True
    )
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    for result_table in result_tables:
        result_table.modify(operator="system", is_enable=True)


def rebuild_event_group(bk_tenant_id: str, bk_biz_id: int, event_group_ids: list[int] | None = None):
    """重建事件分组

    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
        event_group_ids (list[int]): 事件分组ID列表
    """
    event_groups = EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, is_delete=False)
    if event_group_ids:
        event_groups = event_groups.filter(event_group_id__in=event_group_ids)

    data_ids = list(event_groups.values_list("bk_data_id", flat=True))
    table_ids = list(event_groups.values_list("table_id", flat=True))

    # 数据源路由重建
    data_sources = DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids)
    for data_source in data_sources:
        if not data_source.register_to_gse():
            raise ValueError(f"数据源{data_source.bk_data_id}注册到gse失败")
        data_source.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=BKBASE_NAMESPACE_BK_LOG)

    EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, event_group_id__in=event_group_ids).update(is_enable=True)
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids)
    for result_table in result_tables:
        # 默认启用V4事件组数据链路
        v4_option = ResultTableOption.objects.filter(
            table_id=result_table.table_id,
            bk_tenant_id=bk_tenant_id,
            name=ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
        ).first()
        if not v4_option:
            ResultTableOption.create_option(
                table_id=result_table.table_id,
                bk_tenant_id=bk_tenant_id,
                name=ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
                value="true",
                creator="system",
            )
        result_table.modify(operator="system", is_enable=True)


def rebuild_bklog_data_source_route(bk_tenant_id: str, bk_biz_id: int):
    """重建bklog数据源路由
    Args:
        bk_tenant_id (str): 租户ID
        bk_biz_id (int): 业务ID
    """
    result_tables = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    related_data_ids = list(
        DataSourceResultTable.objects.filter(table_id__in=result_tables.values_list("table_id", flat=True))
        .values_list("bk_data_id", flat=True)
        .distinct()
    )
    data_sources = DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id, etl_config=EtlConfigs.BK_FLAT_BATCH.value, bk_data_id__in=related_data_ids
    )

    for data_source in data_sources:
        data_source.register_to_gse()
