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
from metadata.models.data_link.utils import compose_bkdata_table_id
from metadata.task.sync_cmdb_relation import (
    _get_graph_definition_binding_queryset,
    enable_relation_surrealdb_dual_write,
)

pytestmark = pytest.mark.django_db(databases="__all__")


def _create_graph_relation_child_components(
    *,
    data_link_name,
    table_id,
    graph_table_id,
    bkbase_result_table_name,
    graph_result_table_name,
    vertices,
    relations,
    bk_biz_id,
    create_vm_binding=True,
    vm_binding_status=DataLinkResourceStatus.OK.value,
):
    ResultTableConfig.objects.create(
        name=bkbase_result_table_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=bk_biz_id,
        table_id=table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    if create_vm_binding:
        VMStorageBindingConfig.objects.create(
            name=bkbase_result_table_name,
            data_link_name=data_link_name,
            namespace="bkmonitor",
            bk_tenant_id="system",
            bk_biz_id=bk_biz_id,
            vm_cluster_name="vm-default",
            table_id=table_id,
            bkbase_result_table_name=bkbase_result_table_name,
            status=vm_binding_status,
        )
    DataBusConfig.objects.create(
        name=bkbase_result_table_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=bk_biz_id,
        sink_names=[f"VmStorageBinding:{bkbase_result_table_name}"],
        status=DataLinkResourceStatus.OK.value,
    )
    ResultTableConfig.objects.create(
        name=graph_result_table_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=bk_biz_id,
        table_id=graph_table_id,
        status=DataLinkResourceStatus.OK.value,
    )
    SurrealDBBindingConfig.objects.create(
        name=graph_result_table_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=bk_biz_id,
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=graph_result_table_name,
        vertices=vertices,
        relations=relations,
        status=DataLinkResourceStatus.OK.value,
    )
    GraphDataBusConfig.objects.create(
        name=graph_result_table_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=bk_biz_id,
        sink_names=[f"SurrealDBBinding:{graph_result_table_name}"],
        status=DataLinkResourceStatus.OK.value,
    )


def test_graph_relation_binding_write_mode_flags():
    binding = GraphRelationBindingConfig(write_mode=GraphRelationBindingConfig.WRITE_MODE_VM)
    assert binding.should_write_vm is True
    assert binding.should_write_surrealdb is False

    binding.write_mode = GraphRelationBindingConfig.WRITE_MODE_SURREALDB
    assert binding.should_write_vm is False
    assert binding.should_write_surrealdb is True

    binding.write_mode = GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    assert binding.should_write_vm is True
    assert binding.should_write_surrealdb is True


def test_enable_relation_surrealdb_dual_write_creates_graph_relation_datalink(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="2_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__2",
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id="2_bkcc_built_in_time_series.__default__",
        bk_tenant_id="system",
        creator="system",
    )
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
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")

    enable_relation_surrealdb_dual_write(data_source, "system", 2)

    data_link_name = compose_bkdata_table_id("system_2_bkcc_built_in_time_series_graph_relation")
    data_link = DataLink.objects.get(data_link_name=data_link_name)
    assert data_link.data_link_strategy == DataLink.GRAPH_RELATION_TIME_SERIES
    assert data_link.table_ids == ["2_bkcc_built_in_time_series.__default__"]
    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link.data_link_name)
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    assert binding.vm_cluster_name == "vm-default"
    assert binding.surrealdb_cluster_name == "surreal-default"
    mock_apply.assert_called_once()


def test_enable_relation_surrealdb_dual_write_apply_failure_is_best_effort(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50014,
        data_name="5_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__5",
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id="5_bkcc_built_in_time_series.__default__",
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1004,
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
        cluster_id=2004,
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
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )
    mocker.patch(
        "metadata.models.data_link.data_link.DataLink.apply_data_link",
        side_effect=RuntimeError("bkbase down"),
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 5)

    data_link_name = compose_bkdata_table_id("system_5_bkcc_built_in_time_series_graph_relation")
    assert DataLink.objects.filter(data_link_name=data_link_name).exists()
    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link_name)
    assert binding.status == DataLinkResourceStatus.FAILED.value


def test_enable_relation_surrealdb_dual_write_downgrades_empty_definitions_to_vm(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50015,
        data_name="6_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__6",
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id="6_bkcc_built_in_time_series.__default__",
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1005,
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
        cluster_id=2005,
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
    mocker.patch("metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")

    enable_relation_surrealdb_dual_write(data_source, "system", 6)

    data_link_name = compose_bkdata_table_id("system_6_bkcc_built_in_time_series_graph_relation")
    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link_name)
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["write_mode"] == GraphRelationBindingConfig.WRITE_MODE_VM
    assert mock_apply.call_args.kwargs["persist_graph_write_mode"] is False


def test_enable_relation_surrealdb_dual_write_persists_write_mode_transition(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50017,
        data_name="8_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__8",
    )
    table_id = "8_bkcc_built_in_time_series.__default__"
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1007,
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
        cluster_id=2007,
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
    mocker.patch("metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")

    data_link_name = compose_bkdata_table_id("system_8_bkcc_built_in_time_series_graph_relation")
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=8,
        status=DataLinkResourceStatus.OK.value,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        vertices=[{"name": "pod", "id_fields": ["pod"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 8)

    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link_name)
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["write_mode"] == GraphRelationBindingConfig.WRITE_MODE_VM
    assert mock_apply.call_args.kwargs["persist_graph_write_mode"] is False


def test_enable_relation_surrealdb_dual_write_preserves_existing_write_mode(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50012,
        data_name="3_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__3",
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id="3_bkcc_built_in_time_series.__default__",
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1002,
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
        cluster_id=2002,
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
    mock_query_definitions = mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        side_effect=RuntimeError("definition lookup should not run for vm-only mode"),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")
    data_link_name = compose_bkdata_table_id("system_3_bkcc_built_in_time_series_graph_relation")
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=3,
        status="Ok",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        table_type="normal",
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 3)

    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link_name)
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
    assert binding.table_type == "normal"
    mock_query_definitions.assert_not_called()
    mock_apply.assert_called_once()


@pytest.mark.parametrize(
    "binding_status",
    [DataLinkResourceStatus.OK.value, DataLinkResourceStatus.INITIALIZING.value],
)
def test_enable_relation_surrealdb_dual_write_skips_unchanged_healthy_graph_link(mocker, binding_status):
    data_source = models.DataSource.objects.create(
        bk_data_id=50016,
        data_name="7_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__7",
    )
    table_id = "7_bkcc_built_in_time_series.__default__"
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1006,
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
        cluster_id=2006,
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
    vertices = [{"name": "pod", "id_fields": ["pod"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")
    mocker.patch.object(
        GraphRelationBindingConfig,
        "_aggregate_status",
        return_value=DataLinkResourceStatus.OK.value,
    )

    data_link_name = compose_bkdata_table_id("system_7_bkcc_built_in_time_series_graph_relation")
    graph_table_id = "7_bkcc_built_in_time_series_graph.__default__"
    bkbase_result_table_name = compose_bkdata_table_id(table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)
    graph_result_table_name = compose_bkdata_table_id(graph_table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)
    DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=7,
        status=binding_status,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=bkbase_result_table_name,
        graph_result_table_name=graph_result_table_name,
        table_type="temporary",
        vertices=vertices,
        relations=relations,
    )
    _create_graph_relation_child_components(
        data_link_name=data_link_name,
        table_id=table_id,
        graph_table_id=graph_table_id,
        bkbase_result_table_name=bkbase_result_table_name,
        graph_result_table_name=graph_result_table_name,
        vertices=vertices,
        relations=relations,
        bk_biz_id=7,
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 7)

    mock_apply.assert_not_called()


@pytest.mark.parametrize(
    ("create_vm_binding", "vm_binding_status"),
    [
        (False, ""),
        (True, DataLinkResourceStatus.FAILED.value),
        (True, DataLinkResourceStatus.PENDING.value),
    ],
)
def test_enable_relation_surrealdb_dual_write_retries_when_vm_storage_binding_unhealthy(
    mocker, create_vm_binding, vm_binding_status
):
    data_source = models.DataSource.objects.create(
        bk_data_id=50019,
        data_name="10_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__10",
    )
    table_id = "10_bkcc_built_in_time_series.__default__"
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1009,
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
        cluster_id=2009,
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
    vertices = [{"name": "pod", "id_fields": ["pod"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")
    mocker.patch.object(
        GraphRelationBindingConfig,
        "_aggregate_status",
        return_value=DataLinkResourceStatus.OK.value,
    )

    data_link_name = compose_bkdata_table_id("system_10_bkcc_built_in_time_series_graph_relation")
    graph_table_id = "10_bkcc_built_in_time_series_graph.__default__"
    bkbase_result_table_name = compose_bkdata_table_id(table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)
    graph_result_table_name = compose_bkdata_table_id(graph_table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)
    DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=10,
        status=DataLinkResourceStatus.OK.value,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=bkbase_result_table_name,
        graph_result_table_name=graph_result_table_name,
        table_type="temporary",
        vertices=vertices,
        relations=relations,
    )
    _create_graph_relation_child_components(
        data_link_name=data_link_name,
        table_id=table_id,
        graph_table_id=graph_table_id,
        bkbase_result_table_name=bkbase_result_table_name,
        graph_result_table_name=graph_result_table_name,
        vertices=vertices,
        relations=relations,
        bk_biz_id=10,
        create_vm_binding=create_vm_binding,
        vm_binding_status=vm_binding_status,
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 10)

    mock_apply.assert_called_once()


def test_enable_relation_surrealdb_dual_write_retries_unchanged_failed_graph_link(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50018,
        data_name="9_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__9",
    )
    table_id = "9_bkcc_built_in_time_series.__default__"
    models.DataSourceResultTable.objects.create(
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        bk_tenant_id="system",
        creator="system",
    )
    models.ClusterInfo.objects.create(
        cluster_id=1008,
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
        cluster_id=2008,
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
    vertices = [{"name": "pod", "id_fields": ["pod"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")
    mocker.patch.object(
        GraphRelationBindingConfig,
        "_aggregate_status",
        return_value=DataLinkResourceStatus.OK.value,
    )

    data_link_name = compose_bkdata_table_id("system_9_bkcc_built_in_time_series_graph_relation")
    graph_table_id = "9_bkcc_built_in_time_series_graph.__default__"
    DataLink.objects.create(
        bk_tenant_id="system",
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_data_id=data_source.bk_data_id,
        table_ids=[table_id],
        data_link_strategy=DataLink.GRAPH_RELATION_TIME_SERIES,
    )
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=9,
        status=DataLinkResourceStatus.FAILED.value,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        vm_cluster_name="vm-default",
        surrealdb_cluster_name="surreal-default",
        table_id=table_id,
        bkbase_result_table_name=compose_bkdata_table_id(table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
        graph_result_table_name=compose_bkdata_table_id(graph_table_id, DataLink.BK_STANDARD_V2_TIME_SERIES),
        table_type="temporary",
        vertices=vertices,
        relations=relations,
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 9)

    mock_apply.assert_called_once()


def test_get_graph_definition_binding_queryset_includes_auto_downgraded_vm_bindings():
    for index, write_mode in enumerate(
        [
            GraphRelationBindingConfig.WRITE_MODE_VM,
            GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
            GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        ],
        start=1,
    ):
        GraphRelationBindingConfig.objects.create(
            name=f"graph_relation_binding_{index}",
            data_link_name=f"graph_relation_binding_{index}",
            namespace="bkmonitor",
            bk_tenant_id="system",
            bk_biz_id=index,
            status=DataLinkResourceStatus.OK.value,
            write_mode=write_mode,
        )
    GraphRelationBindingConfig.objects.create(
        name="graph_relation_binding_downgraded",
        data_link_name="graph_relation_binding_downgraded",
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=4,
        status=DataLinkResourceStatus.OK.value,
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
        surrealdb_cluster_name="surreal-default",
        graph_result_table_name="graph_rt",
    )

    matched_names = set(_get_graph_definition_binding_queryset("__all__").values_list("name", flat=True))

    assert matched_names == {
        "graph_relation_binding_2",
        "graph_relation_binding_3",
        "graph_relation_binding_downgraded",
    }


def test_enable_relation_surrealdb_dual_write_does_not_create_datalink_without_result_table():
    data_source = models.DataSource.objects.create(
        bk_data_id=50013,
        data_name="4_bkcc_built_in_time_series",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        space_uid="bkcc__4",
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 4)

    data_link_name = compose_bkdata_table_id("system_4_bkcc_built_in_time_series_graph_relation")
    assert not DataLink.objects.filter(data_link_name=data_link_name).exists()
