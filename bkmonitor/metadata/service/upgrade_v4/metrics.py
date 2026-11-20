"""标准时序和自定义格式指标接入；保留原 DataID、Kafka 和启停状态。"""

from metadata import models
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.models.vm.utils import create_bkbase_data_link
from metadata.service.upgrade_v4.common import changed, register_source, require_single_tenant, run_batch, set_option


def migrate_metric(data_id, *, vm_cluster_name, bk_tenant_id="system", bcs_cluster_id=None):
    """单 DataID 散件；不刷新路由、不删除 Transfer，已有组件按原身份重新 apply。"""
    require_single_tenant()
    source = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)
    if not source.is_enable:
        return {"data_id": data_id, "skipped": "数据源已停用", "table_ids": [], "spaces": []}
    if source.etl_config not in {"bk_standard_v2_time_series", "bk_exporter", "bk_standard"}:
        raise ValueError(f"DataID {data_id} 不是标准时序或采集插件，请使用对应场景入口")
    table_ids = list(
        models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id).values_list(
            "table_id", flat=True
        )
    )
    tables = list(
        models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id__in=table_ids, is_enable=True, is_deleted=False
        )
    )
    if not tables:
        return {"data_id": data_id, "skipped": "没有启用的结果表", "table_ids": [], "spaces": []}
    # 同一数据源多表需先转换，不能让多个 Databus 以同消费组分别写不完整的数据。
    if len(tables) != 1:
        raise ValueError(f"DataID {data_id} 有多个启用结果表，请先使用插件多表准备入口")
    table = tables[0]
    if models.ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table.table_id, name="graph_relation_v4_data_link"
    ).exists():
        raise ValueError("图谱指标使用专用链路，不属于普通时序升级范围")
    cluster = models.ClusterInfo.objects.get(
        bk_tenant_id=bk_tenant_id, cluster_name=vm_cluster_name, cluster_type=models.ClusterInfo.TYPE_VM
    )
    bk_biz_id = table.get_target_bk_biz_id()
    if not bk_biz_id:
        from bkmonitor.utils.tenant import get_tenant_default_biz_id

        bk_biz_id = get_tenant_default_biz_id(bk_tenant_id)
    register_source(source, bk_biz_id)
    create_bkbase_data_link(
        bk_biz_id=bk_biz_id,
        data_source=source,
        monitor_table_id=table.table_id,
        storage_cluster_name=cluster.cluster_name,
        consumer_group=compose_transfer_consumer_group(source),
        bcs_cluster_id=bcs_cluster_id,
    )
    return changed(source, [table.table_id])


def migrate_custom_metrics(data_ids=None, *, vm_cluster_name, bk_biz_ids=None, bk_tenant_id="system", **route_options):
    """None=本场景全部启用组；[]=不执行。可通过业务/DataID 局部执行。"""
    groups = models.TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False, is_enable=True)
    if bk_biz_ids is not None:
        groups = groups.filter(bk_biz_id__in=bk_biz_ids)
    if data_ids is not None:
        groups = groups.filter(bk_data_id__in=data_ids)
    ids = list(groups.order_by("bk_data_id").values_list("bk_data_id", flat=True).distinct())
    return run_batch(
        ids,
        lambda data_id: migrate_metric(data_id, vm_cluster_name=vm_cluster_name, bk_tenant_id=bk_tenant_id),
        bk_tenant_id=bk_tenant_id,
        **route_options,
    )


def migrate_builtin_metrics(data_ids, *, vm_cluster_name, bk_tenant_id="system", **route_options):
    """平台内置指标需显式传入 DataID 清单，不硬编码环境 ID，不重启停用对象。"""
    return run_batch(
        list(dict.fromkeys(data_ids)),
        lambda data_id: migrate_metric(data_id, vm_cluster_name=vm_cluster_name, bk_tenant_id=bk_tenant_id),
        bk_tenant_id=bk_tenant_id,
        **route_options,
    )


def migrate_custom_formats(table_ids=None, *, bk_tenant_id="system", **route_options):
    """使用已配置的 custom_format_v4_data_link；不推测或改写清洗规则。"""
    from metadata.task.datalink import apply_custom_format_datalink

    sources = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, etl_config="bk_custom_format", is_enable=True)
    relations = models.DataSourceResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_data_id__in=sources.values("bk_data_id")
    )
    tables = models.ResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id__in=relations.values("table_id"), is_enable=True, is_deleted=False
    )
    if table_ids is not None:
        tables = tables.filter(table_id__in=table_ids)

    def migrate(table_id):
        # 先读取配置，避免缺少清洗配置时只留下已开启的标志。
        models.ResultTableOption.objects.get(
            bk_tenant_id=bk_tenant_id, table_id=table_id, name="custom_format_v4_data_link"
        )
        set_option(table_id, "enable_custom_format_v4_data_link", True, bk_tenant_id=bk_tenant_id)
        apply_custom_format_datalink(bk_tenant_id, table_id, finalize=False)
        source = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id).get_related_datasource()
        return changed(source, [table_id])

    return run_batch(
        list(tables.values_list("table_id", flat=True)), migrate, bk_tenant_id=bk_tenant_id, **route_options
    )
