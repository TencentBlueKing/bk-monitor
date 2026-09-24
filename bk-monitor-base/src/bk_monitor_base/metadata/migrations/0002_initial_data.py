import json
import logging
import os

from django.db import connections, migrations

from bk_monitor_base.metadata import config
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.migration_util import (
    add_datasource,
    add_datasource_option,
    add_datasourceresulttable,
    add_esstorage,
    add_influxdbstorage,
    add_kafkastorage,
    add_resulttable,
    add_resulttable_option,
    add_resulttablefield,
    models,
)

logger = logging.getLogger("metadata")

BATCH_SIZE = 500
SYSTEM_USER = "system"


def init_label_data():
    """增加默认的label信息"""
    Label = models["Label"]
    init_data_path = os.path.join(config.BASE_DIR, "metadata/data/init_label.json")
    with open(init_data_path) as init_file:
        label_data = json.load(init_file)
    labels = [Label(**label) for label in label_data]
    Label.objects.bulk_create(labels, batch_size=BATCH_SIZE)


def init_cluster_info():
    """增加默认的集群信息"""
    init_data_path = os.path.join(config.BASE_DIR, "metadata/data/init_cluster_info.json")
    with open(init_data_path) as init_file:
        cluster_info = json.load(init_file)
    for cluster in cluster_info:
        # 将域名和端口去掉，写入占位信息，实际域名和端口信息，由定时任务刷入
        cluster["domain_name"] = ""
        cluster["port"] = 0
        cluster["display_name"] = cluster["cluster_name"]
        models["ClusterInfo"].objects.create(**cluster)
        logger.info("cluster->[{}] now is inited done.".format(cluster["cluster_name"]))


def init_datasource():
    """增加默认的数据源信息"""
    init_data_path = os.path.join(config.BASE_DIR, "metadata/data/init_datasource.json")
    with open(init_data_path) as init_file:
        data_source_list = json.load(init_file)
    for data_source in data_source_list:
        add_datasource(
            models=models,
            data_id=data_source["bk_data_id"],
            data_name=data_source["data_name"],
            etl_config=data_source["etl_config"],
            source_label=data_source["source_label"],
            type_label=data_source["type_label"],
            is_custom_source=data_source["is_custom_source"],
            user=SYSTEM_USER,
        )
        # 写入datasourceoption信息
        for option in data_source["option_list"]:
            if option["name"] == "metrics_report_path":
                option["value"] = "{}/influxdb_metrics/{}/time_series_metric".format(
                    config.CONSUL_PATH, data_source["bk_data_id"]
                )
        add_datasource_option(
            models=models, data_id=data_source["bk_data_id"], user=SYSTEM_USER, items=data_source["option_list"]
        )


def init_resulttable():
    """增加默认的结果表信息"""
    init_data_path = os.path.join(config.BASE_DIR, "metadata/data/init_resulttable.json")
    with open(init_data_path) as init_file:
        result_table_list = json.load(init_file)
    for result_table in result_table_list:
        # 创建结果表
        table_id = result_table["table_id"]
        add_resulttable(
            models=models,
            table_id=table_id,
            table_name_zh=result_table["table_name_zh"],
            label=result_table["label"],
            default_storage=result_table["default_storage"],
            is_custom_table=result_table["is_custom_table"],
            schema_type=result_table["schema_type"],
            user=SYSTEM_USER,
            bk_biz_id=result_table["bk_biz_id"],
            data_label=result_table["data_label"],
        )
        # 创建结果表Option
        add_resulttable_option(models=models, table_id=table_id, user=SYSTEM_USER, items=result_table["option_list"])

        # 创建结果表字段及Option
        add_resulttablefield(
            models=models,
            table_id=table_id,
            field_item_list=result_table["field_list"],
            user=SYSTEM_USER,
        )
        # 创建data_id和该结果表的关系
        add_datasourceresulttable(
            models=models, data_id=result_table["bk_data_id"], table_id=table_id, user=SYSTEM_USER
        )

        # 5. 创建实际结果表记录
        if result_table["default_storage"] == "influxdb":
            database, table_name = table_id.split(".")
            add_influxdbstorage(
                table_id=table_id, database=database, real_table_name=table_name, source_duration_time="90d"
            )
        elif result_table["default_storage"] == "elasticsearch":
            add_esstorage(table_id)

    storage_path = os.path.join(config.BASE_DIR, "metadata/data/init_storage.json")
    with open(storage_path) as init_file:
        storage_data = json.load(init_file)
    for table_id in storage_data["kafka_storage"]:
        topic = "_".join([config.KAFKA_TOPIC_PREFIX_STORAGE, table_id])
        add_kafkastorage(table_id, topic)


def init_ts_or_event_group():
    """增加默认的时序组和事件组信息"""
    TimeSeriesGroup = models["TimeSeriesGroup"]
    EventGroup = models["EventGroup"]
    init_data_path = os.path.join(config.BASE_DIR, "metadata/data/init_ts_or_event_group.json")
    with open(init_data_path) as init_file:
        group_dict = json.load(init_file)
    ts_list = []
    event_list = []
    for group in group_dict["time_series_group"]:
        ts_list.append(
            TimeSeriesGroup(
                bk_data_id=group["bk_data_id"],
                bk_biz_id=group["bk_biz_id"],
                table_id=group["table_id"],
                max_rate=group["max_rate"],
                label=group["label"],
                time_series_group_name=group["time_series_group_name"],
                creator=SYSTEM_USER,
                last_modify_user=SYSTEM_USER,
                is_delete=False,
                is_enable=True,
            )
        )
    TimeSeriesGroup.objects.bulk_create(ts_list, batch_size=BATCH_SIZE)
    for group in group_dict["event_group"]:
        event_list.append(
            EventGroup(
                bk_data_id=group["bk_data_id"],
                bk_biz_id=group["bk_biz_id"],
                table_id=group["table_id"],
                label=group["label"],
                event_group_name=group["event_group_name"],
                creator=SYSTEM_USER,
                last_modify_user=SYSTEM_USER,
                is_delete=False,
                is_enable=True,
            )
        )
    EventGroup.objects.bulk_create(event_list, batch_size=BATCH_SIZE)


def alter_datasource_auto_increment():
    # 将自增ID限制在GSE提供的最小ID及以上
    # GSE提供的数据范围为：[1 048 576, 2 097 151]
    # 定义：
    # 1 100 000 ~ 1 199 999为监控内置数据源
    # 1 200 000 ~ 2 097 151为用户自定义数据源
    cursor = connections[settings.metadata.backend_database_name].cursor()
    cursor.execute("ALTER TABLE metadata_datasource AUTO_INCREMENT = 1200000")


def init_data(apps, schema_editor):
    # 获取APP models
    for model_name in list(models.keys()):
        models[model_name] = apps.get_model("old_metadata", model_name)

    init_label_data()
    init_cluster_info()
    init_datasource()
    init_resulttable()
    init_ts_or_event_group()
    alter_datasource_auto_increment()


class Migration(migrations.Migration):
    dependencies = [
        ("old_metadata", "0001_initial"),
    ]

    operations = [migrations.RunPython(init_data)]
