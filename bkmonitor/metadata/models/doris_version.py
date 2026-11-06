"""普通 Doris 表版本：修改入口分配，声明入口只复用。"""

import datetime
import re

from django.db import transaction
from django.utils import timezone

from metadata import config


def advance_table_version(storage, operator, *, target_default_storage=None, old_cluster_id=None):
    """调用者持有 ResultTable 行锁；保存物理表、版本和配置时间段后才允许 apply。"""
    from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
    from metadata.models import ResultTable, StorageClusterRecord

    table = ResultTable.objects.get(table_id=storage.table_id, bk_tenant_id=storage.bk_tenant_id)
    if old_cluster_id is None:
        old_cluster_id = storage.storage_cluster_id
    old_physical = dict(storage.physical_tables)
    old_rt = storage.bkbase_table_id or ""
    # 未纳管存量表只在首次换表前读取实际名称，不等待新表创建。
    from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig

    legacy_binding = None
    if not storage.datalink_table_name:
        legacy_binding = (
            DorisStorageBindingConfig.objects.filter(bk_tenant_id=storage.bk_tenant_id, table_id=storage.table_id)
            .order_by("-last_modify_time")
            .first()
        )
    if not old_physical and (old_rt or legacy_binding):
        old_physical = {"main": storage.get_physical_table_name()["physical_table_name"]}
    if not old_rt and legacy_binding:
        old_rt = f"{legacy_binding.datalink_biz_ids.data_biz_id}_{legacy_binding.bkbase_result_table_name}"
    biz_id = get_tenant_datalink_biz_id(bk_tenant_id=storage.bk_tenant_id, bk_biz_id=table.bk_biz_id).data_biz_id
    database = old_physical["main"].split(".", 1)[0] if old_physical else f"mapleleaf_{biz_id}"
    records = StorageClusterRecord.objects.select_for_update().filter(
        table_id=storage.table_id,
        bk_tenant_id=storage.bk_tenant_id,
        cluster_id=old_cluster_id,
        is_deleted=False,
        disable_time__isnull=True,
    )
    now = timezone.now()
    if old_physical:
        record = records.order_by("-id").first()
        if record is None:
            record = StorageClusterRecord.objects.create(
                table_id=storage.table_id,
                bk_tenant_id=storage.bk_tenant_id,
                cluster_id=old_cluster_id,
                creator=operator,
                enable_time=timezone.make_aware(datetime.datetime(1970, 1, 1)),
            )
        if not record.physical_tables:
            record.physical_tables = old_physical
        if not record.bkbase_table_id:
            record.bkbase_table_id = old_rt
        record.save(update_fields=["physical_tables", "bkbase_table_id"])
        records.update(is_current=False, disable_time=now)
    current_name = storage.datalink_table_name
    version = int(current_name.rsplit("_v", 1)[1]) + 1 if current_name else 1
    table_name = f"bkm_doris_{storage.pk}_v{version}"
    storage.bkbase_table_id = f"{biz_id}_{table_name}"
    storage.physical_tables = {"main": f"{database}.{table_name}"}
    storage.save(update_fields=["bkbase_table_id", "physical_tables"])
    # 首次创建可直接补齐 create_table 已建立的空分段。
    current = records.first() if not old_physical and old_cluster_id == storage.storage_cluster_id else None
    if current is None:
        current = StorageClusterRecord(
            table_id=storage.table_id,
            bk_tenant_id=storage.bk_tenant_id,
            cluster_id=storage.storage_cluster_id,
            creator=operator,
            enable_time=now,
        )
    current.is_current = (target_default_storage or table.default_storage) == "doris"
    current.bkbase_table_id = storage.bkbase_table_id
    current.physical_tables = dict(storage.physical_tables)
    current.save()
    transaction.on_commit(
        lambda: publish_doris_route(storage.bk_tenant_id, storage.table_id),
        using=config.DATABASE_CONNECTION_NAME,
        robust=True,
    )


def publish_doris_route(bk_tenant_id, table_id):
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    SpaceTableIDRedis().push_table_id_detail(bk_tenant_id=bk_tenant_id, table_id_list=[table_id], is_publish=True)


def get_datalink_table_name(storage_id, physical_tables):
    name = (physical_tables.get("main") or "").partition(".")[2]
    return name if re.fullmatch(rf"bkm_doris_{storage_id}_v[1-9][0-9]*", name) else None
