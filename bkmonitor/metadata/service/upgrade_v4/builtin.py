"""单租户内置场景：保留共享 DataID 和现有 Kafka，独立于租户初始化。"""

from django.conf import settings

from metadata import models
from metadata.models.data_link.constants import BASEREPORT_SOURCE_SYSTEM, BASEREPORT_USAGES
from metadata.models.data_link.utils import compose_transfer_consumer_group
from metadata.service.upgrade_v4.common import changed, run_batch


def _source(data_id):
    return models.DataSource.objects.get(bk_tenant_id="system", bk_data_id=data_id)


def _link(source, name, strategy, table_ids, namespace="bkmonitor"):
    link, _ = models.DataLink.objects.update_or_create(
        bk_tenant_id="system",
        data_link_name=name,
        defaults={
            "namespace": namespace,
            "data_link_strategy": strategy,
            "bk_data_id": source.bk_data_id,
            "table_ids": table_ids,
        },
    )
    return link


def _vm_record(source, table_id, vmrt, cluster):
    record = models.AccessVMRecord.objects.filter(bk_tenant_id="system", result_table_id=table_id).last()
    if record is None:
        record = models.AccessVMRecord(bk_tenant_id="system", result_table_id=table_id)
    record.data_type = models.AccessVMRecord.ACCESS_VM
    record.bk_base_data_id = source.bk_data_id
    record.bk_base_data_name = source.data_name
    record.storage_cluster_id = cluster.cluster_id
    record.vm_cluster_id = cluster.cluster_id
    record.vm_result_table_id = vmrt
    record.save()


def migrate_host_metrics(*, vm_cluster_name, data_bk_biz_id=None, **route_options):
    bk_biz_id = settings.DEFAULT_BKDATA_BIZ_ID if data_bk_biz_id is None else data_bk_biz_id

    def migrate(data_id):
        source = _source(data_id)
        if not source.is_enable:
            return {"skipped": "数据源已停用", "table_ids": [], "spaces": []}
        cluster = models.ClusterInfo.objects.get(
            bk_tenant_id="system", cluster_name=vm_cluster_name, cluster_type=models.ClusterInfo.TYPE_VM
        )
        source.register_to_bkbase(bk_biz_id=bk_biz_id, bkbase_data_name="basereport", update_created_from=False)
        tables = [f"system.{usage}" for usage in BASEREPORT_USAGES]
        link = _link(source, "basereport", models.DataLink.BASEREPORT_TIME_SERIES_V1, tables)
        link.apply_data_link(
            data_source=source,
            storage_cluster_name=cluster.cluster_name,
            bk_biz_id=bk_biz_id,
            source=BASEREPORT_SOURCE_SYSTEM,
            prefix=BASEREPORT_SOURCE_SYSTEM,
            consumer_group=compose_transfer_consumer_group(source),
        )
        # 与单租户原有入口相同的固定 VMRT；不是多租户 base_<biz> 表。
        for usage in BASEREPORT_USAGES:
            _vm_record(source, f"system.{usage}", f"{bk_biz_id}_{BASEREPORT_SOURCE_SYSTEM}_{usage}", cluster)
        return changed(source, tables)

    return run_batch([settings.SNAPSHOT_DATAID], migrate, **route_options)


def migrate_system_processes(data_ids=None, *, vm_cluster_name, data_bk_biz_id=None, **route_options):
    bk_biz_id = settings.DEFAULT_BKDATA_BIZ_ID if data_bk_biz_id is None else data_bk_biz_id
    specs = {
        settings.PROCESS_PERF_DATAID: ("system.proc", models.DataLink.SYSTEM_PROC_PERF),
        settings.PROCESS_PORT_DATAID: ("system.proc_port", models.DataLink.SYSTEM_PROC_PORT),
    }

    def migrate(data_id):
        table_id, strategy = specs[data_id]
        source = _source(data_id)
        if not source.is_enable:
            return {"skipped": "数据源已停用", "table_ids": [], "spaces": []}
        cluster = models.ClusterInfo.objects.get(
            bk_tenant_id="system", cluster_name=vm_cluster_name, cluster_type=models.ClusterInfo.TYPE_VM
        )
        source.register_to_bkbase(bk_biz_id=bk_biz_id, bkbase_data_name=strategy, update_created_from=False)
        link = _link(source, strategy, strategy, [table_id])
        link.apply_data_link(
            data_source=source,
            table_id=table_id,
            storage_cluster_name=cluster.cluster_name,
            bk_biz_id=bk_biz_id,
            prefix="",
            consumer_group=compose_transfer_consumer_group(source),
        )
        _vm_record(source, table_id, f"{bk_biz_id}_{strategy}", cluster)
        return changed(source, [table_id])

    return run_batch(list(specs) if data_ids is None else list(dict.fromkeys(data_ids)), migrate, **route_options)


def migrate_system_events(*, data_bk_biz_id=None, **route_options):
    from metadata.models.constants import GSE_SYSTEM_EVENT_TABLE_ID

    bk_biz_id = settings.DEFAULT_BKDATA_BIZ_ID if data_bk_biz_id is None else data_bk_biz_id

    def migrate(data_id):
        source = _source(data_id)
        if not source.is_enable:
            return {"skipped": "数据源已停用", "table_ids": [], "spaces": []}
        table_id = GSE_SYSTEM_EVENT_TABLE_ID
        storage = models.ESStorage.objects.get(bk_tenant_id="system", table_id=table_id)
        name = f"base_{bk_biz_id}_agent_event"
        source.register_to_bkbase(
            bk_biz_id=bk_biz_id, namespace="bklog", bkbase_data_name=name, update_created_from=False
        )
        link = _link(source, name, models.DataLink.BASE_EVENT_V1, [table_id], "bklog")
        link.apply_data_link(
            data_source=source,
            table_id=table_id,
            bk_biz_id=bk_biz_id,
            storage_type=models.ClusterInfo.TYPE_ES,
            storage_cluster_name=storage.storage_cluster.cluster_name,
            consumer_group=compose_transfer_consumer_group(source),
        )
        return changed(source, [table_id])

    return run_batch([settings.GSE_BASE_ALARM_DATAID], migrate, **route_options)
