# Generated manually for system_base builtin metadata repair

import json
import uuid

from django.db import migrations, transaction


BK_TENANT_ID = "system"
BK_BIZ_ID = 0
OPERATOR = "system"
SOURCE_LABEL = "bk_monitor"
LABEL = "os"
DATA_LABEL = "system_base"

TYPE_BOOL = "bool"
TYPE_DICT = "dict"
TYPE_LIST = "list"
TYPE_STRING = "string"


def _parse_option_value(value):
    if isinstance(value, bool):
        return json.dumps(value), TYPE_BOOL
    if isinstance(value, list):
        return json.dumps(value), TYPE_LIST
    if isinstance(value, dict):
        return json.dumps(value), TYPE_DICT
    return value, TYPE_STRING


def _get_default_cluster_id(ClusterInfo, cluster_type):
    cluster = ClusterInfo.objects.filter(
        bk_tenant_id=BK_TENANT_ID,
        cluster_type=cluster_type,
        is_default_cluster=True,
    ).first()
    if cluster is None:
        raise ValueError(f"default {cluster_type} cluster for tenant {BK_TENANT_ID} does not exist")
    return cluster.cluster_id


def _ensure_data_source(models, config):
    DataSource = models["DataSource"]
    DataSourceOption = models["DataSourceOption"]
    KafkaTopicInfo = models["KafkaTopicInfo"]
    ClusterInfo = models["ClusterInfo"]

    data_source_by_id = DataSource.objects.filter(bk_data_id=config["bk_data_id"], bk_tenant_id=BK_TENANT_ID).first()
    data_source_by_name = DataSource.objects.filter(data_name=config["data_name"], bk_tenant_id=BK_TENANT_ID).first()
    if data_source_by_id and data_source_by_name and data_source_by_id.bk_data_id != data_source_by_name.bk_data_id:
        raise ValueError(
            f"conflicting system_base datasource records: data_id={config['bk_data_id']} and "
            f"data_name={config['data_name']}"
        )
    if data_source_by_name and data_source_by_name.bk_data_id != config["bk_data_id"]:
        raise ValueError(
            f"conflicting system_base datasource record: data_name={config['data_name']} already exists with "
            f"data_id={data_source_by_name.bk_data_id}, expected data_id={config['bk_data_id']}"
        )

    data_source = data_source_by_id or data_source_by_name
    if data_source is None:
        kafka_cluster_id = _get_default_cluster_id(ClusterInfo, "kafka")
        kafka_topic, _ = KafkaTopicInfo.objects.get_or_create(
            bk_data_id=config["bk_data_id"],
            defaults={
                "topic": f"bkmonitor_{config['bk_data_id']}0",
                "partition": 1,
            },
        )
        data_source = DataSource.objects.create(
            bk_data_id=config["bk_data_id"],
            bk_tenant_id=BK_TENANT_ID,
            data_name=config["data_name"],
            data_description=f"init data_source for {config['data_name']}",
            mq_cluster_id=kafka_cluster_id,
            mq_config_id=kafka_topic.id,
            etl_config=config["etl_config"],
            is_custom_source=True,
            creator=OPERATOR,
            last_modify_user=OPERATOR,
            source_label=SOURCE_LABEL,
            type_label=config["type_label"],
            token=uuid.uuid4().hex,
            is_enable=True,
            is_platform_data_id=True,
        )
        _ensure_data_source_options(DataSourceOption, config["bk_data_id"])
        return data_source

    updated_fields = []
    expected_values = {
        "data_name": config["data_name"],
        "etl_config": config["etl_config"],
        "source_label": SOURCE_LABEL,
        "type_label": config["type_label"],
        "is_custom_source": True,
        "is_platform_data_id": True,
        "is_enable": True,
    }
    for field_name, value in expected_values.items():
        if getattr(data_source, field_name) != value:
            setattr(data_source, field_name, value)
            updated_fields.append(field_name)
    if updated_fields:
        data_source.last_modify_user = OPERATOR
        updated_fields.extend(["last_modify_user", "last_modify_time"])
        data_source.save(update_fields=updated_fields)
    _ensure_data_source_options(DataSourceOption, config["bk_data_id"])
    return data_source


def _ensure_data_source_options(DataSourceOption, bk_data_id):
    option, created = DataSourceOption.objects.get_or_create(
        bk_data_id=bk_data_id,
        bk_tenant_id=BK_TENANT_ID,
        name="flat_batch_key",
        defaults={
            "value": "data",
            "value_type": TYPE_STRING,
            "creator": OPERATOR,
        },
    )
    if not created and (option.value != "data" or option.value_type != TYPE_STRING):
        option.value = "data"
        option.value_type = TYPE_STRING
        option.save(update_fields=["value", "value_type"])


def _ensure_result_table(models, config):
    ResultTable = models["ResultTable"]
    DataSourceResultTable = models["DataSourceResultTable"]

    result_table, created = ResultTable.objects.get_or_create(
        table_id=config["table_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={
            "table_name_zh": config["table_name_zh"],
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": config["default_storage"],
            "creator": OPERATOR,
            "last_modify_user": OPERATOR,
            "bk_biz_id": BK_BIZ_ID,
            "is_deleted": False,
            "is_enable": True,
            "label": LABEL,
            "data_label": DATA_LABEL,
            "is_builtin": False,
            "bk_biz_id_alias": config.get("bk_biz_id_alias", ""),
        },
    )
    if not created:
        updated_fields = []
        expected_values = {
            "table_name_zh": config["table_name_zh"],
            "is_custom_table": True,
            "schema_type": "free",
            "default_storage": config["default_storage"],
            "bk_biz_id": BK_BIZ_ID,
            "is_deleted": False,
            "is_enable": True,
            "label": LABEL,
            "data_label": DATA_LABEL,
            "is_builtin": False,
            "bk_biz_id_alias": config.get("bk_biz_id_alias", ""),
        }
        for field_name, value in expected_values.items():
            if getattr(result_table, field_name) != value:
                setattr(result_table, field_name, value)
                updated_fields.append(field_name)
        if updated_fields:
            result_table.last_modify_user = OPERATOR
            updated_fields.extend(["last_modify_user", "last_modify_time"])
            result_table.save(update_fields=updated_fields)

    DataSourceResultTable.objects.get_or_create(
        bk_data_id=config["bk_data_id"],
        table_id=config["table_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={"creator": OPERATOR},
    )
    return result_table


def _ensure_result_table_options(ResultTableOption, table_id, options):
    for name, value in options.items():
        parsed_value, value_type = _parse_option_value(value)
        option, created = ResultTableOption.objects.get_or_create(
            table_id=table_id,
            bk_tenant_id=BK_TENANT_ID,
            name=name,
            defaults={
                "value": parsed_value,
                "value_type": value_type,
                "creator": OPERATOR,
            },
        )
        if not created and (option.value != parsed_value or option.value_type != value_type):
            option.value = parsed_value
            option.value_type = value_type
            option.save(update_fields=["value", "value_type"])


def _ensure_result_table_fields(ResultTableField, table_id, fields):
    for field in fields:
        defaults = {
            "field_type": field["field_type"],
            "unit": field.get("unit", ""),
            "tag": field["tag"],
            "is_config_by_user": True,
            "default_value": field.get("default_value", ""),
            "creator": OPERATOR,
            "last_modify_user": OPERATOR,
            "description": field.get("description", ""),
            "alias_name": field.get("alias_name", ""),
        }
        rt_field, created = ResultTableField.objects.get_or_create(
            table_id=table_id,
            bk_tenant_id=BK_TENANT_ID,
            field_name=field["field_name"],
            defaults=defaults,
        )
        if created:
            continue
        updated_fields = []
        for field_name, value in defaults.items():
            if field_name == "creator":
                continue
            if getattr(rt_field, field_name) != value:
                setattr(rt_field, field_name, value)
                updated_fields.append(field_name)
        if updated_fields:
            rt_field.save(update_fields=updated_fields)


def _ensure_time_series(models, config):
    TimeSeriesGroup = models["TimeSeriesGroup"]
    InfluxDBStorage = models["InfluxDBStorage"]
    ResultTableOption = models["ResultTableOption"]
    ResultTableField = models["ResultTableField"]
    ClusterInfo = models["ClusterInfo"]

    group, created = TimeSeriesGroup.objects.get_or_create(
        bk_data_id=config["bk_data_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={
            "bk_biz_id": BK_BIZ_ID,
            "time_series_group_name": config["group_name"],
            "label": LABEL,
            "token": uuid.uuid4().hex,
            "creator": OPERATOR,
            "last_modify_user": OPERATOR,
            "is_delete": False,
            "is_enable": True,
            "table_id": config["table_id"],
            "is_split_measurement": True,
        },
    )
    if not created:
        updated_fields = []
        expected_values = {
            "time_series_group_name": config["group_name"],
            "label": LABEL,
            "is_delete": False,
            "is_enable": True,
            "table_id": config["table_id"],
            "is_split_measurement": True,
        }
        for field_name, value in expected_values.items():
            if getattr(group, field_name) != value:
                setattr(group, field_name, value)
                updated_fields.append(field_name)
        if not group.token:
            group.token = uuid.uuid4().hex
            updated_fields.append("token")
        if updated_fields:
            group.last_modify_user = OPERATOR
            updated_fields.extend(["last_modify_user", "last_modify_time"])
            group.save(update_fields=updated_fields)

    influxdb_cluster_id = _get_default_cluster_id(ClusterInfo, "influxdb")
    InfluxDBStorage.objects.get_or_create(
        table_id=config["table_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={
            "storage_cluster_id": influxdb_cluster_id,
            "real_table_name": "__default__",
            "database": f"bkmonitor_time_series_{config['bk_data_id']}",
            "source_duration_time": "30d",
        },
    )
    _ensure_result_table_fields(
        ResultTableField,
        config["table_id"],
        [
            {
                "field_name": "time",
                "field_type": "timestamp",
                "tag": "timestamp",
                "description": "数据上报时间",
            }
        ],
    )
    _ensure_result_table_options(ResultTableOption, config["table_id"], {"is_split_measurement": True})


def _ensure_event(models, config):
    EventGroup = models["EventGroup"]
    ESStorage = models["ESStorage"]
    ResultTableOption = models["ResultTableOption"]
    ResultTableField = models["ResultTableField"]
    ResultTableFieldOption = models["ResultTableFieldOption"]
    ClusterInfo = models["ClusterInfo"]

    group, created = EventGroup.objects.get_or_create(
        bk_data_id=config["bk_data_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={
            "bk_biz_id": BK_BIZ_ID,
            "event_group_name": config["group_name"],
            "label": LABEL,
            "token": uuid.uuid4().hex,
            "creator": OPERATOR,
            "last_modify_user": OPERATOR,
            "is_delete": False,
            "is_enable": True,
            "table_id": config["table_id"],
        },
    )
    if not created:
        updated_fields = []
        expected_values = {
            "event_group_name": config["group_name"],
            "label": LABEL,
            "is_delete": False,
            "is_enable": True,
            "table_id": config["table_id"],
        }
        for field_name, value in expected_values.items():
            if getattr(group, field_name) != value:
                setattr(group, field_name, value)
                updated_fields.append(field_name)
        if not group.token:
            group.token = uuid.uuid4().hex
            updated_fields.append("token")
        if updated_fields:
            group.last_modify_user = OPERATOR
            updated_fields.extend(["last_modify_user", "last_modify_time"])
            group.save(update_fields=updated_fields)

    es_cluster_id = _get_default_cluster_id(ClusterInfo, "elasticsearch")
    ESStorage.objects.get_or_create(
        table_id=config["table_id"],
        bk_tenant_id=BK_TENANT_ID,
        defaults={
            "storage_cluster_id": es_cluster_id,
            "date_format": "%Y%m%d",
            "slice_gap": 1440,
            "index_settings": json.dumps({"number_of_shards": 4, "number_of_replicas": 0}),
            "mapping_settings": json.dumps(
                {
                    "dynamic_templates": [
                        {"discover_dimension": {"path_match": "dimensions.*", "mapping": {"type": "keyword"}}}
                    ]
                }
            ),
            "index_set": config["table_id"],
        },
    )

    fields = [
        {"field_name": "time", "field_type": "timestamp", "tag": "timestamp", "description": "数据上报时间"},
        {"field_name": "event", "field_type": "object", "tag": "dimension"},
        {"field_name": "target", "field_type": "string", "tag": "dimension"},
        {"field_name": "dimensions", "field_type": "object", "tag": "dimension"},
        {"field_name": "event_name", "field_type": "string", "tag": "dimension"},
    ]
    _ensure_result_table_fields(ResultTableField, config["table_id"], fields)
    _ensure_result_table_options(
        ResultTableOption,
        config["table_id"],
        {
            "need_add_time": True,
            "time_field": {"name": "time", "type": "date", "unit": "millisecond"},
            "es_unique_field_list": ["event", "target", "dimensions", "event_name", "time"],
            "enable_v4_event_group_data_link": True,
        },
    )

    field_options = {
        "time": {"es_type": "date", "es_format": "epoch_millis"},
        "event": {"es_type": "object", "es_properties": {"content": {"type": "text"}, "count": {"type": "integer"}}},
        "target": {"es_type": "keyword"},
        "dimensions": {"es_type": "object", "es_dynamic": True},
        "event_name": {"es_type": "keyword"},
    }
    for field_name, options in field_options.items():
        for option_name, option_value in options.items():
            parsed_value, value_type = _parse_option_value(option_value)
            option, created = ResultTableFieldOption.objects.get_or_create(
                table_id=config["table_id"],
                bk_tenant_id=BK_TENANT_ID,
                field_name=field_name,
                name=option_name,
                defaults={
                    "value": parsed_value,
                    "value_type": value_type,
                    "creator": OPERATOR,
                },
            )
            if not created and (option.value != parsed_value or option.value_type != value_type):
                option.value = parsed_value
                option.value_type = value_type
                option.save(update_fields=["value", "value_type"])


def repair_system_base_builtin_metadata(apps, schema_editor):
    models = {
        "ClusterInfo": apps.get_model("metadata", "ClusterInfo"),
        "DataSource": apps.get_model("metadata", "DataSource"),
        "DataSourceOption": apps.get_model("metadata", "DataSourceOption"),
        "DataSourceResultTable": apps.get_model("metadata", "DataSourceResultTable"),
        "ESStorage": apps.get_model("metadata", "ESStorage"),
        "EventGroup": apps.get_model("metadata", "EventGroup"),
        "InfluxDBStorage": apps.get_model("metadata", "InfluxDBStorage"),
        "KafkaTopicInfo": apps.get_model("metadata", "KafkaTopicInfo"),
        "ResultTable": apps.get_model("metadata", "ResultTable"),
        "ResultTableField": apps.get_model("metadata", "ResultTableField"),
        "ResultTableFieldOption": apps.get_model("metadata", "ResultTableFieldOption"),
        "ResultTableOption": apps.get_model("metadata", "ResultTableOption"),
        "TimeSeriesGroup": apps.get_model("metadata", "TimeSeriesGroup"),
    }

    configs = [
        {
            "bk_data_id": 1100030,
            "data_name": "system_base_metric",
            "etl_config": "bk_standard_v2_time_series",
            "type_label": "time_series",
            "table_id": "bkmonitor_time_series_1100030.__default__",
            "table_name_zh": "系统基础指标",
            "group_name": "系统基础指标",
            "default_storage": "influxdb",
            "ensure_group": _ensure_time_series,
        },
        {
            "bk_data_id": 1100031,
            "data_name": "system_base_events",
            "etl_config": "bk_standard_v2_event",
            "type_label": "event",
            "table_id": "bkmonitor_event_1100031",
            "table_name_zh": "系统基础事件",
            "group_name": "系统基础事件",
            "default_storage": "elasticsearch",
            "bk_biz_id_alias": "dimensions.bk_biz_id",
            "ensure_group": _ensure_event,
        },
    ]

    with transaction.atomic(using=schema_editor.connection.alias):
        for config in configs:
            _ensure_data_source(models, config)
            _ensure_result_table(models, config)
            config["ensure_group"](models, config)


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0271_graph_relation_surrealdb_auto_restore"),
    ]

    operations = [
        migrations.RunPython(repair_system_base_builtin_metadata, migrations.RunPython.noop),
    ]
