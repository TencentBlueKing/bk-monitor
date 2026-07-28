import json

import pydantic
import pytest

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.component_reuse import ExistingComponentContext
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.result_table import GraphRelationV4DataLinkOption

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.mark.parametrize(
    ("raw_targets", "expected_targets"),
    [
        (["vm"], ["vm"]),
        (["surrealdb"], ["surrealdb"]),
        (["surrealdb", "vm"], ["vm", "surrealdb"]),
    ],
)
def test_graph_relation_v4_option_normalizes_targets(raw_targets, expected_targets):
    option = GraphRelationV4DataLinkOption(write_targets=raw_targets)

    assert option.write_targets == expected_targets


@pytest.mark.parametrize("write_targets", [[], ["vm", "vm"], ["unknown"], "vm"])
def test_graph_relation_v4_option_rejects_invalid_targets(write_targets):
    with pytest.raises(pydantic.ValidationError):
        GraphRelationV4DataLinkOption(write_targets=write_targets)


@pytest.fixture
def graph_relation_v4_records():
    table_id = "graph_relation_v4.metric.__default__"
    data_source = models.DataSource.objects.create(
        bk_data_id=65001,
        data_name="graph_relation_v4_metric",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    result_table = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_INFLUXDB,
        creator="system",
        bk_biz_id=2,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        creator="system",
    )
    vm_cluster = models.ClusterInfo.objects.create(
        cluster_id=165001,
        cluster_name="graph-v4-vm",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
        port=80,
        username="admin",
        password="password",
        is_default_cluster=True,
        bk_tenant_id="system",
    )
    surrealdb_cluster = models.ClusterInfo.objects.create(
        cluster_id=165002,
        cluster_name="graph-v4-surrealdb",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surrealdb.example.com",
        port=80,
        username="admin",
        password="password",
        is_default_cluster=True,
        bk_tenant_id="system",
    )
    models.SurrealDBStorage.objects.create(
        table_id=table_id,
        bk_tenant_id="system",
        storage_cluster_id=surrealdb_cluster.cluster_id,
        table_type="temporary",
        vertices=[{"name": "pod", "id_fields": ["pod_uid"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_graph_relation_v4_metric",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    return {
        "table_id": table_id,
        "data_source": data_source,
        "result_table": result_table,
        "vm_cluster": vm_cluster,
        "data_link": data_link,
    }


def test_graph_relation_strategy_only_dispatches_v4_compose(mocker, graph_relation_v4_records):
    ctx = graph_relation_v4_records
    v4_compose = mocker.patch.object(
        ctx["data_link"],
        "compose_graph_relation_v4_time_series_configs",
        return_value=[],
    )

    ctx["data_link"].compose_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
    )

    v4_compose.assert_called_once()
    assert ctx["data_link"].data_link_strategy == DataLink.GRAPH_RELATION_TIME_SERIES
    assert not hasattr(DataLink, "GRAPH_RELATION_V4_TIME_SERIES")


def test_graph_relation_apply_rejects_legacy_entry_without_option(graph_relation_v4_records):
    ctx = graph_relation_v4_records

    with pytest.raises(ValueError, match="legacy graph relation entry is disabled"):
        ctx["data_link"].apply_data_link(
            bk_biz_id=2,
            data_source=ctx["data_source"],
            table_id=ctx["table_id"],
            storage_cluster_name=ctx["vm_cluster"].cluster_name,
        )

    assert not models.BkBaseResultTable.objects.filter(
        bk_tenant_id="system",
        data_link_name=ctx["data_link"].data_link_name,
    ).exists()


@pytest.mark.parametrize(
    ("write_targets", "expected_kinds"),
    [
        (["vm"], ["ResultTable", "VmStorageBinding", "Databus"]),
        (["surrealdb"], ["ResultTable", "SurrealDBBinding", "Databus"]),
        (
            ["vm", "surrealdb"],
            ["ResultTable", "VmStorageBinding", "Databus", "ResultTable", "SurrealDBBinding", "Databus"],
        ),
    ],
)
def test_compose_graph_relation_v4_uses_ordinary_components(
    graph_relation_v4_records,
    write_targets,
    expected_kinds,
):
    ctx = graph_relation_v4_records
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": write_targets}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    expected_component_classes = [ResultTableConfig]
    if "vm" in write_targets:
        expected_component_classes.append(VMStorageBindingConfig)
    if "surrealdb" in write_targets:
        expected_component_classes.append(SurrealDBBindingConfig)
    expected_component_classes.append(DataBusConfig)

    configs = ctx["data_link"].compose_graph_relation_v4_time_series_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name if "vm" in write_targets else "",
        existing_context=ExistingComponentContext.from_datalink(ctx["data_link"]),
    )

    assert ctx["data_link"].get_related_component_classes() == expected_component_classes
    assert [config["kind"] for config in configs] == expected_kinds
    assert all("bkm_data_link_strategy" not in config["metadata"]["labels"] for config in configs)
    if "surrealdb" in write_targets:
        graph_databus = next(
            config
            for config in configs
            if config["kind"] == "Databus" and config["spec"]["sinks"][0]["kind"] == "SurrealDBBinding"
        )
        assert graph_databus["spec"]["transforms"] == []
        assert "autoOffsetReset" not in graph_databus["spec"]


def test_graph_relation_v4_transfer_consumer_group_only_applies_to_vm(graph_relation_v4_records):
    ctx = graph_relation_v4_records
    transfer_consumer_group = "bkmonitorv3_transfer_graph_relation_v4"
    graph_databus_name = ctx["data_link"].compose_surrealdb_table_name(ctx["table_id"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["vm", "surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    DataBusConfig.objects.create(
        name=graph_databus_name,
        data_id_name="bkm_graph_relation_v4_metric",
        data_link_name=ctx["data_link"].data_link_name,
        namespace=ctx["data_link"].namespace,
        bk_biz_id=2,
        bk_tenant_id="system",
        bk_data_id=ctx["data_source"].bk_data_id,
        sink_names=[f"SurrealDBBinding:{graph_databus_name}"],
        consumer_group=transfer_consumer_group,
    )

    configs = ctx["data_link"].compose_graph_relation_v4_time_series_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name,
        existing_context=ExistingComponentContext.from_datalink(ctx["data_link"]),
        consumer_group=transfer_consumer_group,
    )

    vm_databus = next(
        config
        for config in configs
        if config["kind"] == "Databus" and config["spec"]["sinks"][0]["kind"] == "VmStorageBinding"
    )
    graph_databus = next(
        config
        for config in configs
        if config["kind"] == "Databus" and config["spec"]["sinks"][0]["kind"] == "SurrealDBBinding"
    )
    assert vm_databus["spec"]["consumerGroup"] == transfer_consumer_group
    assert "consumerGroup" not in graph_databus["spec"]
    assert (
        DataBusConfig.objects.get(
            bk_tenant_id="system",
            namespace=ctx["data_link"].namespace,
            name=vm_databus["metadata"]["name"],
        ).consumer_group
        == transfer_consumer_group
    )
    assert (
        DataBusConfig.objects.get(
            bk_tenant_id="system",
            namespace=ctx["data_link"].namespace,
            name=graph_databus["metadata"]["name"],
        ).consumer_group
        == ""
    )


def test_apply_graph_relation_v4_deletes_components_absent_from_compose(mocker, graph_relation_v4_records):
    ctx = graph_relation_v4_records
    option_record = models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["vm", "surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    ctx["data_link"].compose_graph_relation_v4_time_series_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name,
        existing_context=ExistingComponentContext.from_datalink(ctx["data_link"]),
    )
    option_record.value = json.dumps({"write_targets": ["vm"]})
    option_record.save(update_fields=["value"])

    mocker.patch.object(DataLink, "merge_existing_component_configs", side_effect=lambda configs: configs)
    mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    ctx["data_link"].apply_data_link(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name,
    )

    assert mock_delete.call_count == 3
    assert ResultTableConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        data_type="metric",
    ).exists()
    assert VMStorageBindingConfig.objects.filter(data_link_name=ctx["data_link"].data_link_name).exists()
    assert DataBusConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        sink_names__icontains="VmStorageBinding:",
    ).exists()
    assert not ResultTableConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        data_type="graph",
    ).exists()
    assert not SurrealDBBindingConfig.objects.filter(data_link_name=ctx["data_link"].data_link_name).exists()
    assert not DataBusConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        sink_names__icontains="SurrealDBBinding:",
    ).exists()
    assert (
        models.BkBaseResultTable.objects.get(
            bk_tenant_id="system",
            data_link_name=ctx["data_link"].data_link_name,
        ).storage_type
        == models.ClusterInfo.TYPE_VM
    )


def test_switch_from_surrealdb_only_to_standard_vm_reuses_datalink_and_cleans_graph(
    mocker,
    graph_relation_v4_records,
):
    ctx = graph_relation_v4_records
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    ctx["data_link"].compose_graph_relation_v4_time_series_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        existing_context=ExistingComponentContext.from_datalink(ctx["data_link"]),
    )
    ctx["data_link"].data_link_strategy = DataLink.BK_STANDARD_V2_TIME_SERIES
    ctx["data_link"].save(update_fields=["data_link_strategy"])

    mocker.patch.object(DataLink, "merge_existing_component_configs", side_effect=lambda configs: configs)
    mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    ctx["data_link"].apply_data_link(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name,
        cleanup_absent_components=True,
    )

    assert mock_delete.call_count == 3
    assert ResultTableConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        data_type="metric",
    ).exists()
    assert VMStorageBindingConfig.objects.filter(data_link_name=ctx["data_link"].data_link_name).exists()
    assert not SurrealDBBindingConfig.objects.filter(data_link_name=ctx["data_link"].data_link_name).exists()
    assert not ResultTableConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        data_type="graph",
    ).exists()


def test_apply_graph_relation_v4_failure_does_not_delete_old_components(mocker, graph_relation_v4_records):
    ctx = graph_relation_v4_records
    option_record = models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["vm", "surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    ctx["data_link"].compose_graph_relation_v4_time_series_configs(
        bk_biz_id=2,
        data_source=ctx["data_source"],
        table_id=ctx["table_id"],
        storage_cluster_name=ctx["vm_cluster"].cluster_name,
        existing_context=ExistingComponentContext.from_datalink(ctx["data_link"]),
    )
    option_record.value = json.dumps({"write_targets": ["vm"]})
    option_record.save(update_fields=["value"])

    mocker.patch.object(DataLink, "merge_existing_component_configs", side_effect=lambda configs: configs)
    mocker.patch.object(DataLink, "apply_data_link_with_retry", side_effect=ValueError("apply failed"))
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    with pytest.raises(ValueError, match="apply failed"):
        ctx["data_link"].apply_data_link(
            bk_biz_id=2,
            data_source=ctx["data_source"],
            table_id=ctx["table_id"],
            storage_cluster_name=ctx["vm_cluster"].cluster_name,
        )

    mock_delete.assert_not_called()
    assert SurrealDBBindingConfig.objects.filter(data_link_name=ctx["data_link"].data_link_name).exists()
    assert ResultTableConfig.objects.filter(
        data_link_name=ctx["data_link"].data_link_name,
        data_type="graph",
    ).exists()


def test_result_table_apply_datalink_dispatches_only_graph_v4_task(
    mocker,
    settings,
    graph_relation_v4_records,
):
    ctx = graph_relation_v4_records
    settings.ENABLE_INFLUXDB_STORAGE = False
    ctx["result_table"].default_storage = models.ClusterInfo.TYPE_ES
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    mock_graph_apply = mocker.patch("metadata.task.datalink.apply_graph_relation_v4_datalink")
    mock_vm_apply = mocker.patch("metadata.task.tasks.access_bkdata_vm")

    ctx["result_table"].apply_datalink()

    mock_graph_apply.assert_called_once_with(bk_tenant_id="system", table_id=ctx["table_id"])
    mock_vm_apply.assert_not_called()


def test_removing_graph_option_follows_standard_metric_datalink_rules(
    mocker,
    settings,
    graph_relation_v4_records,
):
    ctx = graph_relation_v4_records
    settings.ENABLE_INFLUXDB_STORAGE = True
    settings.ENABLE_V2_VM_DATA_LINK = False
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=ctx["data_link"].data_link_name,
        bkbase_data_name="bkm_graph_relation_v4_metric",
        monitor_table_id=ctx["table_id"],
        storage_type=models.ClusterInfo.TYPE_SURREALDB,
    )
    mock_graph_apply = mocker.patch("metadata.task.datalink.apply_graph_relation_v4_datalink")
    mock_vm_apply = mocker.patch("metadata.task.tasks.access_bkdata_vm")

    ctx["result_table"].apply_datalink(delay=False, force_update=True)

    mock_graph_apply.assert_not_called()
    mock_vm_apply.assert_not_called()


def test_apply_graph_relation_v4_surrealdb_only_does_not_create_vm_record(
    mocker,
    graph_relation_v4_records,
):
    from metadata.task.datalink import apply_graph_relation_v4_datalink

    ctx = graph_relation_v4_records
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="bkm_graph_relation_v4_metric",
        bk_biz_id=2,
        bk_data_id=ctx["data_source"].bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")
    mock_sync = mocker.patch.object(DataLink, "sync_metadata")

    apply_graph_relation_v4_datalink(bk_tenant_id="system", table_id=ctx["table_id"])

    data_link = DataLink.objects.get(data_link_name="bkm_graph_relation_v4_metric")
    assert data_link.data_link_strategy == DataLink.GRAPH_RELATION_TIME_SERIES
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["storage_type"] == models.ClusterInfo.TYPE_SURREALDB
    assert mock_apply.call_args.kwargs["storage_cluster_name"] == ""
    mock_sync.assert_called_once_with(
        table_id=ctx["table_id"],
        storage_cluster_id=165002,
    )
    assert not models.AccessVMRecord.objects.filter(
        bk_tenant_id="system",
        result_table_id=ctx["table_id"],
    ).exists()


def test_apply_graph_relation_v4_surrealdb_only_preserves_existing_vm_record(
    mocker,
    graph_relation_v4_records,
):
    from metadata.task.datalink import apply_graph_relation_v4_datalink

    ctx = graph_relation_v4_records
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="bkm_graph_relation_v4_metric",
        bk_biz_id=2,
        bk_data_id=ctx["data_source"].bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    vm_record = models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=ctx["table_id"],
        storage_cluster_id=165001,
        vm_cluster_id=165001,
        bk_base_data_id=75001,
        bk_base_data_name="legacy_graph_relation_data",
        vm_result_table_id="2_legacy_graph_relation_vm_rt",
        remark="preserve vm branch identity",
    )
    original_vm_identity = {
        "storage_cluster_id": vm_record.storage_cluster_id,
        "vm_cluster_id": vm_record.vm_cluster_id,
        "bk_base_data_id": vm_record.bk_base_data_id,
        "bk_base_data_name": vm_record.bk_base_data_name,
        "vm_result_table_id": vm_record.vm_result_table_id,
        "remark": vm_record.remark,
    }
    mocker.patch.object(DataLink, "apply_data_link")
    mocker.patch.object(DataLink, "sync_metadata")

    apply_graph_relation_v4_datalink(bk_tenant_id="system", table_id=ctx["table_id"])

    assert (
        models.AccessVMRecord.objects.filter(pk=vm_record.pk).values(*original_vm_identity).get()
        == original_vm_identity
    )


def test_apply_graph_relation_v4_reuses_existing_graph_datalink(mocker, graph_relation_v4_records):
    from metadata.task.datalink import apply_graph_relation_v4_datalink

    ctx = graph_relation_v4_records
    legacy_data_link_name = "legacy_graph_relation_datalink"
    legacy_data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=legacy_data_link_name,
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=ctx["data_source"].bk_data_id,
        table_ids=[ctx["table_id"]],
    )
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=legacy_data_link_name,
        bkbase_data_name="legacy_graph_relation_data",
        monitor_table_id=ctx["table_id"],
        storage_type=models.ClusterInfo.TYPE_SURREALDB,
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=ctx["table_id"],
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value=json.dumps({"write_targets": ["surrealdb"]}),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    models.DataIdConfig.objects.create(
        bk_tenant_id="system",
        namespace="bkmonitor",
        name="bkm_graph_relation_v4_metric",
        bk_biz_id=2,
        bk_data_id=ctx["data_source"].bk_data_id,
        status=DataLinkResourceStatus.OK.value,
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link", autospec=True)
    mock_sync = mocker.patch.object(DataLink, "sync_metadata", autospec=True)

    apply_graph_relation_v4_datalink(bk_tenant_id="system", table_id=ctx["table_id"])

    assert mock_apply.call_args.args[0].data_link_name == legacy_data_link_name
    assert mock_sync.call_args.args[0].data_link_name == legacy_data_link_name
    legacy_data_link.refresh_from_db()
    assert legacy_data_link.data_link_strategy == DataLink.GRAPH_RELATION_TIME_SERIES
    assert legacy_data_link.table_ids == [ctx["table_id"]]
