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
    assert kinds.count("Databus") == expected_databus_count
    assert ("VmStorageBinding" in kinds) is expected_vm
    assert ("SurrealDBBinding" in kinds) is expected_surrealdb

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
        DataBusConfig.objects.create(
            name=name,
            data_id_name="bkm_relation_data_id",
            bk_data_id=50003,
            data_link_name=data_link.data_link_name,
            namespace=data_link.namespace,
            bk_tenant_id=data_link.bk_tenant_id,
            bk_biz_id=2,
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

    deleted_names = {call.kwargs["name"] for call in mock_delete.call_args_list}
    assert deleted_names == {"bkm_graph_relation_rt"}
    assert [config["kind"] for config in configs] == ["ResultTable", "VmStorageBinding", "Databus"]
    assert ResultTableConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert VMStorageBindingConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert DataBusConfig.objects.filter(name="bkm_vm_relation_rt").exists()
    assert not ResultTableConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert not SurrealDBBindingConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert not GraphDataBusConfig.objects.filter(name="bkm_graph_relation_rt").exists()
    assert not SurrealDBStorage.objects.filter(table_id="2_bkcc_built_in_time_series.__default__").exists()
    assert not StorageClusterRecord.objects.filter(
        table_id="2_bkcc_built_in_time_series.__default__", cluster_id=2001
    ).exists()
    assert StorageClusterRecord.objects.filter(
        table_id="2_bkcc_built_in_time_series.__default__", cluster_id=1001
    ).exists()


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


def test_sync_graph_definition_skips_empty_definitions(mocker):
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
    assert result["skipped"] == 1
    assert result["failed"] == 0
    mock_apply.assert_not_called()


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
