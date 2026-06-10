"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import uuid
from collections.abc import Callable

from django.db import transaction
from django.db.models import Q, Model
from django.db.models.base import ModelBase

from metadata import config

logger = logging.getLogger("metadata")

models = {
    "DataSource": None,
    "DataSourceOption": None,
    "DataSourceResultTable": None,
    "ResultTable": None,
    "ResultTableField": None,
    "ClusterInfo": None,
    "KafkaTopicInfo": None,
    "ESStorage": None,
    "TimeSeriesGroup": None,
    "EventGroup": None,
    "ResultTableOption": None,
    "ResultTableFieldOption": None,
    "InfluxDBStorage": None,
}


def add_datasource(models, data_id, data_name, etl_config, source_label, type_label, user, is_custom_source):
    kafka_cluster = models["ClusterInfo"].objects.get(cluster_type="kafka", is_default_cluster=True)

    data_object = models["DataSource"].objects.create(
        bk_data_id=data_id,
        data_name=data_name,
        etl_config=etl_config,
        source_label=source_label,
        type_label=type_label,
        creator=user,
        mq_cluster_id=kafka_cluster.cluster_id,
        is_custom_source=is_custom_source,
        data_description=f"init data_source for {data_name}",
        # 由于mq_config和data_source两者相互指向对方，所以只能先提供占位符，先创建data_source
        mq_config_id=0,
        last_modify_user=user,
    )

    # 获取这个数据源对应的配置记录model，并创建一个新的配置记录
    mq_config = models["KafkaTopicInfo"].objects.create(
        bk_data_id=data_object.bk_data_id,
        topic=f"{config.KAFKA_TOPIC_PREFIX}{data_object.bk_data_id}0",
        partition=1,
    )
    data_object.mq_config_id = mq_config.id
    data_object.save()


def add_datasourceresulttable(models, data_id, table_id, user):
    models["DataSourceResultTable"].objects.create(bk_data_id=data_id, table_id=table_id, creator=user)


def add_resulttable(
    models, table_id, table_name_zh, label, default_storage, is_custom_table, schema_type, user, bk_biz_id
):
    models["ResultTable"].objects.create(
        table_id=table_id,
        table_name_zh=table_name_zh,
        is_custom_table=is_custom_table,
        schema_type=schema_type,
        default_storage=default_storage,
        creator=user,
        last_modify_user=user,
        bk_biz_id=bk_biz_id,
        label=label,
        is_enable=1,
    )


def add_resulttablefield(models, table_id, field_item_list, user):
    for item in field_item_list:
        models["ResultTableField"].objects.create(
            table_id=table_id,
            field_name=item["field_name"],
            field_type=item["field_type"],
            unit=item["unit"],
            tag=item["tag"],
            is_config_by_user=1,
            creator=user,
            description=item["description"],
        )


def add_esstorage(table_id):
    es_cluster = models["ClusterInfo"].objects.filter(cluster_type="elasticsearch", is_default_cluster=True).first()
    if es_cluster:
        models["ESStorage"].objects.create(
            table_id=table_id,
            storage_cluster_id=es_cluster.cluster_id,
            date_format="%Y%m%d",
            slice_gap=1440,
            index_settings=json.dumps({"number_of_shards": 4, "number_of_replicas": 0}),
            mapping_settings=json.dumps(
                {
                    "dynamic_templates": [
                        {"discover_dimension": {"path_match": "dimensions.*", "mapping": {"type": "keyword"}}}
                    ]
                }
            ),
        )


def add_datasource_token(models, data_id):
    datasource_model = models["DataSource"]
    datasource = datasource_model.objects.get(bk_data_id=data_id)
    datasource.token = uuid.uuid4().hex
    datasource.save()


def add_influxdbstorage(table_id, database, real_table_name, source_duration_time):
    influx_cluster = models["ClusterInfo"].objects.get(cluster_type="influxdb", is_default_cluster=True)
    models["InfluxDBStorage"].objects.create(
        table_id=table_id,
        storage_cluster_id=influx_cluster.cluster_id,
        database=database,
        real_table_name=real_table_name,
        source_duration_time=source_duration_time,
    )


def add_datasource_option(models, data_id, user, items):
    for item in items:
        models["DataSourceOption"].objects.create(
            bk_data_id=data_id,
            name=item["name"],
            value_type=item["value_type"],
            value=item["value"],
            creator=user,
        )


def add_result_table_option(models, table_id, user, items):
    for item in items:
        models["ResultTableOption"].objects.create(
            table_id=table_id,
            name=item["name"],
            value_type=item["value_type"],
            value=item["value"],
            creator=user,
        )


def add_es_resulttableoption(table_id, user):
    models["ResultTableOption"].objects.create(
        table_id=table_id,
        name="es_unique_field_list",
        value_type="list",
        value=json.dumps(["event", "target", "dimensions", "event_name", "time"]),
        creator=user,
    )


def add_resulttablefieldoption(items):
    for item in items:
        models["ResultTableFieldOption"].objects.create(
            value_type=item["value_type"],
            value=item["value"],
            creator=item["creator"],
            table_id=item["table_id"],
            field_name=item["field_name"],
            name=item["name"],
        )


def filter_apm_log_table_ids(data_source_model: ModelBase, ds_rt_model: ModelBase) -> dict[str, list]:
    """过滤 apm 和 log 对应的结果表"""
    data_ids = data_source_model.objects.filter(etl_config="bk_flat_batch").values_list("bk_data_id", flat=True)
    qs = ds_rt_model.objects.filter(bk_data_id__in=data_ids)
    # 根据 table id 进行过滤
    # table_id 以 bkapm_ 开头或者以 apm_global 开头或者包含 _bkapm，则为 apm 类型
    # table_id 包含 _bklog，则为 log 类型
    apm_table_id_list = list(
        qs.filter(
            Q(table_id__startswith="bkapm_") | Q(table_id__startswith="apm_global") | Q(table_id__contains="_bkapm")
        )
        .values_list("table_id", flat=True)
        .distinct()
    )
    log_table_id_list = list(qs.filter(table_id__contains="_bklog").values_list("table_id", flat=True).distinct())
    return {"apm": apm_table_id_list, "log": log_table_id_list}


def filter_table_id_es_versions(
    es_storage_model: ModelBase, cluster_info_model: ModelBase, table_id_list: list
) -> dict[str, str]:
    """根据结果表过滤使用的 ES 的版本"""
    qs = es_storage_model.objects.filter(table_id__in=table_id_list)
    table_id_storage_id_map = {obj.table_id: obj.storage_cluster_id for obj in qs}
    # 过滤 es 存储集群对应的集群版本
    cluster_qs = cluster_info_model.objects.filter(cluster_id__in=table_id_storage_id_map.values())
    cluster_id_version_map = {obj.cluster_id: obj.version for obj in cluster_qs}
    table_id_es_version_map = {}
    # 匹配结果表和使用的 es 的版本
    for table_id, cluster_id in table_id_storage_id_map.items():
        version = cluster_id_version_map.get(cluster_id)
        if not version:
            print(f"table_id: {table_id}, cluster_id: {cluster_id} not found version")
            continue
        table_id_es_version_map[table_id] = version

    return table_id_es_version_map


def get_log_field_options(
    rt_field_model: ModelBase, rt_field_option_model: ModelBase, table_id: str, es_version: str, creator: str
) -> list:
    """获取日志字段选项配置"""
    field_options = [
        {
            "table_id": table_id,
            "field_name": rt_field_model.FIELD_DEF_BK_HOST_ID["field_name"],
            "name": rt_field_option_model.OPTION_ES_FIELD_TYPE,
            "value_type": rt_field_option_model.TYPE_STRING,
            "value": "integer",
            "creator": creator,
        }
    ]
    # 如果版本为 5.x, 则需要添加 `es_include_in_all` 选项
    if es_version.startswith("5."):
        field_options.append(
            {
                "table_id": table_id,
                "field_name": rt_field_model.FIELD_DEF_BK_HOST_ID["field_name"],
                "name": rt_field_option_model.OPTION_ES_INCLUDE_IN_ALL,
                "value_type": rt_field_option_model.TYPE_BOOL,
                "value": "false",
                "creator": creator,
            }
        )

    return field_options


def parse_value(value):
    if type(value) in (bool, list, dict):
        val = json.dumps(value)
        if isinstance(value, bool):
            val_type = "bool"
        elif isinstance(value, list):
            val_type = "list"
        else:
            val_type = "dict"

    elif type(value) in (int,):
        val = json.dumps(value)
        val_type = "int"

    else:
        val, val_type = value, "string"
    return val, val_type


def sync_index_set_to_es_storages(es_storage_model: type[Model], table_ids: list[str]):
    # Step-1: ESStorage 指定索引集。
    to_be_updated_storages = []
    for es_storage_obj in es_storage_model.objects.filter(table_id__in=table_ids):
        es_storage_obj.index_set = es_storage_obj.table_id.replace(".", "_")
        to_be_updated_storages.append(es_storage_obj)

    if to_be_updated_storages:
        es_storage_model.objects.bulk_update(to_be_updated_storages, fields=["index_set"])
    logger.info("[migration_util] sync index_set to ESStorage: %s", len(to_be_updated_storages))


def _get_value_from_option(option: dict) -> object:
    """按 ResultTableOption.value_type 解析 option value。

    历史 ResultTableOption 的 value 统一存在文本字段里，只有 string 类型可以直接使用。
    其它类型需要按 JSON 还原，才能继续写回到真实 RT 的 time_field option。
    """
    if option["value_type"] == "string":
        return option["value"]

    try:
        return json.loads(option["value"])
    except (TypeError, ValueError):
        return {}


def _emit_backfill_detail(message: str, detail_logger: Callable[[str], None] | None = None):
    """输出本次回填的明细日志。

    migration 执行时只依赖 metadata logger；management command 会额外传入 detail_logger，
    把同一份明细打印到 stdout。这样 dry_run 和真实写入看到的变更预览完全一致。
    """
    logger.info("[backfill_esstorage_origin_table_options] %s", message)
    if detail_logger:
        detail_logger(message)


def _get_origin_table_time_fields(
    es_storage_model: type[Model],
    result_table_model: type[Model],
    result_table_option_model: type[Model],
    origin_table_keys: set[tuple[str, str]],
) -> dict[tuple[str, str], object]:
    """获取真实 ES 表对应虚拟 RT 上配置的 time_field。

    日志平台的虚拟 RT 通过 ESStorage.origin_table_id 指向真实 RT。真实 RT 缺失
    time_field 时，只能从这些虚拟 RT 的查询 option 里继承，且必须同租户继承，
    避免多租户环境下同名 table_id 串配置。

    当一个真实 RT 关联多个虚拟 RT 时，优先取仍启用且未删除的虚拟 RT；如果没有
    启用候选，再按 ESStorage.id 稳定取第一个有 time_field 的虚拟 RT。
    """
    if not origin_table_keys:
        return {}

    tenant_ids = {bk_tenant_id for bk_tenant_id, _ in origin_table_keys}
    table_ids = {table_id for _, table_id in origin_table_keys}
    # 一次性取当前 batch 涉及的所有虚拟 ESStorage，避免按真实 RT 逐条查询。
    virtual_storages = list(
        es_storage_model.objects.filter(
            bk_tenant_id__in=tenant_ids,
            origin_table_id__in=table_ids,
        )
        .exclude(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
        .values("id", "bk_tenant_id", "table_id", "origin_table_id")
        .order_by("bk_tenant_id", "origin_table_id", "id")
    )

    virtual_table_keys = {
        (storage["bk_tenant_id"], storage["table_id"])
        for storage in virtual_storages
        if (storage["bk_tenant_id"], storage["origin_table_id"]) in origin_table_keys
    }
    if not virtual_table_keys:
        return {}

    virtual_tenants = {bk_tenant_id for bk_tenant_id, _ in virtual_table_keys}
    virtual_table_ids = {table_id for _, table_id in virtual_table_keys}
    # ResultTable 状态只参与候选优先级排序，不直接过滤；没有启用候选时仍可回退历史虚拟 RT。
    virtual_rt_status = {
        (record["bk_tenant_id"], record["table_id"]): (record["is_enable"], record["is_deleted"])
        for record in result_table_model.objects.filter(
            bk_tenant_id__in=virtual_tenants,
            table_id__in=virtual_table_ids,
        ).values("bk_tenant_id", "table_id", "is_enable", "is_deleted")
    }
    virtual_time_fields = {}
    for option in (
        result_table_option_model.objects.filter(
            bk_tenant_id__in=virtual_tenants,
            table_id__in=virtual_table_ids,
            name="time_field",
        )
        .values("id", "bk_tenant_id", "table_id", "value", "value_type")
        .order_by("bk_tenant_id", "table_id", "id")
    ):
        option_key = (option["bk_tenant_id"], option["table_id"])
        # 同一个虚拟 RT 历史上可能存在重复 option，按 id 排序后只取最早的一条，保持结果稳定。
        virtual_time_fields.setdefault(option_key, _get_value_from_option(option))

    origin_time_fields: dict[tuple[str, str], object] = {}
    origin_candidates: dict[tuple[str, str], list[tuple[int, int, object]]] = {}
    for storage in virtual_storages:
        origin_key = (storage["bk_tenant_id"], storage["origin_table_id"])
        virtual_key = (storage["bk_tenant_id"], storage["table_id"])
        if origin_key not in origin_table_keys or virtual_key not in virtual_time_fields:
            continue

        is_enable, is_deleted = virtual_rt_status.get(virtual_key, (False, True))
        # priority=0 表示启用且未删除；priority=1 是最后兜底候选。
        priority = 0 if is_enable and not is_deleted else 1
        origin_candidates.setdefault(origin_key, []).append((priority, storage["id"], virtual_time_fields[virtual_key]))

    for origin_key, candidates in origin_candidates.items():
        origin_time_fields[origin_key] = sorted(candidates, key=lambda item: (item[0], item[1]))[0][2]

    return origin_time_fields


def _build_result_table_options(
    result_table_option_model: type[Model],
    target_keys: set[tuple[str, str]],
    time_field_map: dict[tuple[str, str], object],
    stats: dict[str, int],
    detail_logger: Callable[[str], None] | None = None,
):
    """构造需要创建或更新的 ResultTableOption 对象。

    need_add_time 是真实 ES RT 必须补齐的固定查询配置；time_field 则必须能从虚拟
    RT 继承到明确值才写入。找不到 time_field 时只打印明细并跳过，避免把错误的
    空 dict 写入真实 RT。
    """
    tenant_ids = {bk_tenant_id for bk_tenant_id, _ in target_keys}
    table_ids = {table_id for _, table_id in target_keys}
    existing_options: dict[tuple[str, str, str], list[Model]] = {}
    for option in result_table_option_model.objects.filter(
        bk_tenant_id__in=tenant_ids,
        table_id__in=table_ids,
        name__in=["need_add_time", "time_field"],
    ).order_by("id"):
        existing_options.setdefault((option.bk_tenant_id, option.table_id, option.name), []).append(option)

    to_be_created = []
    to_be_updated = []
    for bk_tenant_id, table_id in sorted(target_keys):
        # 所有命中的真实 ES RT 都需要补 need_add_time；time_field 只有继承到值才追加。
        option_values = {
            "need_add_time": True,
        }
        time_field = time_field_map.get((bk_tenant_id, table_id))
        if time_field:
            option_values["time_field"] = time_field
        else:
            stats["time_field_skipped"] += 1
            detail_message = (
                f"skip time_field bk_tenant_id={bk_tenant_id} table_id={table_id}, "
                "no virtual ESStorage time_field found"
            )
            logger.warning(
                "[backfill_esstorage_origin_table_options] %s",
                detail_message,
            )
            if detail_logger:
                detail_logger(detail_message)

        for option_name, option_value in option_values.items():
            value, value_type = parse_value(option_value)
            option_key = (bk_tenant_id, table_id, option_name)
            if option_key not in existing_options:
                _emit_backfill_detail(
                    f"create option bk_tenant_id={bk_tenant_id} table_id={table_id} name={option_name} "
                    f"value_type={value_type} value={value}",
                    detail_logger,
                )
                to_be_created.append(
                    result_table_option_model(
                        bk_tenant_id=bk_tenant_id,
                        table_id=table_id,
                        name=option_name,
                        value=value,
                        value_type=value_type,
                        creator="system",
                    )
                )
                continue

            # 可能存在历史重复 option。为了避免运行后仍有脏值，所有重复记录都同步为目标值。
            for option in existing_options[option_key]:
                if option.value == value and option.value_type == value_type:
                    continue
                _emit_backfill_detail(
                    f"update option bk_tenant_id={bk_tenant_id} table_id={table_id} name={option_name} "
                    f"value_type={value_type} value={value}",
                    detail_logger,
                )
                option.value = value
                option.value_type = value_type
                to_be_updated.append(option)

    return to_be_created, to_be_updated


def backfill_esstorage_origin_table_options(
    es_storage_model: type[Model],
    result_table_model: type[Model],
    result_table_option_model: type[Model],
    bk_tenant_id: str | None = None,
    batch_size: int = 500,
    dry_run: bool = False,
    detail_logger: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """回填真实 ESStorage 的 index_set 与日志查询 ResultTableOption。

    处理范围限定为 origin_table_id 为空的真实 ESStorage。数据量可能较大，所以使用
    id 游标按 batch 分片处理；每个 batch 内再批量查询 ResultTable、虚拟 ESStorage
    和 ResultTableOption，避免按表逐条查库。

    dry_run=True 时仍完整执行查询、对象构造和明细输出，但跳过 bulk_update /
    bulk_create，因此可用来预览每个 table_id 将补的 index_set 和 option 配置。
    """
    batch_size = max(batch_size, 1)
    stats = {
        "scanned": 0,
        "index_set_updated": 0,
        "option_created": 0,
        "option_updated": 0,
        "time_field_skipped": 0,
    }
    last_id = 0
    base_qs = (
        es_storage_model.objects.filter(Q(origin_table_id__isnull=True) | Q(origin_table_id=""))
        .values("id", "bk_tenant_id", "table_id", "index_set")
        .order_by("id")
    )
    if bk_tenant_id:
        base_qs = base_qs.filter(bk_tenant_id=bk_tenant_id)

    while True:
        # 用 id 游标分页，避免大 offset 在 ESStorage 数据量较大时越来越慢。
        batch = list(base_qs.filter(id__gt=last_id)[:batch_size])
        if not batch:
            break
        last_id = batch[-1]["id"]
        stats["scanned"] += len(batch)

        batch_keys = {(record["bk_tenant_id"], record["table_id"]) for record in batch}
        tenant_ids = {bk_tenant_id for bk_tenant_id, _ in batch_keys}
        table_ids = {table_id for _, table_id in batch_keys}
        result_table_keys = {
            (record["bk_tenant_id"], record["table_id"])
            for record in result_table_model.objects.filter(
                bk_tenant_id__in=tenant_ids,
                table_id__in=table_ids,
            ).values("bk_tenant_id", "table_id")
        }
        target_keys = batch_keys & result_table_keys

        index_set_storages = []
        for record in batch:
            if record["index_set"]:
                continue
            # 真实 ESStorage 的默认 index_set 与既有迁移逻辑保持一致：把 table_id 中的点替换成下划线。
            index_set = record["table_id"].replace(".", "_")
            _emit_backfill_detail(
                f"update index_set bk_tenant_id={record['bk_tenant_id']} table_id={record['table_id']} "
                f"index_set={index_set}",
                detail_logger,
            )
            storage = es_storage_model(id=record["id"], index_set=index_set)
            index_set_storages.append(storage)

        time_field_map = _get_origin_table_time_fields(
            es_storage_model=es_storage_model,
            result_table_model=result_table_model,
            result_table_option_model=result_table_option_model,
            origin_table_keys=target_keys,
        )
        to_be_created_options, to_be_updated_options = _build_result_table_options(
            result_table_option_model=result_table_option_model,
            target_keys=target_keys,
            time_field_map=time_field_map,
            stats=stats,
            detail_logger=detail_logger,
        )

        stats["index_set_updated"] += len(index_set_storages)
        stats["option_created"] += len(to_be_created_options)
        stats["option_updated"] += len(to_be_updated_options)
        logger.info(
            "[backfill_esstorage_origin_table_options] batch last_id=%s scanned=%s index_set=%s option_create=%s "
            "option_update=%s",
            last_id,
            len(batch),
            len(index_set_storages),
            len(to_be_created_options),
            len(to_be_updated_options),
        )

        if dry_run:
            # dry_run 已经输出了所有明细和统计，不能进入写库事务。
            continue

        with transaction.atomic(config.DATABASE_CONNECTION_NAME):
            if index_set_storages:
                es_storage_model.objects.bulk_update(index_set_storages, ["index_set"], batch_size=batch_size)
            if to_be_created_options:
                result_table_option_model.objects.bulk_create(to_be_created_options, batch_size=batch_size)
            if to_be_updated_options:
                result_table_option_model.objects.bulk_update(
                    to_be_updated_options,
                    ["value", "value_type"],
                    batch_size=batch_size,
                )

    logger.info("[backfill_esstorage_origin_table_options] stats: %s", stats)
    return stats
