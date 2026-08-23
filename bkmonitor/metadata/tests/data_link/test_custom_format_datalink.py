import json

import pydantic
import pytest

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.result_table import CustomFormatV4DataLinkOption
from metadata.models.space.constants import LOG_EVENT_ETL_CONFIGS, EtlConfigs
from metadata.task.datalink import apply_custom_format_datalink, compose_custom_format_data_link_name

pytestmark = pytest.mark.django_db(databases="__all__")


def _clean_rules():
    return [
        {"input_id": "item", "output_id": "metric", "operator": {"type": "assign", "output_type": "string"}},
        {"input_id": "item", "output_id": "value", "operator": {"type": "assign", "output_type": "double"}},
        {
            "input_id": "item",
            "output_id": "dimensions",
            "operator": {"type": "assign", "output_type": "text"},
        },
        {
            "input_id": "item",
            "output_id": "time",
            "operator": {
                "type": "assign",
                "output_type": "long",
                "is_time_field": True,
                "time_format": {"format": "Unix Time Stamp(milliseconds)", "zone": None},
            },
        },
    ]


def _replace_result_table_fields(table_id, fields):
    models.ResultTableField.objects.filter(bk_tenant_id="system", table_id=table_id).delete()
    for field_name, field_type, tag in fields:
        models.ResultTableField.objects.create(
            bk_tenant_id="system",
            table_id=table_id,
            field_name=field_name,
            field_type=field_type,
            tag=tag,
            is_config_by_user=True,
            creator="system",
            last_modify_user="system",
        )


@pytest.fixture
def custom_format_records():
    models.Label.objects.get_or_create(
        label_id=models.Label.RESULT_TABLE_LABEL_OTHER,
        defaults={
            "label_name": "其他",
            "label_type": models.Label.LABEL_TYPE_RESULT_TABLE,
        },
    )
    table_id = "custom_format.metric"
    data_source = models.DataSource.objects.create(
        bk_data_id=527765,
        data_name="custom_format_source",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_custom_format",
        is_custom_source=True,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    result_table = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_VM,
        creator="system",
        bk_biz_id=2,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        creator="system",
    )
    _replace_result_table_fields(
        table_id,
        (
            ("cpu_usage", "double", "metric"),
            ("host", "string", "dimension"),
        ),
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="bkm_custom_format_source",
        bk_biz_id=2,
        bk_data_id=data_source.bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
        value=json.dumps(
            {
                "target_storage_type": models.ClusterInfo.TYPE_VM,
                "clean_rules": _clean_rules(),
                "filter_rules": "True",
            }
        ),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        name=models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
        value=json.dumps(False),
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )
    data_link_name = compose_custom_format_data_link_name("system", data_source.bk_data_id, table_id)
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=data_link_name,
        namespace="bkmonitor",
        data_link_strategy=DataLink.CUSTOM_FORMAT_VM,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    return data_source, result_table, data_link


def test_custom_format_option_requires_target_storage_config():
    with pytest.raises(pydantic.ValidationError, match="es_storage_config"):
        CustomFormatV4DataLinkOption(
            target_storage_type=models.ClusterInfo.TYPE_ES,
            clean_rules=_clean_rules(),
        )


def test_custom_format_option_uses_bkbase_filter_rule_format():
    option = CustomFormatV4DataLinkOption(
        target_storage_type=models.ClusterInfo.TYPE_VM,
        clean_rules=_clean_rules(),
    )
    assert option.filter_rules == "True"

    filter_rule = {
        "BinOp": {
            "Eq": {
                "lval": {"Field": "env"},
                "rval": {"Const": "prod"},
            }
        }
    }
    option = CustomFormatV4DataLinkOption(
        target_storage_type=models.ClusterInfo.TYPE_VM,
        clean_rules=_clean_rules(),
        filter_rules=filter_rule,
    )
    assert option.filter_rules == filter_rule

    with pytest.raises(pydantic.ValidationError, match="filter_rules"):
        CustomFormatV4DataLinkOption(
            target_storage_type=models.ClusterInfo.TYPE_VM,
            clean_rules=_clean_rules(),
            filter_rules=[],
        )


def test_custom_format_datasource_is_registered_as_log():
    assert EtlConfigs.BK_CUSTOM_FORMAT.value in LOG_EVENT_ETL_CONFIGS


def test_custom_format_vm_does_not_create_metadata_storage(mocker, custom_format_records):
    _, result_table, _ = custom_format_records
    create_storage = mocker.patch.object(result_table, "create_storage")

    result_table.check_and_create_storage(
        bk_tenant_id="system",
        is_sync_db=True,
    )

    create_storage.assert_not_called()


def test_custom_format_data_link_name_is_stable_and_short():
    first = compose_custom_format_data_link_name("tenant-a", 527765, "db.very_long_table_name")
    second = compose_custom_format_data_link_name("tenant-a", 527765, "db.very_long_table_name")

    assert first == second
    assert len(first) <= 64


def test_compose_custom_format_vm_has_two_databuses(custom_format_records):
    data_source, result_table, data_link = custom_format_records

    configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    assert [config["kind"] for config in configs] == [
        "ResultTable",
        "ChannelBinding",
        "VmStorageBinding",
        "Databus",
        "Databus",
    ]
    result_table_config = configs[0]
    assert [(field["field_name"], field["field_type"]) for field in result_table_config["spec"]["fields"]] == [
        ("metric", "string"),
        ("value", "double"),
        ("dimensions", "text"),
        ("time", "long"),
    ]
    vm_binding = next(config for config in configs if config["kind"] == "VmStorageBinding")
    assert vm_binding["spec"]["filter"] == {
        "kind": "Whitelist",
        "metrics": ["cpu_usage"],
        "tags": ["host"],
    }
    databuses = {config["metadata"]["name"]: config for config in configs if config["kind"] == "Databus"}
    clean = databuses[f"{data_link.data_link_name}_clean"]
    shipper = databuses[f"{data_link.data_link_name}_shipper"]
    assert clean["spec"]["sources"][0]["kind"] == "DataId"
    assert clean["spec"]["sinks"][0]["kind"] == "ChannelBinding"
    assert clean["spec"]["transforms"][0]["kind"] == "Clean"
    assert clean["spec"]["transforms"][0]["filter_rules"] == "True"
    assert "context_map" not in clean["spec"]["transforms"][0]
    assert shipper["spec"]["sources"][0]["kind"] == "ResultTable"
    assert shipper["spec"]["sinks"][0]["kind"] == "VmStorageBinding"
    assert shipper["spec"]["transforms"] == [
        {"kind": "PreDefinedLogic", "name": "avro_to_metric", "tags": [], "fields": [], "schemaless": True}
    ]
    databus_records = models.DataBusConfig.objects.filter(data_link_name=data_link.data_link_name)
    assert set(databus_records.values_list("role", flat=True)) == {"clean", "vm_shipper"}
    assert len(set(databus_records.values_list("consumer_group", flat=True))) == 2


def test_compose_custom_format_vm_auto_discovery_has_no_whitelist(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    models.TimeSeriesGroup.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        bk_biz_id=result_table.bk_biz_id,
        table_id=result_table.table_id,
        time_series_group_name="custom_format_auto",
        label=result_table.label,
        token="auto-token",
        is_split_measurement=True,
        creator="system",
        last_modify_user="system",
    )
    enable_option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
    )
    enable_option.value = json.dumps(True)
    enable_option.save(update_fields=["value"])

    initial_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )
    models.ResultTableField.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        field_name="request_total",
        field_type="double",
        tag="metric",
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )

    configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    initial_result_table_config = initial_configs[0]
    result_table_config = configs[0]
    expected_field_names = [
        "metric",
        "value",
        "dimensions",
        "time",
    ]
    assert [field["field_name"] for field in initial_result_table_config["spec"]["fields"]] == expected_field_names
    assert [field["field_name"] for field in result_table_config["spec"]["fields"]] == expected_field_names
    vm_binding = next(config for config in configs if config["kind"] == "VmStorageBinding")
    assert vm_binding["spec"]["filter"] is None


def test_compose_custom_format_vm_fixed_fields_update_whitelist(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    initial_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )
    _replace_result_table_fields(
        result_table.table_id,
        (
            ("request_total", "double", "metric"),
            ("service", "string", "dimension"),
        ),
    )

    updated_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    initial_binding = next(config for config in initial_configs if config["kind"] == "VmStorageBinding")
    updated_binding = next(config for config in updated_configs if config["kind"] == "VmStorageBinding")
    assert initial_binding["spec"]["filter"]["metrics"] == ["cpu_usage"]
    assert updated_binding["spec"]["filter"] == {
        "kind": "Whitelist",
        "metrics": ["request_total"],
        "tags": ["service"],
    }


def test_compose_custom_format_vm_time_series_group_can_switch_to_whitelist(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    models.TimeSeriesGroup.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        bk_biz_id=result_table.bk_biz_id,
        table_id=result_table.table_id,
        time_series_group_name="custom_format_auto",
        label=result_table.label,
        token="auto-token",
        creator="system",
        last_modify_user="system",
    )
    enable_option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
    )
    enable_option.value = json.dumps(True)
    enable_option.save(update_fields=["value"])
    auto_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    enable_option.value = json.dumps(False)
    enable_option.save(update_fields=["value"])
    whitelist_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    auto_binding = next(config for config in auto_configs if config["kind"] == "VmStorageBinding")
    whitelist_binding = next(config for config in whitelist_configs if config["kind"] == "VmStorageBinding")
    assert auto_binding["spec"]["filter"] is None
    assert whitelist_binding["spec"]["filter"] == {
        "kind": "Whitelist",
        "metrics": ["cpu_usage"],
        "tags": ["host"],
    }


def test_compose_custom_format_vm_fixed_mode_requires_metric(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    models.ResultTableField.objects.filter(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
    ).delete()

    with pytest.raises(ValueError, match="缺少有效指标字段"):
        data_link.compose_custom_format_configs(
            bk_biz_id=2,
            data_source=data_source,
            table_id=result_table.table_id,
            storage_cluster_name="vm-cluster",
            inner_kafka_channel_name="kafka-inner",
        )


@pytest.mark.parametrize(
    ("target", "strategy", "binding_kind"),
    [
        (models.ClusterInfo.TYPE_ES, DataLink.CUSTOM_FORMAT_ES, "ElasticSearchBinding"),
        (models.ClusterInfo.TYPE_DORIS, DataLink.CUSTOM_FORMAT_DORIS, "DorisBinding"),
    ],
)
def test_compose_custom_format_log_storage_is_direct(custom_format_records, target, strategy, binding_kind):
    data_source, result_table, data_link = custom_format_records
    _replace_result_table_fields(
        result_table.table_id,
        (
            ("metric", "string", "dimension"),
            ("value", "double", "metric"),
            ("dimensions", "text", "dimension"),
            ("time", "long", "timestamp"),
        ),
    )
    data_link.namespace = "bklog"
    data_link.data_link_strategy = strategy
    data_link.save(update_fields=["namespace", "data_link_strategy"])
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="bkm_custom_format_source",
        bk_biz_id=2,
        bk_data_id=data_source.bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    cluster = models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=527770 if target == models.ClusterInfo.TYPE_ES else 527771,
        cluster_name="custom-storage",
        cluster_type=target,
        domain_name="storage.example.com",
        port=9200,
        description="",
        is_default_cluster=False,
    )
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    if target == models.ClusterInfo.TYPE_ES:
        models.ESStorage.objects.create(
            bk_tenant_id="system", table_id=result_table.table_id, storage_cluster_id=cluster.cluster_id
        )
        storage_config = {"es_storage_config": {"unique_field_list": [], "json_field_list": [], "timezone": 0}}
    else:
        models.DorisStorage.objects.create(
            bk_tenant_id="system", table_id=result_table.table_id, storage_cluster_id=cluster.cluster_id
        )
        storage_config = {
            "doris_storage_config": {
                "storage_keys": [],
                "json_fields": [],
                "original_json_fields": [],
                "field_config_group": {},
                "flush_timeout": None,
            }
        }
    clean_rules = [
        {
            "input_id": "item",
            "output_id": "custom_output",
            "operator": {"type": "assign", "output_type": "object"},
        }
    ]
    option.value = json.dumps(
        {"target_storage_type": target, "clean_rules": clean_rules, "filter_rules": "True", **storage_config}
    )
    option.save(update_fields=["value"])

    configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
    )

    assert [config["kind"] for config in configs] == ["ResultTable", binding_kind, "Databus"]
    databus = configs[-1]
    assert databus["spec"]["sources"][0]["kind"] == "DataId"
    assert databus["spec"]["sinks"][0]["kind"] == binding_kind
    assert databus["spec"]["transforms"][0]["kind"] == "Clean"
    assert databus["spec"]["transforms"][0]["rules"] == clean_rules


def test_custom_format_vm_does_not_validate_clean_contract(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    payload = json.loads(option.value)
    payload["clean_rules"] = [
        {
            "input_id": "item",
            "output_id": "custom_output",
            "operator": {"type": "assign", "output_type": "object"},
        }
    ]
    option.value = json.dumps(payload)
    option.save(update_fields=["value"])

    configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    result_table_config = configs[0]
    assert [field["field_name"] for field in result_table_config["spec"]["fields"]] == [
        "metric",
        "value",
        "dimensions",
        "time",
    ]
    clean = next(config for config in configs if config["metadata"]["name"] == f"{data_link.data_link_name}_clean")
    assert clean["spec"]["transforms"][0]["rules"] == payload["clean_rules"]


def test_custom_format_clean_rule_update_keeps_internal_resources_stable(custom_format_records):
    data_source, result_table, data_link = custom_format_records
    initial_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    payload = json.loads(option.value)
    payload["clean_rules"][0]["input_id"] = "renamed_metric_input"
    option.value = json.dumps(payload)
    option.save(update_fields=["value"])

    updated_configs = data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )

    assert {(config["kind"], config["metadata"]["name"]) for config in updated_configs} == {
        (config["kind"], config["metadata"]["name"]) for config in initial_configs
    }
    assert [(field["field_name"], field["field_type"]) for field in updated_configs[0]["spec"]["fields"]] == [
        ("metric", "string"),
        ("value", "double"),
        ("dimensions", "text"),
        ("time", "long"),
    ]


def test_custom_format_disable_deletes_managed_components_only(mocker, custom_format_records):
    data_source, result_table, data_link = custom_format_records
    data_link.compose_custom_format_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=result_table.table_id,
        storage_cluster_name="vm-cluster",
        inner_kafka_channel_name="kafka-inner",
    )
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=data_link.data_link_name,
        bkbase_data_name="bkm_custom_format_source",
        monitor_table_id=result_table.table_id,
        storage_type=models.ClusterInfo.TYPE_VM,
    )
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=result_table.table_id,
        data_type=models.AccessVMRecord.ACCESS_VM,
        storage_cluster_id=1,
        vm_cluster_id=1,
        bk_base_data_id=data_source.bk_data_id,
        bk_base_data_name="bkm_custom_format_source",
        vm_result_table_id="2_custom_format_metric",
    )
    delete_remote = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    result_table.delete_datalink()

    assert delete_remote.call_count == 5
    assert not models.DataLink.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not models.ResultTableConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not models.ChannelBindingConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not models.VMStorageBindingConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not models.DataBusConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert models.DataIdConfig.objects.filter(name="bkm_custom_format_source").exists()
    assert models.ResultTable.objects.filter(table_id=result_table.table_id).exists()
    assert not models.BkBaseResultTable.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not models.AccessVMRecord.objects.filter(result_table_id=result_table.table_id).exists()


def test_custom_format_datasource_cannot_switch_etl(custom_format_records):
    data_source, _, _ = custom_format_records

    with pytest.raises(ValueError, match="不能原地切换"):
        data_source.update_config(operator="system", etl_config="bk_standard_v2_time_series")


def test_custom_format_datasource_can_link_multiple_result_tables(mocker, custom_format_records):
    data_source, _, _ = custom_format_records
    mocker.patch.object(models.DataSource, "refresh_consul_config")

    models.DataSourceResultTable.modify_table_id_datasource(
        bk_tenant_id="system",
        table_id="custom_format.second_metric",
        bk_data_id=data_source.bk_data_id,
    )

    assert set(
        models.DataSourceResultTable.objects.filter(
            bk_tenant_id="system", bk_data_id=data_source.bk_data_id
        ).values_list("table_id", flat=True)
    ) == {"custom_format.metric", "custom_format.second_metric"}


def test_custom_format_influxdb_result_table_can_target_vm(mocker, custom_format_records):
    _, result_table, _ = custom_format_records
    result_table.default_storage = models.ClusterInfo.TYPE_INFLUXDB
    result_table.save(update_fields=["default_storage"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK,
        value=json.dumps(True),
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )
    apply_custom_format = mocker.patch("metadata.task.datalink.apply_custom_format_datalink")

    result_table.apply_datalink(delay=False)

    apply_custom_format.assert_called_once_with(bk_tenant_id="system", table_id=result_table.table_id)


def test_custom_format_influxdb_result_table_rejects_non_vm_target(custom_format_records):
    _, result_table, _ = custom_format_records
    result_table.default_storage = models.ClusterInfo.TYPE_INFLUXDB
    result_table.save(update_fields=["default_storage"])
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    option.value = json.dumps(
        {
            "target_storage_type": models.ClusterInfo.TYPE_ES,
            "clean_rules": _clean_rules(),
            "filter_rules": "True",
            "es_storage_config": {"unique_field_list": [], "json_field_list": [], "timezone": 0},
        }
    )
    option.save(update_fields=["value"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK,
        value=json.dumps(True),
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )

    with pytest.raises(ValueError, match="default_storage 必须与 target_storage_type 一致"):
        result_table.apply_datalink(delay=False)


def test_custom_format_time_series_group_uses_vm_and_preserves_fixed_tables(mocker, custom_format_records):
    data_source, result_table, _ = custom_format_records
    mocker.patch.object(
        models.TimeSeriesGroup,
        "pre_check",
        return_value={"time_series_group_name": "custom_format_auto"},
    )
    mocker.patch.object(models.TimeSeriesGroup, "update_metrics")
    mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay")
    refresh_consul = mocker.patch.object(models.DataSource, "refresh_consul_config")
    create_result_table = mocker.spy(models.ResultTable, "create_result_table")

    group = models.TimeSeriesGroup.create_time_series_group(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        bk_biz_id=result_table.bk_biz_id,
        table_id="custom_format.auto",
        time_series_group_name="custom_format_auto",
        label=result_table.label,
        operator="system",
        metric_info_list=[],
        additional_options={
            models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST: True,
            models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK: True,
            models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK: {
                "target_storage_type": models.ClusterInfo.TYPE_VM,
                "clean_rules": _clean_rules(),
                "filter_rules": "True",
            },
        },
        is_sync_db=False,
    )

    assert group.table_id == "custom_format.auto"
    assert create_result_table.call_args.kwargs["default_storage"] == models.ClusterInfo.TYPE_INFLUXDB
    assert create_result_table.call_args.kwargs["default_storage_config"] == {"use_default_rp": True}
    auto_result_table = models.ResultTable.objects.get(bk_tenant_id="system", table_id=group.table_id)
    assert auto_result_table.default_storage == models.ClusterInfo.TYPE_INFLUXDB
    assert models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=group.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST,
    ).get_value()
    assert set(
        models.DataSourceResultTable.objects.filter(
            bk_tenant_id="system",
            bk_data_id=data_source.bk_data_id,
        ).values_list("table_id", flat=True)
    ) == {result_table.table_id, group.table_id}
    refresh_consul.assert_not_called()


def test_standard_time_series_group_rejects_existing_result_table_without_deleting(mocker, custom_format_records):
    _, result_table, _ = custom_format_records
    data_source = models.DataSource.objects.create(
        bk_data_id=527766,
        data_name="standard_time_series_source",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
        is_custom_source=True,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    existing_result_table = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="standard.existing",
        table_name_zh="standard.existing",
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_INFLUXDB,
        creator="system",
        bk_biz_id=2,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=existing_result_table.table_id,
        creator="system",
    )
    mocker.patch.object(
        models.TimeSeriesGroup,
        "pre_check",
        return_value={"time_series_group_name": "standard_new"},
    )

    with pytest.raises(ValueError, match="已经关联结果表.*不能创建新的自定义组"):
        models.TimeSeriesGroup.create_time_series_group(
            bk_tenant_id="system",
            bk_data_id=data_source.bk_data_id,
            bk_biz_id=2,
            table_id="standard.new",
            time_series_group_name="standard_new",
            label=result_table.label,
            operator="system",
            is_sync_db=False,
        )

    assert models.DataSourceResultTable.objects.filter(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=existing_result_table.table_id,
    ).exists()
    assert not models.TimeSeriesGroup.objects.filter(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
    ).exists()


def test_standard_time_series_group_without_result_table_still_creates(mocker, custom_format_records):
    _, result_table, _ = custom_format_records
    data_source = models.DataSource.objects.create(
        bk_data_id=527767,
        data_name="standard_new_time_series_source",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
        is_custom_source=True,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    mocker.patch.object(
        models.TimeSeriesGroup,
        "pre_check",
        return_value={"time_series_group_name": "standard_new"},
    )
    mocker.patch.object(models.TimeSeriesGroup, "update_metrics")
    create_result_table = mocker.patch.object(models.ResultTable, "create_result_table")
    mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay")
    refresh_consul = mocker.patch.object(models.DataSource, "refresh_consul_config")

    group = models.TimeSeriesGroup.create_time_series_group(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        bk_biz_id=2,
        table_id="standard.new",
        time_series_group_name="standard_new",
        label=result_table.label,
        operator="system",
        is_sync_db=False,
    )

    assert group.table_id == "standard.new"
    create_result_table.assert_called_once()
    refresh_consul.assert_called_once()


def test_custom_format_time_series_group_rejects_non_vm_target(custom_format_records):
    data_source, result_table, _ = custom_format_records

    with pytest.raises(ValueError, match="仅支持 victoria_metrics"):
        models.TimeSeriesGroup.create_time_series_group(
            bk_tenant_id="system",
            bk_data_id=data_source.bk_data_id,
            bk_biz_id=result_table.bk_biz_id,
            table_id="custom_format.auto",
            time_series_group_name="custom_format_auto",
            label=result_table.label,
            operator="system",
            additional_options={
                models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK: True,
                models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK: {
                    "target_storage_type": models.ClusterInfo.TYPE_ES,
                    "clean_rules": _clean_rules(),
                    "filter_rules": "True",
                    "es_storage_config": {
                        "unique_field_list": [],
                        "json_field_list": [],
                        "timezone": 0,
                    },
                },
            },
        )


def test_delete_custom_format_time_series_group_keeps_fixed_result_table(mocker, custom_format_records):
    data_source, fixed_result_table, _ = custom_format_records
    auto_result_table = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="custom_format.auto",
        table_name_zh="custom_format.auto",
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_VM,
        creator="system",
        bk_biz_id=2,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=auto_result_table.table_id,
        creator="system",
    )
    group = models.TimeSeriesGroup.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        bk_biz_id=2,
        table_id=auto_result_table.table_id,
        time_series_group_name="custom_format_auto",
        label=auto_result_table.label,
        token="auto-token",
        is_split_measurement=True,
        creator="system",
        last_modify_user="system",
    )
    modify_result_table = mocker.patch.object(models.ResultTable, "modify")

    group.delete_time_series_group("system")

    assert modify_result_table.call_count == 1
    assert modify_result_table.call_args.kwargs == {"operator": "system", "is_enable": False}
    assert models.ResultTable.objects.filter(
        bk_tenant_id="system",
        table_id=auto_result_table.table_id,
        is_enable=False,
        is_deleted=True,
    ).exists()
    assert models.ResultTable.objects.filter(
        bk_tenant_id="system",
        table_id=fixed_result_table.table_id,
        is_enable=True,
        is_deleted=False,
    ).exists()
    assert models.DataSourceResultTable.objects.filter(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=fixed_result_table.table_id,
    ).exists()


def test_custom_format_result_table_cannot_switch_datasource(custom_format_records):
    _, result_table, _ = custom_format_records
    other = models.DataSource.objects.create(
        bk_data_id=527799,
        data_name="other_custom_format_source",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_custom_format",
        is_custom_source=True,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )

    with pytest.raises(ValueError, match="不能切换关联 DataSource"):
        models.DataSourceResultTable.modify_table_id_datasource(
            bk_tenant_id="system",
            table_id=result_table.table_id,
            bk_data_id=other.bk_data_id,
        )


def test_custom_format_apply_failure_records_component_error(mocker, custom_format_records):
    data_source, result_table, _ = custom_format_records
    result_table.default_storage = models.ClusterInfo.TYPE_ES
    result_table.save(update_fields=["default_storage"])
    es_cluster = models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=527766,
        cluster_name="custom-es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.example.com",
        port=9200,
        description="",
        is_default_cluster=False,
    )
    models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        storage_cluster_id=es_cluster.cluster_id,
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="bkm_custom_format_source",
        bk_biz_id=2,
        bk_data_id=data_source.bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    option.value = json.dumps(
        {
            "target_storage_type": models.ClusterInfo.TYPE_ES,
            "clean_rules": _clean_rules(),
            "filter_rules": "True",
            "es_storage_config": {"unique_field_list": [], "json_field_list": [], "timezone": 0},
        }
    )
    option.save(update_fields=["value"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK,
        value=json.dumps(True),
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )
    mocker.patch.object(DataLink, "apply_data_link", side_effect=ValueError("ElasticSearchBinding apply failed"))

    with pytest.raises(ValueError, match="ElasticSearchBinding apply failed"):
        apply_custom_format_datalink(bk_tenant_id="system", table_id=result_table.table_id)

    record = models.BkBaseResultTable.objects.get(
        data_link_name=compose_custom_format_data_link_name("system", data_source.bk_data_id, result_table.table_id)
    )
    assert record.status == DataLinkResourceStatus.FAILED.value


def test_custom_format_missing_storage_keeps_failed_expected_state(custom_format_records):
    data_source, result_table, _ = custom_format_records
    result_table.default_storage = models.ClusterInfo.TYPE_ES
    result_table.save(update_fields=["default_storage"])
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="bkm_custom_format_source",
        bk_biz_id=2,
        bk_data_id=data_source.bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK,
    )
    option.value = json.dumps(
        {
            "target_storage_type": models.ClusterInfo.TYPE_ES,
            "clean_rules": _clean_rules(),
            "filter_rules": "True",
            "es_storage_config": {"unique_field_list": [], "json_field_list": [], "timezone": 0},
        }
    )
    option.save(update_fields=["value"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=result_table.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_CUSTOM_FORMAT_V4_DATA_LINK,
        value=json.dumps(True),
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )

    with pytest.raises(ValueError, match="缺少 ESStorage"):
        apply_custom_format_datalink(bk_tenant_id="system", table_id=result_table.table_id)

    data_link_name = compose_custom_format_data_link_name("system", data_source.bk_data_id, result_table.table_id)
    assert models.DataLink.objects.filter(data_link_name=data_link_name).exists()
    record = models.BkBaseResultTable.objects.get(data_link_name=data_link_name)
    assert record.status == DataLinkResourceStatus.FAILED.value
