import copy
import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from metadata import models
from metadata.models.constants import DT_TIME_STAMP_NANO, EPOCH_MILLIS_FORMAT, NANO_FORMAT, STRICT_NANO_ES_FORMAT
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

logger = logging.getLogger(__name__)


def migrate_nano_log_tables(bk_tenant_id: str, table_ids: list[str]):
    """迁移日志纳秒结果表

    Args:
        table_ids: 结果表ID列表
    """

    migrate_results: dict[str, tuple[bool, str, dict[str, Any] | None]] = {}

    for table_id in table_ids:
        try:
            # 迁移单个结果表，不刷新路由，后续统一刷新
            migrate_results[table_id] = migrate_nano_log_table(
                bk_tenant_id=bk_tenant_id, table_id=table_id, refresh_router=False
            )
        except Exception as e:
            logger.exception(f"migrate nano log table {table_id} failed: {e}")
            migrate_results[table_id] = False, f"unknown error: {e}", None

    need_refresh_spaces: set[tuple[str, str]] = set()
    need_refresh_data_labels: set[str] = set()
    need_refresh_table_ids: set[str] = set()

    # 收集需要刷新的空间、data_label、ES表详情
    for table_id, result in migrate_results.items():
        if not result[0]:
            continue

        result_data = result[2]
        if result_data is None:
            continue

        space_type = result_data["space_type"]
        space_id = result_data["space_id"]
        need_refresh_spaces.add((space_type, space_id))
        need_refresh_table_ids.update(result_data["need_refresh_table_ids"])
        need_refresh_data_labels.update(result_data["need_refresh_data_labels"])

    # 批量刷新空间路由、data_label路由、ES表详情路由
    for space_type, space_id in need_refresh_spaces:
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)
    if need_refresh_data_labels:
        SpaceTableIDRedis().push_data_label_table_ids(
            bk_tenant_id=bk_tenant_id, data_label_list=list(need_refresh_data_labels), is_publish=True
        )
    if need_refresh_table_ids:
        SpaceTableIDRedis().push_es_table_id_detail(
            table_id_list=list(need_refresh_table_ids), is_publish=True, bk_tenant_id=bk_tenant_id
        )

    return migrate_results


def migrate_nano_log_table(
    bk_tenant_id: str, table_id: str, refresh_router: bool = True
) -> tuple[bool, str, dict[str, Any] | None]:
    """迁移日志纳秒结果表

    Args:
        table_id: 结果表ID
        refresh_router: 是否刷新路由
    """
    try:
        result_table = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
    except models.ResultTable.DoesNotExist:
        logger.error(f"result table not found: {table_id}")
        return False, f"result table not found: {table_id}", None
    except models.ResultTable.MultipleObjectsReturned:
        logger.error(f"multiple result tables found: {table_id}")
        return False, f"multiple result tables found: {table_id}", None

    # 检查是否已经迁移过
    new_table_id = f"{table_id}_nano"
    if models.ResultTable.objects.filter(table_id=new_table_id, bk_tenant_id=bk_tenant_id).exists():
        logger.info(f"result table {table_id} has been migrated: {new_table_id}")
        return False, f"result table {table_id} has been migrated: {new_table_id}", None

    # 获取空间信息
    bk_biz_id = result_table.bk_biz_id
    if bk_biz_id == 0:
        raise ValueError(f"result table {table_id} bk_biz_id is 0")
    elif bk_biz_id > 0:
        space_type = "bkcc"
        space_id = str(bk_biz_id)
    else:
        space = models.Space.objects.get(bk_tenant_id=bk_tenant_id, id=-bk_biz_id)
        space_type = space.space_type_id
        space_id = space.space_id

    result_table_options = list(models.ResultTableOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id))
    result_table_fields = list(models.ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id))
    result_table_field_options = list(
        models.ResultTableFieldOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
    )
    es_storage = models.ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
    es_field_query_alias_options = list(
        models.ESFieldQueryAliasOption.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id)
    )

    # 复制新结果表相关配置
    new_result_table = copy.deepcopy(result_table)
    new_result_table_options = copy.deepcopy(result_table_options)
    new_result_table_fields = copy.deepcopy(result_table_fields)
    new_result_table_field_options = copy.deepcopy(result_table_field_options)
    new_es_storage = copy.deepcopy(es_storage)
    new_es_field_query_alias_options = copy.deepcopy(es_field_query_alias_options)

    new_records_list = [
        new_result_table,
        *new_result_table_options,
        *new_result_table_fields,
        *new_result_table_field_options,
        new_es_storage,
        *new_es_field_query_alias_options,
    ]
    # 移除pk字段，替换table_id
    for record in new_records_list:
        record.pk = None
        record.table_id = new_table_id
        record.save()

    # 增加dtEventTimestampNanos字段，将旧的时间字段变更为毫秒
    models.ResultTableField.objects.create(
        table_id=new_table_id,
        field_name=DT_TIME_STAMP_NANO,
        field_type="timestamp",
        description="数据时间",
        tag="dimension",
        is_config_by_user=True,
        bk_tenant_id=bk_tenant_id,
    )

    # 通过复制的方式,生成dtEventTimestampNanos的option
    original_objects = models.ResultTableFieldOption.objects.filter(
        table_id=new_table_id, field_name="dtEventTimeStamp", bk_tenant_id=bk_tenant_id
    )

    # 创建新对象，修改 field_name 为 'dtEventTimeStampNanos'
    for obj in original_objects:
        # 使用 get_or_create 以确保不会重复创建相同的记录
        models.ResultTableFieldOption.objects.update_or_create(
            table_id=new_table_id,
            field_name="dtEventTimeStampNanos",  # 更新 field_name
            name=obj.name,
            defaults={  # 如果记录不存在，才会使用 defaults 来创建新的记录
                "value_type": obj.value_type,
                "value": obj.value,
                "creator": obj.creator,
                "bk_tenant_id": obj.bk_tenant_id,
            },
        )

    update_field_options = [
        ("dtEventTimeStampNanos", "es_type", NANO_FORMAT),
        ("dtEventTimeStampNanos", "es_format", STRICT_NANO_ES_FORMAT),
        ("dtEventTimeStamp", "es_format", EPOCH_MILLIS_FORMAT),
        ("dtEventTimeStamp", "es_type", "date"),
    ]

    for field_name, name, value in update_field_options:
        models.ResultTableFieldOption.objects.filter(
            table_id=new_table_id, field_name=field_name, name=name, bk_tenant_id=bk_tenant_id
        ).update(value=value)

    # 增加新表集群迁移记录，为了确保数据能够正常被查询，将enable_time设置为当前时间的前两年
    models.StorageClusterRecord.objects.update_or_create(
        table_id=new_table_id,
        cluster_id=new_es_storage.storage_cluster_id,
        bk_tenant_id=bk_tenant_id,
        defaults={"is_current": True, "enable_time": timezone.now() - timedelta(days=365 * 2)},
    )

    # 旧表标记与新表的关联关系，后续构建data_label查询路由时，需要根据此字段进行查询
    models.ResultTableOption.objects.get_or_create(
        table_id=table_id,
        name="es_related_query_table_id",
        bk_tenant_id=bk_tenant_id,
        defaults={"value": new_table_id},
    )

    # 将原本的索引集关联的虚拟RT进行复制
    virtual_es_storages = models.ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, origin_table_id=table_id)
    virtual_table_ids = [es_storage.table_id for es_storage in virtual_es_storages]
    virtual_result_tables = models.ResultTable.objects.filter(table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id)
    virtual_result_table_options = models.ResultTableOption.objects.filter(
        table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
    )
    virtual_result_table_fields = models.ResultTableField.objects.filter(
        table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
    )
    virtual_result_table_field_options = models.ResultTableFieldOption.objects.filter(
        table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
    )
    virtual_storage_cluster_records = models.StorageClusterRecord.objects.filter(
        table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
    )
    virtual_es_field_query_alias_options = models.ESFieldQueryAliasOption.objects.filter(
        table_id__in=virtual_table_ids, bk_tenant_id=bk_tenant_id
    )

    # 获取虚拟RT的data_label
    virtual_data_labels = list(virtual_result_tables.values_list("data_label", flat=True))

    new_virtual_table_ids: set[str] = set()
    new_records_list = [
        *virtual_es_storages,
        *virtual_result_tables,
        *virtual_result_table_options,
        *virtual_result_table_fields,
        *virtual_result_table_field_options,
        *virtual_storage_cluster_records,
        *virtual_es_field_query_alias_options,
    ]
    for record in new_records_list:
        record.pk = None
        if hasattr(record, "origin_table_id"):
            record.origin_table_id = new_table_id
        if hasattr(record, "index_set") and getattr(record, "index_set", None):
            record.index_set += "_nano"
        record.table_id = record.table_id.split(".")[0] + "_nano" + ".__default__"
        new_virtual_table_ids.add(record.table_id)
        record.save()

    # 新rt对应的虚拟路由表需要增加时间字段别名，兼容新旧rt时间字段
    for new_virtual_table_id in new_virtual_table_ids:
        # 设置新表时间字段别名
        models.ESFieldQueryAliasOption.objects.update_or_create(
            table_id=new_virtual_table_id,
            query_alias="dtEventTimeStamp",
            field_path="dtEventTimeStampNanos",
            bk_tenant_id=bk_tenant_id,
        )

    # 停用旧表的索引轮转并删除datasource关联，并更新新表的datasource关联
    es_storage.need_create_index = False
    es_storage.save()
    old_dsrt = models.DataSourceResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
    bk_data_id = old_dsrt.bk_data_id
    old_dsrt.delete()
    models.DataSourceResultTable.objects.create(table_id=new_table_id, bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id)

    # 更新新表的索引轮转
    new_es_storage.create_index_v2()
    new_es_storage.create_or_update_aliases()

    # 刷新consul配置
    new_result_table.refresh_etl_config()

    # 刷新路由
    need_refresh_table_ids = virtual_table_ids + list(new_virtual_table_ids) + [new_table_id, table_id]
    need_refresh_data_labels = virtual_data_labels

    if refresh_router:
        SpaceTableIDRedis().push_space_table_ids(space_type=space_type, space_id=space_id, is_publish=True)
        SpaceTableIDRedis().push_data_label_table_ids(
            bk_tenant_id=bk_tenant_id, data_label_list=virtual_data_labels, is_publish=True
        )
        SpaceTableIDRedis().push_es_table_id_detail(
            bk_tenant_id=bk_tenant_id, table_id_list=need_refresh_table_ids, is_publish=True
        )

    return (
        True,
        f"result table {table_id} has been migrated: {table_id}_nano",
        {
            "space_type": space_type,
            "space_id": space_id,
            "need_refresh_table_ids": need_refresh_table_ids,
            "need_refresh_data_labels": need_refresh_data_labels,
        },
    )
