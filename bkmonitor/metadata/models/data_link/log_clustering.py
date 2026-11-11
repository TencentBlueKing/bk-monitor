"""聚类 Pattern 结果表注册及存储历史，复用 metadata 的实体表和资源配置。"""

import json

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
    "dtEventTimeStamp": "long",
}
PATTERN_KEYS = ["index_set_id", "distance_threshold", "signature"]


RESULT_FIELDS = {
    "__log_signature": "string",
    "__log_cluster_publish_revision": "long",
}


def register_result_fields(table_id, tenant):
    """两种写入目标使用相同的聚类字段和查询别名，不覆盖业务字段选项。"""
    from metadata import models

    for field, kind in RESULT_FIELDS.items():
        models.ResultTableField.objects.update_or_create(
            bk_tenant_id=tenant,
            table_id=table_id,
            field_name=field,
            defaults={
                "field_type": "int" if kind == "long" else kind,
                "tag": "dimension",
                "is_config_by_user": True,
                "creator": "system",
                "last_modify_user": "system",
            },
        )
        models.ResultTableFieldOption.objects.update_or_create(
            table_id=table_id,
            field_name=field,
            name="es_type",
            bk_tenant_id=tenant,
            defaults={"value": "long" if kind == "long" else "keyword", "value_type": "string", "creator": "system"},
        )
    register_signature_alias(table_id, tenant)


def register_signature_alias(table_id, tenant):
    from metadata import models

    models.ESFieldQueryAliasOption.objects.update_or_create(
        table_id=table_id,
        bk_tenant_id=tenant,
        query_alias="signature",
        defaults={"field_path": "__log_signature", "path_type": "keyword", "is_deleted": False},
    )


def prepare_clustering_stores(sink):
    """准备 Pattern，以及首次开启时选择的独立结果表。"""
    from metadata.models.data_link.utils import generate_result_table_field_list

    configs, refs = _prepare_store(sink, "pattern", PATTERN_FIELDS)
    sink.pattern_store = refs
    if sink.result.get("mode") == "append":
        from metadata import models
        from metadata.models.result_table import LogV4DataLinkOption

        option = models.ResultTableOption.objects.get(
            bk_tenant_id=sink.bk_tenant_id,
            table_id=sink.table_id,
            name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        )
        es_config = LogV4DataLinkOption(**json.loads(option.value)).es_storage_config
        fields = {
            field["field_name"]: field["field_type"]
            for field in generate_result_table_field_list(
                sink.table_id, sink.bk_tenant_id, unique_field_list=es_config.unique_field_list
            )
        }
        fields.update(RESULT_FIELDS)
        result_configs, result_refs = _prepare_store(sink, "clustered", fields, es_config=es_config)
        sink.result = {"mode": "append", **result_refs}
        configs.extend(result_configs)
    else:
        from metadata import models

        register_result_fields(sink.table_id, sink.bk_tenant_id)
        source = models.ESStorage.objects.get(table_id=sink.table_id, bk_tenant_id=sink.bk_tenant_id)
        if source.update_index_and_aliases(ahead_time=0, strict=True) is False:
            raise RuntimeError(f"{sink.table_id} ES 索引或写别名未准备完成")
    sink.save(update_fields=["pattern_store", "result"])
    return configs


def _prepare_store(sink, suffix, fields, *, es_config=None):
    """每个租户、索引集登记聚类结果或 Pattern 表，跟随源日志的 ES 存储。

    资源单独归组，避免被原日志链路的单 RT/Binding 认领和清理逻辑误处理。
    不创建 DataID、Databus 或源数据关联，只有聚类算子向该表写入。
    """
    from metadata import models

    tenant = sink.bk_tenant_id
    name = f"bklog_{sink.binding['index_id']}_{suffix}"
    table_id = (
        f"bklog.{name}"
        if suffix == "pattern"
        else f"{sink.datalink_biz_ids.data_biz_id}_bklog.{sink.binding['index_id']}_clustered"
    )
    source = models.ESStorage.objects.get(bk_tenant_id=tenant, table_id=sink.table_id)
    cluster = models.ClusterInfo.objects.get(
        bk_tenant_id=tenant, cluster_id=source.storage_cluster_id, cluster_type=models.ClusterInfo.TYPE_ES
    )
    with transaction.atomic(using=DATABASE_CONNECTION_NAME):
        table, _ = models.ResultTable.objects.get_or_create(
            bk_tenant_id=tenant,
            table_id=table_id,
            defaults={
                "table_name_zh": f"日志聚类 {suffix}",
                "is_custom_table": True,
                "default_storage": models.ClusterInfo.TYPE_ES,
                "bk_biz_id": sink.bk_biz_id,
                "creator": "system",
                "is_enable": True,
            },
        )
        models.ResultTable.objects.select_for_update().get(pk=table.pk)
        if suffix == "pattern":
            existing_fields = set(
                models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=tenant).values_list(
                    "field_name", flat=True
                )
            )
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
                    for field, kind in fields.items()
                    if field not in existing_fields
                ],
                bk_tenant_id=tenant,
            )
        if suffix == "pattern":
            mapped = set(
                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, bk_tenant_id=tenant, name="es_type"
                ).values_list("field_name", flat=True)
            )
            missing_options = [
                {
                    "table_id": table_id,
                    "field_name": field,
                    "name": "es_type",
                    "value": "date" if field == "dtEventTimeStamp" else ("long" if kind == "long" else "keyword"),
                    "creator": "system",
                }
                for field, kind in fields.items()
                if field not in mapped
            ]
            if missing_options:
                models.ResultTableFieldOption.bulk_create_options(table_id, missing_options, bk_tenant_id=tenant)
            # V4 用毫秒 long；ES 必须以时间字段索引，兼容 UnifyQuery 时间过滤。
            for option, value in (("es_type", "date"), ("es_format", "epoch_millis")):
                models.ResultTableFieldOption.objects.update_or_create(
                    table_id=table_id,
                    field_name="dtEventTimeStamp",
                    name=option,
                    bk_tenant_id=tenant,
                    defaults={"value": value, "value_type": "string", "creator": "system"},
                )
        if suffix == "clustered":
            # 独立日志表复用原字段及 ES 字段选项，保留分词、时间与对象字段语义。
            source_fields = list(models.ResultTableField.objects.filter(table_id=sink.table_id, bk_tenant_id=tenant))
            models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=tenant).exclude(
                field_name__in=[field.field_name for field in source_fields] + list(RESULT_FIELDS)
            ).delete()
            for source_field in source_fields:
                if source_field.field_name in RESULT_FIELDS:
                    continue
                values = {
                    f.name: getattr(source_field, f.name)
                    for f in source_field._meta.fields
                    if f.name not in ("id", "table_id", "bk_tenant_id", "field_name")
                }
                models.ResultTableField.objects.update_or_create(
                    table_id=table_id, bk_tenant_id=tenant, field_name=source_field.field_name, defaults=values
                )
            models.ResultTableFieldOption.objects.filter(table_id=table_id, bk_tenant_id=tenant).delete()
            for option in models.ResultTableFieldOption.objects.filter(table_id=sink.table_id, bk_tenant_id=tenant):
                if option.field_name not in RESULT_FIELDS:
                    option.pk = None
                    option.table_id = table_id
                    option.save()
            register_result_fields(table_id, tenant)
        rt, _ = models.ResultTableConfig.objects.get_or_create(
            bk_tenant_id=tenant,
            namespace=sink.namespace,
            name=name,
            defaults={"data_link_name": name, "bk_biz_id": sink.bk_biz_id, "table_id": table_id, "data_type": "log"},
        )
        rt_config = rt.compose_config(
            fields=[
                {
                    "field_name": field,
                    "field_type": kind,
                    "field_alias": field,
                    "description": field,
                    "is_dimension": field in PATTERN_KEYS,
                    "field_index": index,
                }
                for index, (field, kind) in enumerate(fields.items())
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
                "timezone": source.time_zone,
            },
        )
        # 在不同集群使用同一个固定物理名称，历史路由可以复用原来的查询目标。
        # 与 BKBase ResultTable.result_table_id() 的业务前缀保持一致。
        physical_name = f"{rt_config['spec']['bizId']}_{rt.name}"
        storage = models.ESStorage.objects.filter(bk_tenant_id=tenant, table_id=table_id).first()
        is_moving_cluster = storage is None or storage.storage_cluster_id != cluster.cluster_id
        storage_options = {
            key: getattr(source, key)
            for key in ("date_format", "slice_size", "slice_gap", "retention", "warm_phase_days", "time_zone")
        }
        storage_options.update(
            index_settings=json.loads(source.index_settings or "{}"),
            warm_phase_settings=source.warm_phase_settings,
        )
        if suffix == "pattern":
            # Pattern Binding 使用按日写别名，与原表的日期格式独立。
            storage_options["date_format"] = "%Y%m%d"
        else:
            storage_options["mapping_settings"] = json.loads(source.mapping_settings or "{}")
        if storage is None:
            storage = models.ESStorage.create_table(
                bk_tenant_id=tenant,
                table_id=table_id,
                cluster_id=cluster.cluster_id,
                source_type="log" if suffix == "pattern" else source.source_type,
                index_set=physical_name,
                need_create_index=True,
                enable_create_index=False,
                is_sync_db=False,
                **storage_options,
            )
        else:
            if suffix == "pattern":
                storage.source_type = "log"
            storage.need_create_index = True
            for key, value in storage_options.items():
                setattr(storage, key, json.dumps(value) if key in ("index_settings", "mapping_settings") else value)
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
            storage.save()
        if storage.update_index_and_aliases(ahead_time=0, is_moving_cluster=is_moving_cluster, strict=True) is False:
            raise RuntimeError(f"{table_id} ES 索引或写别名未准备完成")
        binding_ref = binding.reference
        if settings.ENABLE_MULTI_TENANT_MODE:
            binding_ref["tenant"] = tenant
        refs = {
            "result_table": {**binding_ref, "kind": rt.kind, "name": rt.name},
            "es_binding": binding_ref,
        }

    binding_config = binding.compose_config(
        storage_cluster_name=cluster.cluster_name,
        write_alias_format=f"write_%Y%m%d_{physical_name}",
        unique_field_list=PATTERN_KEYS,
        rt_name=rt.name,
    )
    binding_config["metadata"]["annotations"] = {"physical_table_name": physical_name}
    if suffix == "pattern":
        binding_config["spec"].update(doc_value_fields=PATTERN_KEYS)
    else:
        binding_config["spec"].update(
            unique_field_list=es_config.unique_field_list,
            json_field_list=es_config.json_field_list,
        )
    return [rt_config, binding_config], refs


def publish_clustering_routes(datalink):
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
    table_ids = [rt.table_id, sink.table_id]
    if sink.result.get("mode") == "append":
        ref = sink.result["result_table"]
        table_ids.append(
            models.ResultTableConfig.objects.get(
                bk_tenant_id=datalink.bk_tenant_id, namespace=ref["namespace"], name=ref["name"]
            ).table_id
        )
    route_ids = list(table_ids)
    for table_id in table_ids:
        storage = models.ESStorage.objects.get(bk_tenant_id=datalink.bk_tenant_id, table_id=table_id)
        routes = models.ESStorage.objects.filter(
            bk_tenant_id=datalink.bk_tenant_id,
            origin_table_id=table_id,
        )
        related_ids = list(routes.values_list("table_id", flat=True))
        # 普通检索的虚拟 RT 可有其他别名；增量补签名，避免其遮住源表别名。
        if table_id != rt.table_id and (
            table_id != sink.table_id or sink.result.get("mode", "update_original") == "update_original"
        ):
            for route_id in related_ids:
                register_signature_alias(route_id, sink.bk_tenant_id)
        route_ids.extend(related_ids)
        routes.update(storage_cluster_id=storage.storage_cluster_id)
    if route_ids:
        SpaceTableIDRedis().push_table_id_detail(
            table_id_list=route_ids, bk_tenant_id=datalink.bk_tenant_id, is_publish=True, raise_on_log_write_error=True
        )
