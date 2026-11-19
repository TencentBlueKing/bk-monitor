import json

import pytest

from constants.common import DEFAULT_TENANT_ID
from metadata import models
from metadata.models.constants import BASE_EVENT_RESULT_TABLE_FIELD_MAP, DataIdCreatedFromSystem
from metadata.models.space.constants import EtlConfigs
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.task import tenant
from metadata.task.tasks import (
    create_base_event_datalink_for_bkcc,
    create_single_tenant_system_datalink,
    create_single_tenant_system_event_datalink,
    create_single_tenant_system_proc_datalink,
)

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
        cluster_name="default_kafka",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="kafka.test",
        port=9092,
        is_default_cluster=True,
    )
    datasource = models.DataSource.objects.create(
        bk_data_id=1000,
        bk_tenant_id=DEFAULT_TENANT_ID,
        data_name="gse_system_event",
        etl_config=EtlConfigs.BK_GSE_SYSTEM_EVENT.value,
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
    assert data_id["spec"]["predefined"]["channel"]["name"] == "default_kafka"
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


def test_system_event_applies_databus_before_stopping_transfer(system_event_records):
    _, _, _, apply_api, delete_consul, _ = system_event_records
    submitted_databus = []

    def apply_configs(*, config, bk_tenant_id):
        for resource in config:
            if resource["kind"] == "Databus":
                delete_consul.assert_not_called()
                submitted_databus.append(resource)
        return {}

    apply_api.side_effect = apply_configs

    create_single_tenant_system_event_datalink()

    assert len(submitted_databus) == 1
    delete_consul.assert_called_once_with()


def test_reapply_system_event_reuses_registered_data_id_and_components(system_event_records):
    _, _, _, apply_api, delete_consul, _ = system_event_records
    create_single_tenant_system_event_datalink()
    first_configs = apply_api.call_args.kwargs["config"]
    apply_api.reset_mock()
    delete_consul.reset_mock()

    create_single_tenant_system_event_datalink()

    apply_api.assert_called_once()
    assert apply_api.call_args.kwargs["config"] == first_configs
    delete_consul.assert_called_once_with()
    for model in (
        models.DataLink,
        models.DataIdConfig,
        models.ResultTableConfig,
        models.ESStorageBindingConfig,
        models.DataBusConfig,
    ):
        assert model.objects.count() == 1


@pytest.mark.parametrize("kafka_cluster_name", ["missing_kafka", ""])
def test_missing_kafka_keeps_legacy_system_event_source(system_event_records, kafka_cluster_name, caplog):
    datasource, kafka_cluster, _, apply_api, delete_consul, push_router = system_event_records
    if not kafka_cluster_name:
        kafka_cluster.is_default_cluster = False
        kafka_cluster.save(update_fields=["is_default_cluster"])

    create_single_tenant_system_event_datalink(kafka_cluster_name=kafka_cluster_name)

    assert "create_single_tenant_system_event_datalink: Kafka cluster" in caplog.text
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


@pytest.mark.parametrize(
    "failure_step", ["compose_configs", "merge_existing_component_configs", "apply_data_link_with_retry"]
)
def test_failed_v4_apply_keeps_transfer_until_retry_succeeds(system_event_records, mocker, failure_step):
    datasource, _, _, apply_api, delete_consul, push_router = system_event_records
    failed_step = mocker.patch.object(models.DataLink, failure_step, side_effect=RuntimeError("V4 apply failed"))

    with pytest.raises(RuntimeError, match="V4 apply failed"):
        create_single_tenant_system_event_datalink()

    datasource.refresh_from_db()
    assert datasource.created_from == DataIdCreatedFromSystem.BKDATA.value
    delete_consul.assert_not_called()
    push_router.assert_not_called()
    assert all(config["kind"] != "Databus" for call in apply_api.call_args_list for config in call.kwargs["config"])
    mocker.stop(failed_step)
    apply_api.reset_mock()

    create_single_tenant_system_event_datalink()

    apply_api.assert_called_once()
    assert any(config["kind"] == "Databus" for config in apply_api.call_args.kwargs["config"])
    delete_consul.assert_called_once_with()
    push_router.assert_called_once()
    assert models.DataIdConfig.objects.count() == 1
    assert models.DataLink.objects.filter(bk_data_id=datasource.bk_data_id).count() == 1


def test_failed_consul_cleanup_is_retried_after_v4_apply(system_event_records):
    datasource, _, _, apply_api, delete_consul, push_router = system_event_records
    delete_consul.side_effect = [RuntimeError("Consul cleanup failed"), None]

    with pytest.raises(RuntimeError, match="Consul cleanup failed"):
        create_single_tenant_system_event_datalink()

    datasource.refresh_from_db()
    assert datasource.created_from == DataIdCreatedFromSystem.BKDATA.value
    assert any(config["kind"] == "Databus" for config in apply_api.call_args.kwargs["config"])
    push_router.assert_not_called()
    apply_api.reset_mock()

    create_single_tenant_system_event_datalink()

    apply_api.assert_called_once()
    assert any(config["kind"] == "Databus" for config in apply_api.call_args.kwargs["config"])
    assert delete_consul.call_count == 2
    push_router.assert_called_once()
    assert models.DataIdConfig.objects.count() == 1
    assert models.DataLink.objects.filter(bk_data_id=datasource.bk_data_id).count() == 1


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


@pytest.mark.parametrize(
    "create_datalink, data_ids",
    [
        (create_single_tenant_system_datalink, [1001]),
        (create_single_tenant_system_event_datalink, [1000]),
        (create_single_tenant_system_proc_datalink, [1007, 1013]),
    ],
    ids=["basereport", "system_event", "system_proc"],
)
@pytest.mark.parametrize(
    "kafka_kwargs",
    [{}, {"kafka_cluster_name": ""}, {"kafka_cluster_name": "selected_kafka"}],
    ids=["omitted", "empty", "named"],
)
def test_single_tenant_builtin_links_select_kafka(
    system_event_records, settings, mocker, create_datalink, data_ids, kafka_kwargs
):
    _, default_kafka, _, apply_api, _, _ = system_event_records
    settings.SNAPSHOT_DATAID = 1001
    settings.PROCESS_PERF_DATAID = 1007
    settings.PROCESS_PORT_DATAID = 1013
    selected_kafka = models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_name="selected_kafka",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="selected.test",
        port=9092,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        bk_tenant_id="other_tenant",
        cluster_name="selected_kafka",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="other.test",
        port=9092,
        is_default_cluster=True,
    )
    models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_name="default_vm",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.test",
        port=80,
        is_default_cluster=True,
    )
    etl_configs = {
        1001: EtlConfigs.BK_SYSTEM_BASEREPORT.value,
        1007: EtlConfigs.BK_SYSTEM_PROC.value,
        1013: EtlConfigs.BK_SYSTEM_PROC_PORT.value,
    }
    for data_id in data_ids:
        if data_id == 1000:
            continue
        models.DataSource.objects.create(
            bk_data_id=data_id,
            bk_tenant_id=DEFAULT_TENANT_ID,
            data_name=f"builtin_{data_id}",
            etl_config=etl_configs[data_id],
            mq_cluster_id=0,
            mq_config_id=0,
            is_custom_source=False,
        )
        models.KafkaTopicInfo.objects.create(bk_data_id=data_id, topic=f"builtin_{data_id}", partition=1)
    mocker.patch("metadata.task.tasks.BASEREPORT_USAGES", ["cpu_summary"])
    mocker.patch.object(models.DataLink, "apply_data_link")

    create_datalink(**kafka_kwargs)

    expected_kafka = selected_kafka if kafka_kwargs.get("kafka_cluster_name") else default_kafka
    for data_id in data_ids:
        datasource = models.DataSource.objects.get(bk_data_id=data_id)
        assert datasource.created_from == DataIdCreatedFromSystem.BKDATA.value
        assert datasource.mq_cluster_id == expected_kafka.cluster_id
    data_id_configs = [
        config for call in apply_api.call_args_list for config in call.kwargs["config"] if config["kind"] == "DataId"
    ]
    assert {config["spec"]["predefined"]["dataId"] for config in data_id_configs} == set(data_ids)
    assert all(
        config["spec"]["predefined"]["channel"]["name"] == expected_kafka.cluster_name for config in data_id_configs
    )


@pytest.fixture
def system_event_doris_cluster():
    return models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_name="system_event_doris",
        cluster_type="doris",
        domain_name="doris.test",
        port=9030,
        is_default_cluster=True,
    )


def test_system_event_doris_switch_and_retry(system_event_records, system_event_doris_cluster, mocker):
    _, _, es, apply_api, cleanup, publish = system_event_records
    create_single_tenant_system_event_datalink()
    cleanup.reset_mock()
    publish.reset_mock()
    fail = mocker.patch.object(models.DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("apply failed"))
    with pytest.raises(RuntimeError, match="apply failed"):
        create_single_tenant_system_event_datalink(storage_type="doris")
    assert models.ResultTable.objects.get(table_id=es.table_id).default_storage == "elasticsearch"
    assert not models.StorageClusterRecord.objects.filter(table_id=es.table_id).exists()
    cleanup.assert_not_called()
    publish.assert_not_called()
    mocker.stop(fail)

    for _ in range(2):
        create_single_tenant_system_event_datalink(storage_type="doris")
    configs = {v["kind"]: v for v in apply_api.call_args.kwargs["config"]}
    assert set(configs) == {"ResultTable", "DorisBinding", "Databus"}
    binding = configs["DorisBinding"]["spec"]
    assert binding["storage"]["name"] == system_event_doris_cluster.cluster_name
    assert binding["storage_config"]["json_fields"] == ["event", "dimensions"]
    bus = configs["Databus"]["spec"]
    assert bus["sinks"] == [{"kind": "DorisBinding", "name": "base_2_agent_event", "namespace": "bklog"}]
    assert bus["transforms"] == [{"kind": "PreDefinedLogic", "name": "gse_system_event"}]
    assert models.ESStorageBindingConfig.objects.filter(table_id=es.table_id).exists()
    assert models.DorisStorageBindingConfig.objects.filter(table_id=es.table_id).count() == 1
    routes, _ = SpaceTableIDRedis()._compose_log_table_id_detail(
        bk_tenant_id=DEFAULT_TENANT_ID, table_id_list=[es.table_id]
    )
    route = routes[es.table_id]
    assert route["db"] == "2_base_2_agent_event"
    assert route["data_label"] == "system_event"
    assert [(s["storage_id"], s["db"]) for s in route["storage_cluster_records"]] == [
        (system_event_doris_cluster.cluster_id, route["db"]),
        (es.storage_cluster_id, es.index_set),
    ]
    create_single_tenant_system_event_datalink()
    assert models.ResultTable.objects.get(table_id=es.table_id).default_storage == "elasticsearch"
    assert (
        models.StorageClusterRecord.objects.get(table_id=es.table_id, is_current=True).cluster_id
        == es.storage_cluster_id
    )


def test_multi_tenant_system_event_doris(system_event_records, system_event_doris_cluster, settings, mocker):
    ds, _, _, apply_api, _, publish = system_event_records
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.SPACE_BUILTIN_DATA_LINK_MODE = "biz"
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    ds.data_name = "base_42_agent_event"
    ds.save(update_fields=["data_name"])
    create_base_event_datalink_for_bkcc("system", 42, system_event_doris_cluster.cluster_name, storage_type="doris")
    table_id = "base_system_42_event"
    rt = models.ResultTable.objects.get(table_id=table_id)
    assert rt.default_storage == "doris"
    assert rt.get_storage("doris").bkbase_table_id
    assert not models.ESStorage.objects.filter(table_id=table_id).exists()
    assert models.StorageClusterRecord.objects.filter(table_id=table_id).count() == 1
    configs = {v["kind"]: v for v in apply_api.call_args.kwargs["config"]}
    assert configs["Databus"]["spec"]["sinks"] == [
        {"kind": "DorisBinding", "namespace": "bklog", "tenant": "system", "name": "base_42_agent_event"}
    ]
    publish.assert_called_once_with(bk_tenant_id="system", table_id_list=[table_id], is_publish=True)
