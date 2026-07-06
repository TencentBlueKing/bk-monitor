"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.data_link import DataLink
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    DataIdConfig,
    GraphDataBusConfig,
    GraphRelationBindingConfig,
    ResultTableConfig,
    SurrealDBBindingConfig,
    VMStorageBindingConfig,
)
from metadata.models.storage import StorageClusterRecord, SurrealDBStorage
from metadata.models.space.constants import EtlConfigs

pytestmark = pytest.mark.django_db(databases="__all__")


def create_graph_relation_data_source() -> models.DataSource:
    return models.DataSource.objects.create(
        bk_data_id=50001,
        data_name="2_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
        is_custom_source=False,
        space_uid="bkcc__2",
    )


def create_storage_clusters() -> None:
    models.ClusterInfo.objects.create(
        cluster_id=1001,
        cluster_name="vm-default",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
        port=80,
        username="admin",
        password="1234",
        is_default_cluster=True,
        is_ssl_verify=False,
        bk_tenant_id="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=2001,
        cluster_name="surreal-default",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surreal.example.com",
        port=80,
        username="admin",
        password="1234",
        is_default_cluster=True,
        is_ssl_verify=False,
        bk_tenant_id="system",
    )


def create_ok_vm_storage_binding(data_link: DataLink, table_id: str, name: str = "2_bkcc_built_in_time_series") -> None:
    VMStorageBindingConfig.objects.create(
        name=name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        vm_cluster_name="vm-default",
        table_id=table_id,
        bkbase_result_table_name=name,
        status=DataLinkResourceStatus.OK.value,
    )


def test_compose_standard_time_series_configs_only_vm(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_standard_test",
        namespace="bkmonitor",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )

    configs = data_link.compose_standard_time_series_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
    )

    kinds = [config["kind"] for config in configs]
    assert kinds.count("Databus") == 1
    assert "VmStorageBinding" in kinds
    assert "SurrealDBBinding" not in kinds


@pytest.mark.parametrize(
    ("write_mode", "expected_databus_count", "expected_vm", "expected_surrealdb"),
    [
        (GraphRelationBindingConfig.WRITE_MODE_VM, 1, True, False),
        (GraphRelationBindingConfig.WRITE_MODE_SURREALDB, 1, False, True),
        (GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB, 2, True, True),
    ],
)
def test_compose_graph_relation_time_series_configs_by_write_mode(
    mocker,
    write_mode,
    expected_databus_count,
    expected_vm,
    expected_surrealdb,
):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=f"bkm_relation_graph_test_{write_mode}",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )

    configs = data_link.compose_graph_relation_time_series_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
        write_mode=write_mode,
    )

    kinds = [config["kind"] for config in configs]
    assert kinds[0] == "DataId"
    assert kinds.count("Databus") == expected_databus_count
    assert ("VmStorageBinding" in kinds) is expected_vm
    assert ("SurrealDBBinding" in kinds) is expected_surrealdb

    data_id_name = "bkm_2_bkcc_built_in_time_series"
    source_data_id = configs[0]
    assert source_data_id["metadata"]["name"] == data_id_name
    assert source_data_id["spec"]["predefined"]["dataId"] == data_source.bk_data_id
    assert (
        DataIdConfig.objects.get(
            bk_tenant_id=data_link.bk_tenant_id,
            namespace=data_link.namespace,
            name=data_id_name,
        ).bk_data_id
        == data_source.bk_data_id
    )

    if expected_surrealdb:
        databus_names = [config["metadata"]["name"] for config in configs if config["kind"] == "Databus"]
        result_tables = [config for config in configs if config["kind"] == "ResultTable"]
        result_table_names = [config["metadata"]["name"] for config in result_tables]
        assert DataLink.compose_surrealdb_table_name(table_id) in databus_names
        assert DataLink.compose_surrealdb_table_name(table_id) in result_table_names
        graph_rt = next(
            config
            for config in result_tables
            if config["metadata"]["name"] == DataLink.compose_surrealdb_table_name(table_id)
        )
        assert graph_rt["spec"]["dataType"] == "graph"
        graph_binding = next(config for config in configs if config["kind"] == "SurrealDBBinding")
        assert graph_binding["metadata"]["labels"]["bkm_data_link_strategy"] == "graph_relation_time_series"


def test_get_related_component_classes_for_graph_relation():
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_lifecycle",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=50003,
        table_ids=["2_bkcc_built_in_time_series.__default__"],
    )

    component_names = [component.__name__ for component in data_link.get_related_component_classes()]
    assert "ResultTableConfig" in component_names
    assert "VMStorageBindingConfig" in component_names
    assert "SurrealDBBindingConfig" in component_names
    assert "GraphRelationBindingConfig" in component_names
    assert "DataBusConfig" in component_names


@pytest.mark.parametrize(
    ("write_mode", "expected_component_names"),
    [
        (
            GraphRelationBindingConfig.WRITE_MODE_VM,
            {"GraphRelationBindingConfig", "ResultTableConfig", "VMStorageBindingConfig", "DataBusConfig"},
        ),
        (
            GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
            {"GraphRelationBindingConfig", "ResultTableConfig", "SurrealDBBindingConfig", "GraphDataBusConfig"},
        ),
        (
            GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
            {
                "GraphRelationBindingConfig",
                "ResultTableConfig",
                "VMStorageBindingConfig",
                "SurrealDBBindingConfig",
                "DataBusConfig",
                "GraphDataBusConfig",
            },
        ),
    ],
)
def test_get_related_component_classes_for_graph_relation_by_write_mode(write_mode, expected_component_names):
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=f"bkm_relation_lifecycle_{write_mode}",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=50003,
        table_ids=["2_bkcc_built_in_time_series.__default__"],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        write_mode=write_mode,
    )

    component_names = {component.__name__ for component in data_link.get_related_component_classes()}
    assert component_names == expected_component_names


def test_delete_graph_relation_data_link_uses_binding_write_mode_and_component_names(mocker):
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_delete_surrealdb_only",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=50003,
        table_ids=["2_bkcc_built_in_time_series.__default__"],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        bkbase_result_table_name="bkm_vm_relation_rt",
        graph_result_table_name="bkm_graph_relation_rt",
    )
    ResultTableConfig.objects.create(
        name="bkm_vm_relation_rt",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    ResultTableConfig.objects.create(
        name="bkm_graph_relation_rt",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    VMStorageBindingConfig.objects.create(
        name="bkm_vm_relation_rt",
        vm_cluster_name="vm-default",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name="bkm_graph_relation_rt",
        surrealdb_cluster_name="surreal-default",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    for name in ("bkm_vm_relation_rt", "bkm_graph_relation_rt"):
        sink_kind = "SurrealDBBinding" if name == "bkm_graph_relation_rt" else "VmStorageBinding"
        DataBusConfig.objects.create(
            name=name,
            data_id_name="bkm_relation_data_id",
            bk_data_id=50003,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            sink_names=[f"{sink_kind}:{name}"],
            status=DataLinkResourceStatus.OK.value,
        )
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    data_link.delete_data_link()

    deleted_names = {call.kwargs["name"] for call in mock_delete.call_args_list}
    assert deleted_names == {"bkm_graph_relation_rt"}
    assert ResultTableConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert VMStorageBindingConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert DataBusConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert not DataLink.objects.filter(data_link_name=data_link.data_link_name).exists()


def test_delete_graph_relation_data_link_falls_back_when_binding_missing(mocker):
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_delete_missing_binding",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=50003,
        table_ids=["2_bkcc_built_in_time_series.__default__"],
    )
    for name, binding_class, sink_kind in (
        ("bkm_vm_relation_rt", VMStorageBindingConfig, "VmStorageBinding"),
        ("bkm_graph_relation_rt", SurrealDBBindingConfig, "SurrealDBBinding"),
    ):
        ResultTableConfig.objects.create(
            name=name,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            status=DataLinkResourceStatus.OK.value,
        )
        binding_class.objects.create(
            name=name,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            status=DataLinkResourceStatus.OK.value,
        )
        DataBusConfig.objects.create(
            name=name,
            data_id_name="bkm_relation_data_id",
            bk_data_id=50003,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            sink_names=[f"{sink_kind}:{name}"],
            status=DataLinkResourceStatus.OK.value,
        )
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    data_link.delete_data_link()

    deleted_names = {call.kwargs["name"] for call in mock_delete.call_args_list}
    assert deleted_names == {"bkm_vm_relation_rt", "bkm_graph_relation_rt"}
    assert not ResultTableConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not VMStorageBindingConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not SurrealDBBindingConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not DataBusConfig.objects.filter(data_link_name=data_link.data_link_name).exists()
    assert not DataLink.objects.filter(data_link_name=data_link.data_link_name).exists()


def test_transition_graph_relation_write_mode_deletes_disabled_surrealdb_side(mocker):
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_transition_to_vm",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=50003,
        table_ids=["2_bkcc_built_in_time_series.__default__"],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        table_id="2_bkcc_built_in_time_series.__default__",
        bkbase_result_table_name="bkm_vm_relation_rt",
        graph_result_table_name="bkm_graph_relation_rt",
    )
    for name in ("bkm_vm_relation_rt", "bkm_graph_relation_rt"):
        sink_kind = "SurrealDBBinding" if name == "bkm_graph_relation_rt" else "VmStorageBinding"
        ResultTableConfig.objects.create(
            name=name,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            status=DataLinkResourceStatus.OK.value,
        )
        DataBusConfig.objects.create(
            name=name,
            data_id_name="bkm_relation_data_id",
            bk_data_id=50003,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            sink_names=[f"{sink_kind}:{name}"],
            status=DataLinkResourceStatus.OK.value,
        )
    VMStorageBindingConfig.objects.create(
        name="bkm_vm_relation_rt",
        vm_cluster_name="vm-default",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name="bkm_graph_relation_rt",
        surrealdb_cluster_name="surreal-default",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBStorage.objects.create(
        table_id="2_bkcc_built_in_time_series.__default__",
        bk_tenant_id=data_link.bk_tenant_id,
        table_type="temporary",
        vertices=[{"name": "pod", "id_fields": ["pod_uid"]}],
        relations=[],
        storage_cluster_id=2001,
    )
    StorageClusterRecord.objects.create(
        table_id="2_bkcc_built_in_time_series.__default__",
        bk_tenant_id=data_link.bk_tenant_id,
        cluster_id=2001,
        is_current=True,
        creator="system",
    )
    StorageClusterRecord.objects.create(
        table_id="2_bkcc_built_in_time_series.__default__",
        bk_tenant_id=data_link.bk_tenant_id,
        cluster_id=1001,
        is_current=True,
        creator="system",
    )
    mocker.patch("metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))
    mock_delete = mocker.patch("metadata.models.data_link.data_link_configs.api.bkdata.delete_data_link")

    configs = data_link.compose_graph_relation_time_series_configs(
        bk_biz_id=2,
        data_source=create_graph_relation_data_source(),
        table_id="2_bkcc_built_in_time_series.__default__",
        storage_cluster_name="vm-default",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
    )

    assert mock_delete.call_count == 0
    assert [config["kind"] for config in configs] == ["ResultTable", "VmStorageBinding", "Databus"]
    assert ResultTableConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert VMStorageBindingConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert DataBusConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert ResultTableConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert SurrealDBBindingConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert GraphDataBusConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert SurrealDBStorage.objects.filter(table_id="2_bkcc_built_in_time_series.__default__").exists()
    assert StorageClusterRecord.objects.filter(
        table_id="2_bkcc_built_in_time_series.__default__", cluster_id=2001
    ).exists()
    assert StorageClusterRecord.objects.filter(
        table_id="2_bkcc_built_in_time_series.__default__", cluster_id=1001
    ).exists()
    assert hasattr(data_link, "_graph_transition_cleanup_after_apply")


@pytest.mark.parametrize(
    ("write_mode", "expected_storage_type"),
    [
        (GraphRelationBindingConfig.WRITE_MODE_VM, models.ClusterInfo.TYPE_VM),
        (GraphRelationBindingConfig.WRITE_MODE_SURREALDB, models.ClusterInfo.TYPE_SURREALDB),
        (GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB, models.ClusterInfo.TYPE_VM),
    ],
)
def test_apply_graph_relation_time_series_records_storage_type(mocker, write_mode, expected_storage_type):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=f"bkm_relation_apply_{write_mode}",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    mocker.patch.object(data_link, "compose_configs", return_value=[])
    mocker.patch.object(data_link, "apply_data_link_with_retry", return_value={})

    data_link.apply_data_link(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
        write_mode=write_mode,
    )

    bkbase_rt = BkBaseResultTable.objects.get(data_link_name=data_link.data_link_name)
    assert bkbase_rt.storage_type == expected_storage_type


def test_compose_graph_relation_time_series_reuses_existing_vm_result_table(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=table_id,
        bk_base_data_id=12345,
        bk_base_data_name="legacy_data_name",
        storage_cluster_id=9001,
        vm_cluster_id=9001,
        vm_result_table_id="2_vm_bkcc_built_in_time_series",
    )
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_compose_existing_vm_record",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )

    configs = data_link.compose_graph_relation_time_series_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )

    graph_binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    vm_result_table = ResultTableConfig.objects.get(
        data_link_name=data_link.data_link_name, name="vm_bkcc_built_in_time_series"
    )
    vm_binding = VMStorageBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    vm_databus = DataBusConfig.objects.get(data_link_name=data_link.data_link_name, name="vm_bkcc_built_in_time_series")
    vm_binding_payload = next(
        config
        for config in configs
        if config["kind"] == "VmStorageBinding" and config["metadata"]["name"] == "vm_bkcc_built_in_time_series"
    )
    vm_databus_payload = next(
        config
        for config in configs
        if config["kind"] == "Databus"
        and config["metadata"]["name"] == "vm_bkcc_built_in_time_series"
        and config["spec"]["sinks"][0]["kind"] == "VmStorageBinding"
    )

    assert graph_binding.bkbase_result_table_name == "vm_bkcc_built_in_time_series"
    assert graph_binding.vm_storage_binding_name == "vm_bkcc_built_in_time_series"
    assert graph_binding.vm_databus_name == "vm_bkcc_built_in_time_series"
    assert vm_result_table.table_id == table_id
    assert vm_binding.bkbase_result_table_name == "vm_bkcc_built_in_time_series"
    assert vm_databus.bk_data_id == data_source.bk_data_id
    assert vm_binding_payload["spec"]["data"]["name"] == "vm_bkcc_built_in_time_series"
    assert vm_databus_payload["spec"]["sinks"][0]["name"] == "vm_bkcc_built_in_time_series"


def test_compose_graph_relation_time_series_corrects_existing_binding_vm_result_table(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=table_id,
        bk_base_data_id=12345,
        bk_base_data_name="legacy_data_name",
        storage_cluster_id=9001,
        vm_cluster_id=9001,
        vm_result_table_id="2_vm_bkcc_built_in_time_series",
    )
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_compose_correct_existing_binding",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name="bkm_bkcc_built_in_time_series",
        graph_result_table_name="bkm_bkcc_built_in_time_series_graph_relation",
        vm_storage_binding_name="bkm_bkcc_built_in_time_series",
        vm_databus_name="bkm_bkcc_built_in_time_series",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        table_type="temporary",
        vertices=[{"name": "old"}],
        relations=[{"name": "old_relation"}],
    )

    configs = data_link.compose_graph_relation_time_series_configs(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )

    graph_binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    vm_binding_payload = next(
        config
        for config in configs
        if config["kind"] == "VmStorageBinding" and config["metadata"]["name"] == "vm_bkcc_built_in_time_series"
    )
    vm_databus_payload = next(
        config
        for config in configs
        if config["kind"] == "Databus"
        and config["metadata"]["name"] == "vm_bkcc_built_in_time_series"
        and config["spec"]["sinks"][0]["kind"] == "VmStorageBinding"
    )

    assert graph_binding.bkbase_result_table_name == "vm_bkcc_built_in_time_series"
    assert graph_binding.vm_storage_binding_name == "vm_bkcc_built_in_time_series"
    assert graph_binding.vm_databus_name == "vm_bkcc_built_in_time_series"
    assert vm_binding_payload["spec"]["data"]["name"] == "vm_bkcc_built_in_time_series"
    assert vm_databus_payload["spec"]["sinks"][0]["name"] == "vm_bkcc_built_in_time_series"


def test_resolve_graph_relation_vm_result_table_name_keeps_non_numeric_prefix():
    table_id = "2_bkcc_built_in_time_series.__default__"
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=table_id,
        bk_base_data_id=12345,
        bk_base_data_name="legacy_data_name",
        storage_cluster_id=9001,
        vm_cluster_id=9001,
        vm_result_table_id="test_vm_rt",
    )

    assert (
        DataLink.resolve_graph_relation_vm_result_table_name(
            bk_tenant_id="system",
            table_id=table_id,
            default_name="bkm_bkcc_built_in_time_series",
        )
        == "test_vm_rt"
    )


def test_apply_graph_relation_time_series_does_not_rewrite_existing_vm_record(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    models.AccessVMRecord.objects.create(
        bk_tenant_id="system",
        result_table_id=table_id,
        bk_base_data_id=12345,
        bk_base_data_name="legacy_data_name",
        storage_cluster_id=9001,
        vm_cluster_id=9001,
        vm_result_table_id="2_vm_bkcc_built_in_time_series",
    )
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_apply_existing_vm_record",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    mocker.patch.object(data_link, "apply_data_link_with_retry", return_value={})

    data_link.apply_data_link(
        bk_biz_id=2,
        data_source=data_source,
        table_id=table_id,
        storage_cluster_name="vm-default",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
    )

    vm_record = models.AccessVMRecord.objects.get(
        bk_tenant_id=data_link.bk_tenant_id,
        result_table_id=table_id,
    )
    assert vm_record.bk_base_data_id == 12345
    assert vm_record.bk_base_data_name == "legacy_data_name"
    assert vm_record.vm_result_table_id == "2_vm_bkcc_built_in_time_series"
    assert vm_record.storage_cluster_id == 9001
    assert vm_record.vm_cluster_id == 9001


def test_sync_graph_definition_marks_surrealdb_only_empty_definitions_failed(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_empty_definition_sync",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([], []),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="delete")

    assert result["matched"] == 1
    assert result["applied"] == 0
    assert result["skipped"] == 0
    assert result["failed"] == 1
    assert "graph definitions are empty" in result["failures"][0]["error"]
    assert (
        GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name).status
        == DataLinkResourceStatus.FAILED.value
    )
    mock_apply.assert_not_called()


def test_sync_graph_definition_downgrades_dual_write_empty_definitions_to_vm(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_empty_definition_dual_sync",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([], []),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="delete")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["write_mode"] == GraphRelationBindingConfig.WRITE_MODE_VM
    assert mock_apply.call_args.kwargs["persist_graph_write_mode"] is True
    assert mock_apply.call_args.kwargs["surrealdb_auto_restore"] is True


def test_sync_graph_definition_skips_vm_only_empty_definitions(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_empty_definition_vm_sync",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        status=DataLinkResourceStatus.OK.value,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch("metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="delete")

    assert result["matched"] == 1
    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert result["failed"] == 0
    mock_apply.assert_not_called()
    graph_binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    assert graph_binding.status == DataLinkResourceStatus.OK.value


def test_sync_graph_definition_keeps_explicit_vm_only_binding_when_definitions_return(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_restored_definition_vm_sync",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        bkbase_result_table_name="2_bkcc_built_in_time_series",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        status=DataLinkResourceStatus.OK.value,
    )
    ResultTableConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    create_ok_vm_storage_binding(data_link, table_id)
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 0
    assert result["applied"] == 0
    assert result["skipped"] == 0
    mock_apply.assert_not_called()


def test_sync_graph_definition_promotes_auto_downgraded_vm_binding_when_definitions_return(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_restored_definition_downgraded_sync",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="2_bkcc_built_in_time_series",
        graph_result_table_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        surrealdb_auto_restore=True,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    create_ok_vm_storage_binding(data_link, table_id)
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert mock_apply.call_args.kwargs["write_mode"] == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB


def test_sync_graph_definition_keeps_explicit_vm_only_binding_with_historical_graph_fields(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_explicit_vm_with_graph_fields",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="2_bkcc_built_in_time_series",
        graph_result_table_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        surrealdb_auto_restore=False,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    create_ok_vm_storage_binding(data_link, table_id)
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 0
    assert result["skipped"] == 1
    assert result["failed"] == 0
    mock_apply.assert_not_called()


def test_sync_graph_definition_treats_fallback_vm_databus_name_as_healthy(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_vm_databus_fallback",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="2_bkcc_built_in_time_series",
        graph_result_table_name=graph_table_name,
        vm_databus_name="",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    create_ok_vm_storage_binding(data_link, table_id)
    ResultTableConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_table_name,
        vertices=vertices,
        relations=relations,
    )
    GraphDataBusConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        sink_names=[f"SurrealDBBinding:{graph_table_name}"],
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 0
    assert result["skipped"] == 1
    mock_apply.assert_not_called()


@pytest.mark.parametrize(
    ("create_vm_binding", "vm_binding_status"),
    [
        (False, ""),
        (True, DataLinkResourceStatus.FAILED.value),
        (True, DataLinkResourceStatus.PENDING.value),
    ],
)
def test_sync_graph_definition_reapplies_when_vm_storage_binding_unhealthy(
    mocker, create_vm_binding, vm_binding_status
):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_vm_binding_unhealthy",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        bkbase_result_table_name="2_bkcc_built_in_time_series",
        graph_result_table_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    if create_vm_binding:
        VMStorageBindingConfig.objects.create(
            name="2_bkcc_built_in_time_series",
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
            vm_cluster_name="vm-default",
            table_id=table_id,
            bkbase_result_table_name="2_bkcc_built_in_time_series",
            status=vm_binding_status,
        )
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        sink_names=["VmStorageBinding:2_bkcc_built_in_time_series"],
        status=DataLinkResourceStatus.OK.value,
    )
    ResultTableConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_table_name,
        vertices=vertices,
        relations=relations,
    )
    GraphDataBusConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        sink_names=[f"SurrealDBBinding:{graph_table_name}"],
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_apply.assert_called_once()


def test_sync_graph_definition_scopes_datalink_lookup_to_graph_strategy(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_strategy_lookup",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(
            [{"name": "service", "id_fields": ["service_name"]}],
            [{"name": "service_pod", "from": "service", "to": "pod"}],
        ),
    )
    mock_get = mocker.patch.object(DataLink.objects, "get", return_value=data_link)
    mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    mock_get.assert_called_once_with(
        bk_tenant_id=data_link.bk_tenant_id,
        namespace=data_link.namespace,
        data_link_name=data_link.data_link_name,
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    )


def test_sync_graph_definition_marks_binding_failed_when_apply_raises(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_apply_failure",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(
            [{"name": "service", "id_fields": ["service_name"]}],
            [{"name": "service_pod", "from": "service", "to": "pod"}],
        ),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link", side_effect=ValueError("apply failed"))

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 0
    assert result["failed"] == 1
    mock_apply.assert_called_once()
    assert result["failures"][0]["error"] == "apply failed"
    assert (
        GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name).status
        == DataLinkResourceStatus.FAILED.value
    )


def test_sync_graph_definition_dry_run_does_not_mark_empty_surrealdb_binding_failed(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_empty_dry_run",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch("metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply", dry_run=True)

    assert result["matched"] == 1
    assert result["failed"] == 1
    graph_binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    assert graph_binding.status == DataLinkResourceStatus.OK.value


def test_sync_graph_definition_dry_run_does_not_mark_apply_exception_failed(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_apply_dry_run_failure",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=DataLink.compose_surrealdb_table_name(table_id),
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "service", "id_fields": ["service_name"]}], [{"name": "service_pod"}]),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link", side_effect=ValueError("apply failed"))

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply", dry_run=True)

    assert result["applied"] == 1
    assert result["failed"] == 0
    mock_apply.assert_not_called()
    graph_binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    assert graph_binding.status == DataLinkResourceStatus.OK.value


def test_sync_graph_definition_retries_unchanged_failed_binding(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_retry_failed",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        status=DataLinkResourceStatus.FAILED.value,
        vertices=vertices,
        relations=relations,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_table_name,
        vertices=vertices,
        relations=relations,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_apply.assert_called_once()


def test_sync_graph_definition_reapplies_when_graph_databus_missing(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_missing_databus",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_table_name,
        vertices=vertices,
        relations=relations,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mocker.patch(
        "metadata.models.data_link.service.get_data_link_component_status",
        return_value=DataLinkResourceStatus.OK.value,
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_apply.assert_called_once()


def test_sync_graph_definition_reapplies_when_graph_databus_not_ok(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    graph_table_name = DataLink.compose_surrealdb_table_name(table_id)
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    data_source = create_graph_relation_data_source()
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id=data_source.bk_tenant_id,
        creator="system",
    )
    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_graph_failed_databus",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link.data_link_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name=graph_table_name,
        graph_databus_name=graph_table_name,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
        vertices=vertices,
        relations=relations,
    )
    ResultTableConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.OK.value,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_table_name,
        vertices=vertices,
        relations=relations,
    )
    GraphDataBusConfig.objects.create(
        name=graph_table_name,
        data_link_name=data_link.data_link_name,
        namespace=data_link.namespace,
        bk_tenant_id=data_link.bk_tenant_id,
        bk_biz_id=2,
        status=DataLinkResourceStatus.FAILED.value,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch.object(DataLink, "apply_data_link")

    from metadata.models.entity_relation import NAMESPACE_ALL
    from metadata.task.sync_cmdb_relation import sync_graph_definition_to_bkbase

    result = sync_graph_definition_to_bkbase(namespace=NAMESPACE_ALL, action="apply")

    assert result["matched"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0
    mock_apply.assert_called_once()


def test_compose_graph_relation_rejects_empty_surrealdb_definitions(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = create_graph_relation_data_source()
    create_storage_clusters()
    mocker.patch(
        "metadata.models.entity_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([], []),
    )

    data_link = DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name="bkm_relation_empty_definition_compose",
        namespace="bkmonitor",
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
    )

    with pytest.raises(ValueError, match="graph definitions are empty"):
        data_link.compose_graph_relation_time_series_configs(
            bk_biz_id=2,
            data_source=data_source,
            table_id=table_id,
            storage_cluster_name="vm-default",
            write_mode=GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
        )


def test_graph_databus_proxy_manager_filters_graph_records():
    DataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series",
        data_id_name="data",
        data_link_name="vm_link",
        namespace="bkmonitor",
        bk_biz_id=2,
        bk_tenant_id="system",
        bk_data_id=50001,
        sink_names=["VmStorageBinding:2_bkcc_built_in_time_series"],
    )
    GraphDataBusConfig.objects.create(
        name="2_bkcc_built_in_time_series_graph",
        data_id_name="data",
        data_link_name="graph_link",
        namespace="bkmonitor",
        bk_biz_id=2,
        bk_tenant_id="system",
        bk_data_id=50001,
        sink_names=["SurrealDBBinding:2_bkcc_built_in_time_series_graph"],
    )

    assert list(GraphDataBusConfig.objects.values_list("name", flat=True)) == ["2_bkcc_built_in_time_series_graph"]
