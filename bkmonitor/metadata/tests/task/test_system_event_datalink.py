import json

import pytest

from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.constants import BASE_EVENT_RESULT_TABLE_FIELD_MAP, DataIdCreatedFromSystem
from metadata.task import tenant
from metadata.task.tasks import create_single_tenant_system_event_datalink

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def system_event_records(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.DEFAULT_BKDATA_BIZ_ID = 2
    settings.BK_DATA_PROJECT_MAINTAINER = "admin"
    es_cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_name="system_event_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.test",
        port=9200,
        is_default_cluster=False,
    )
    kafka_cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_name="kafka_outer_default",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="kafka.test",
        port=9092,
        is_default_cluster=False,
    )
    datasource = models.DataSource.objects.create(
        bk_data_id=1000,
        bk_tenant_id=DEFAULT_TENANT_ID,
        data_name="gse_system_event",
        etl_config="bk_gse_system_event",
        source_label="bk_monitor",
        type_label="event",
        is_platform_data_id=True,
        is_custom_source=False,
        mq_cluster_id=0,
        mq_config_id=0,
        created_from=DataIdCreatedFromSystem.BKGSE.value,
    )
    models.KafkaTopicInfo.objects.create(bk_data_id=1000, topic="system_event_1000", partition=1)
    models.ResultTable.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id="gse_system_event",
        table_name_zh="系统事件",
        default_storage=models.ClusterInfo.TYPE_ES,
        is_custom_table=True,
        schema_type="free",
        bk_biz_id=0,
        data_label="system_event",
        creator="system",
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID, bk_data_id=1000, table_id="gse_system_event"
    )
    models.ResultTableField.objects.bulk_create(
        models.ResultTableField(bk_tenant_id=DEFAULT_TENANT_ID, table_id="gse_system_event", **field)
        for field in BASE_EVENT_RESULT_TABLE_FIELD_MAP["base_event"]
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id="gse_system_event",
        name="es_unique_field_list",
        value=json.dumps(["event_name", "target", "time"]),
        value_type="list",
    )
    es_storage = models.ESStorage.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id="gse_system_event",
        storage_cluster_id=es_cluster.cluster_id,
        index_set="gse_system_event",
    )
    apply_api = mocker.patch("metadata.task.tasks.api.bkdata.apply_data_link", return_value={})
    mocker.patch.object(models.DataLink, "get_existing_component_config", return_value=None)
    delete_consul = mocker.patch.object(models.DataSource, "delete_consul_config")
    push_router = mocker.patch("metadata.task.tasks.SpaceTableIDRedis.push_table_id_detail")
    return datasource, kafka_cluster, es_storage, apply_api, delete_consul, push_router


@pytest.mark.parametrize("data_bk_biz_id, expected_biz_id", [(None, 2), (42, 42)])
def test_create_system_event_reuses_base_event_configs(system_event_records, data_bk_biz_id, expected_biz_id):
    datasource, kafka_cluster, es_storage, apply_api, delete_consul, push_router = system_event_records

    create_single_tenant_system_event_datalink(data_bk_biz_id=data_bk_biz_id)

    name = f"base_{expected_biz_id}_agent_event"
    datasource.refresh_from_db()
    assert datasource.bk_data_id == 1000
    assert datasource.created_from == DataIdCreatedFromSystem.BKDATA.value
    assert datasource.mq_cluster_id == kafka_cluster.cluster_id
    assert datasource.etl_config == "bk_gse_system_event"
    data_id = apply_api.call_args_list[0].kwargs["config"][0]
    assert data_id["metadata"]["name"] == name
    assert data_id["metadata"]["namespace"] == "bklog"
    assert data_id["spec"]["eventType"] == "log"
    assert data_id["spec"]["predefined"]["dataId"] == 1000
    assert data_id["spec"]["predefined"]["channel"]["name"] == "kafka_outer_default"
    assert data_id["spec"]["predefined"]["topic"] == "system_event_1000"
    configs = {config["kind"]: config for config in apply_api.call_args.kwargs["config"]}
    assert set(configs) == {"ResultTable", "ElasticSearchBinding", "Databus"}
    for config in configs.values():
        assert config["metadata"]["name"] == name
        assert config["metadata"]["namespace"] == "bklog"
        assert "tenant" not in config["metadata"]
    assert configs["ElasticSearchBinding"]["spec"]["storage"]["name"] == "system_event_es"
    assert configs["ElasticSearchBinding"]["spec"]["doc_type"] == "gse_system_event"
    assert configs["ElasticSearchBinding"]["spec"]["write_alias"]["TimeBased"]["format"] == (
        "write_%Y%m%d_gse_system_event"
    )
    assert configs["Databus"]["spec"]["sources"] == [{"kind": "DataId", "name": name, "namespace": "bklog"}]
    assert configs["Databus"]["spec"]["transforms"] == [{"kind": "PreDefinedLogic", "name": "gse_system_event"}]
    assert configs["Databus"]["spec"]["sinks"] == [{"kind": "ElasticSearchBinding", "name": name, "namespace": "bklog"}]
    es_storage.refresh_from_db()
    assert es_storage.storage_cluster_id != 0
    assert es_storage.index_set == "gse_system_event"
    assert models.ResultTable.objects.count() == 1
    assert models.DataLink.objects.get(bk_data_id=1000).table_ids == ["gse_system_event"]
    delete_consul.assert_called_once_with()
    push_router.assert_called_once_with(
        bk_tenant_id=DEFAULT_TENANT_ID, table_id_list=["gse_system_event"], is_publish=True
    )


def test_reapply_system_event_reuses_registered_data_id_and_components(system_event_records):
    _, _, _, apply_api, delete_consul, _ = system_event_records
    create_single_tenant_system_event_datalink()
    first_configs = apply_api.call_args.kwargs["config"]
    apply_api.reset_mock()
    delete_consul.reset_mock()

    create_single_tenant_system_event_datalink()

    apply_api.assert_called_once()
    assert apply_api.call_args.kwargs["config"] == first_configs
    delete_consul.assert_not_called()
    for model in (
        models.DataLink,
        models.DataIdConfig,
        models.ResultTableConfig,
        models.ESStorageBindingConfig,
        models.DataBusConfig,
    ):
        assert model.objects.count() == 1


def test_missing_kafka_keeps_legacy_system_event_source(system_event_records):
    datasource, _, _, apply_api, delete_consul, push_router = system_event_records

    with pytest.raises(models.ClusterInfo.DoesNotExist):
        create_single_tenant_system_event_datalink(kafka_cluster_name="missing_kafka")

    datasource.refresh_from_db()
    assert datasource.created_from == DataIdCreatedFromSystem.BKGSE.value
    assert datasource.mq_cluster_id == 0
    apply_api.assert_not_called()
    delete_consul.assert_not_called()
    push_router.assert_not_called()


def test_failed_registration_keeps_legacy_system_event_source(system_event_records):
    datasource, _, _, apply_api, delete_consul, _ = system_event_records
    apply_api.side_effect = RuntimeError("registration failed")

    with pytest.raises(RuntimeError, match="registration failed"):
        create_single_tenant_system_event_datalink()

    datasource.refresh_from_db()
    assert datasource.created_from == DataIdCreatedFromSystem.BKGSE.value
    assert datasource.mq_cluster_id == 0
    delete_consul.assert_not_called()


def test_system_event_creation_skips_multi_tenant_mode(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    get_source = mocker.patch.object(models.DataSource.objects, "get")

    create_single_tenant_system_event_datalink()

    get_source.assert_not_called()


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_init_tenant_creates_system_events_only_in_single_tenant_mode(settings, mocker, multi_tenant):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.INITIALIZED_TENANT_LIST = []
    for name in (
        "_init_kafka_cluster",
        "_init_es_cluster",
        "_init_bkbase_cluster",
        "sync_bkcc_space",
        "create_single_tenant_system_datalink",
        "create_single_tenant_system_proc_datalink",
    ):
        mocker.patch.object(tenant, name)
    create_event = mocker.patch.object(tenant, "create_single_tenant_system_event_datalink")

    tenant.init_tenant(DEFAULT_TENANT_ID)

    assert create_event.call_count == (0 if multi_tenant else 1)
