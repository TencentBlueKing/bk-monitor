"""聚类 Pattern 结果表注册及存储历史，复用 metadata 的实体表和资源配置。"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from metadata.config import DATABASE_CONNECTION_NAME

PATTERN_FIELDS = {
    "index_set_id": "string",
    "distance_threshold": "string",
    "signature": "string",
    "pattern": "string",
    "pattern_hash": "string",
    "task_id": "string",
    "generation": "long",
    "publish_revision": "long",
}
PATTERN_KEYS = ["index_set_id", "distance_threshold", "signature"]


def prepare_pattern_store(sink):
    """每个租户、索引集登记一张固定 Pattern 表，跟随源日志的 ES 存储。

    资源单独归组，避免被原日志链路的单 RT/Binding 认领和清理逻辑误处理。
    不创建 DataID、Databus 或源数据关联，只有聚类算子向该表写入。
    """
    from metadata import models

    tenant = sink.bk_tenant_id
    name = f"bklog_pattern_{sink.binding['index_id']}"
    table_id = f"bklog.{name}"
    source = models.ESStorage.objects.get(bk_tenant_id=tenant, table_id=sink.table_id)
    cluster = models.ClusterInfo.objects.get(
        bk_tenant_id=tenant, cluster_id=source.storage_cluster_id, cluster_type=models.ClusterInfo.TYPE_ES
    )
    with transaction.atomic(using=DATABASE_CONNECTION_NAME):
        table, created = models.ResultTable.objects.get_or_create(
            bk_tenant_id=tenant,
            table_id=table_id,
            defaults={
                "table_name_zh": "日志聚类 Pattern",
                "is_custom_table": True,
                "default_storage": models.ClusterInfo.TYPE_ES,
                "bk_biz_id": sink.bk_biz_id,
                "creator": "system",
                "is_enable": True,
            },
        )
        models.ResultTable.objects.select_for_update().get(pk=table.pk)
        if created:
            models.ResultTableField.bulk_create_fields(
                table_id,
                [
                    {
                        "field_name": field,
                        "field_type": "int" if kind == "long" else kind,
                        "tag": "dimension",
                        "is_config_by_user": True,
                        "operator": "system",
                    }
                    for field, kind in PATTERN_FIELDS.items()
                ],
                bk_tenant_id=tenant,
            )
        rt, _ = models.ResultTableConfig.objects.get_or_create(
            bk_tenant_id=tenant,
            namespace=sink.namespace,
            name=name,
            defaults={"data_link_name": name, "bk_biz_id": sink.bk_biz_id, "table_id": table_id, "data_type": "log"},
        )
        rt_config = rt.compose_config(
            fields=[
                {
                    "name": field,
                    "type": kind,
                    "alias": field,
                    "description": field,
                    "is_dimension": field in PATTERN_KEYS,
                    "index": index,
                }
                for index, (field, kind) in enumerate(PATTERN_FIELDS.items())
            ]
        )
        binding, _ = models.ESStorageBindingConfig.objects.update_or_create(
            bk_tenant_id=tenant,
            namespace=sink.namespace,
            name=f"{name}_{cluster.cluster_id}",
            defaults={
                "data_link_name": name,
                "bk_biz_id": sink.bk_biz_id,
                "table_id": table_id,
                "bkbase_result_table_name": rt.name,
                "es_cluster_name": cluster.cluster_name,
            },
        )
        # 在不同集群使用同一个固定物理名称，历史路由可以复用原来的查询目标。
        # 与 BKBase ResultTable.result_table_id() 的业务前缀保持一致。
        physical_name = f"{rt_config['spec']['bizId']}_{rt.name}"
        storage = models.ESStorage.objects.filter(bk_tenant_id=tenant, table_id=table_id).first()
        if storage is None:
            storage = models.ESStorage.create_table(
                bk_tenant_id=tenant,
                table_id=table_id,
                cluster_id=cluster.cluster_id,
                source_type="es",
                index_set=physical_name,
                need_create_index=False,
                enable_create_index=False,
                is_sync_db=False,
            )
        else:
            # 与源日志使用相同的切存储时间边界。关闭、重开和重试不产生重复分段。
            source_record = (
                models.StorageClusterRecord.objects.filter(
                    bk_tenant_id=tenant,
                    table_id=sink.table_id,
                    cluster_id=cluster.cluster_id,
                    is_current=True,
                    is_deleted=False,
                )
                .order_by("-enable_time", "-id")
                .first()
            )
            models.StorageClusterRecord.switch_current_cluster(
                table_id=table_id,
                bk_tenant_id=tenant,
                target_cluster_id=cluster.cluster_id,
                target_storage_type=models.ClusterInfo.TYPE_ES,
                switch_time=source_record.enable_time
                if source_record and source_record.enable_time
                else timezone.now(),
                creator="system",
            )
            storage.storage_cluster_id = cluster.cluster_id
            storage.save(update_fields=["storage_cluster_id"])
        binding_ref = binding.reference
        if settings.ENABLE_MULTI_TENANT_MODE:
            binding_ref["tenant"] = tenant
        sink.pattern_store = {
            "result_table": {**binding_ref, "kind": rt.kind, "name": rt.name},
            "es_binding": binding_ref,
        }
        sink.save(update_fields=["pattern_store"])

    binding_config = binding.compose_config(
        storage_cluster_name=cluster.cluster_name,
        write_alias_format=None,
        unique_field_list=PATTERN_KEYS,
        rt_name=rt.name,
    )
    binding_config["metadata"]["annotations"] = {"physical_table_name": physical_name}
    binding_config["spec"].update(doc_value_fields=PATTERN_KEYS)
    return [rt_config, binding_config]


def publish_pattern_routes(datalink):
    """完整链路或 Sink 下发成功后，刷新已存在的聚类路由；失败由原操作重试补发。"""
    from metadata import models
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    sink = models.LogClusteringSinkConfig.objects.filter(
        bk_tenant_id=datalink.bk_tenant_id,
        namespace=datalink.namespace,
        data_link_name=datalink.data_link_name,
    ).first()
    if sink is None or not sink.pattern_store:
        return
    ref = sink.pattern_store["result_table"]
    rt = models.ResultTableConfig.objects.get(
        bk_tenant_id=datalink.bk_tenant_id, namespace=ref["namespace"], name=ref["name"]
    )
    route_ids = []
    for table_id in (rt.table_id, sink.table_id):
        storage = models.ESStorage.objects.get(bk_tenant_id=datalink.bk_tenant_id, table_id=table_id)
        routes = models.ESStorage.objects.filter(
            bk_tenant_id=datalink.bk_tenant_id,
            origin_table_id=table_id,
        )
        route_ids.extend(routes.values_list("table_id", flat=True))
        routes.update(storage_cluster_id=storage.storage_cluster_id)
    if route_ids:
        SpaceTableIDRedis().push_table_id_detail(
            table_id_list=route_ids, bk_tenant_id=datalink.bk_tenant_id, is_publish=True, raise_on_log_write_error=True
        )
