import json
import logging
import uuid
from typing import Any

from django.db.models import Model, Q
from django.db.models.base import ModelBase

from bk_monitor_base.metadata import config

logger = logging.getLogger("metadata")

models = {
    "DataSource": None,
    "DataSourceOption": None,
    "DataSourceResultTable": None,
    "ResultTable": None,
    "ResultTableField": None,
    "ClusterInfo": None,
    "KafkaStorage": None,
    "KafkaTopicInfo": None,
    "ESStorage": None,
    "TimeSeriesGroup": None,
    "EventGroup": None,
    "ResultTableOption": None,
    "ResultTableFieldOption": None,
    "InfluxDBStorage": None,
    "Space": None,
    "BCSClusterInfo": None,
    "Label": None,
    "InfluxDBClusterInfo": None,
    "InfluxDBHostInfo": None,
}


def add_datasource(
    models: dict[str, type[Model]],
    data_id: int,
    data_name: str,
    etl_config: str,
    source_label: str,
    type_label: str,
    user: str,
    is_custom_source: bool,
):
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
        token=uuid.uuid4().hex,
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


def add_datasourceresulttable(models: dict[str, type[Model]], data_id: int, table_id: str, user: str):
    models["DataSourceResultTable"].objects.create(bk_data_id=data_id, table_id=table_id, creator=user)


def add_resulttable(
    models: dict[str, type[Model]],
    table_id: str,
    table_name_zh: str,
    label: str,
    default_storage: str,
    is_custom_table: bool,
    schema_type: str,
    user: str,
    bk_biz_id: int,
    data_label: str = "",
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
        data_label=data_label,
    )


def add_resulttablefield(
    models: dict[str, type[Model]], table_id: str, field_item_list: list[dict[str, Any]], user: str
):
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
            alias_name=item["alias_name"],
        )
        add_resulttablefieldoption(items=item["option_list"], table_id=table_id)


def add_esstorage(table_id):
    es_cluster = models["ClusterInfo"].objects.filter(cluster_type="elasticsearch", is_default_cluster=True).first()
    if es_cluster:
        models["ESStorage"].objects.create(
            table_id=table_id,
            storage_cluster_id=es_cluster.cluster_id,
            date_format="%Y%m%d",
            slice_gap=1440,
            index_set=table_id,
            index_settings=json.dumps({"number_of_shards": 4, "number_of_replicas": 0}),
            mapping_settings=json.dumps(
                {
                    "dynamic_templates": [
                        {"discover_dimension": {"path_match": "dimensions.*", "mapping": {"type": "keyword"}}}
                    ]
                }
            ),
        )


def add_kafkastorage(table_id: str, topic: str):
    kafka_cluster = models["ClusterInfo"].objects.filter(cluster_type="kafka", is_default_cluster=True).first()
    if kafka_cluster:
        models["KafkaStorage"].objects.create(
            table_id=table_id, storage_cluster_id=kafka_cluster.cluster_id, topic=topic, partition=1
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


def add_resulttable_option(models, table_id, user, items):
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


def add_resulttablefieldoption(items: list[dict[str, Any]], table_id: str):
    for item in items:
        models["ResultTableFieldOption"].objects.create(
            value_type=item["value_type"],
            value=item["value"],
            creator="system",
            table_id=table_id,
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
