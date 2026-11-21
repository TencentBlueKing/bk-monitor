"""标准事件组散件：保持原 ES，不改历史存储、不清理 GSE 路由。"""

from metadata import models
from metadata.service.upgrade_v4.common import changed, require_single_tenant, run_batch, set_option
from metadata.task.datalink import apply_event_group_datalink


def migrate_event(data_id, *, bk_tenant_id="system"):
    require_single_tenant()
    source = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)
    if not source.is_enable:
        return {"data_id": data_id, "skipped": "数据源已停用", "table_ids": [], "spaces": []}
    if source.etl_config != "bk_standard_v2_event":
        raise ValueError(f"DataID {data_id} 不是标准事件；系统事件应使用独立入口")
    groups = list(
        models.EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id, is_delete=False, is_enable=True)
    )
    tables = []
    for group in groups:
        table = models.ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=group.table_id)
        if not table.is_enable or table.is_deleted:
            continue
        set_option(table.table_id, "enable_v4_event_group_data_link", True, bk_tenant_id=bk_tenant_id)
        apply_event_group_datalink(bk_tenant_id, table.table_id, finalize=False, refresh_route=False)
        tables.append(table.table_id)
    return changed(source, tables)


def migrate_custom_events(data_ids=None, *, bk_biz_ids=None, bk_tenant_id="system", **route_options):
    groups = models.EventGroup.objects.filter(bk_tenant_id=bk_tenant_id, is_delete=False, is_enable=True)
    if bk_biz_ids is not None:
        groups = groups.filter(bk_biz_id__in=bk_biz_ids)
    if data_ids is not None:
        groups = groups.filter(bk_data_id__in=data_ids)
    ids = list(groups.order_by("bk_data_id").values_list("bk_data_id", flat=True).distinct())
    return run_batch(
        ids,
        lambda data_id: migrate_event(data_id, bk_tenant_id=bk_tenant_id),
        bk_tenant_id=bk_tenant_id,
        **route_options,
    )
