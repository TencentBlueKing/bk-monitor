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
from metadata.models.data_link.data_link_configs import GraphRelationBindingConfig
from metadata.task.sync_cmdb_relation import enable_relation_surrealdb_dual_write

pytestmark = pytest.mark.django_db(databases="__all__")


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

    data_link = DataLink.objects.get(data_link_name="2_bkcc_built_in_time_series_graph_relation")
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
    mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link", side_effect=RuntimeError("bkbase down"))

    enable_relation_surrealdb_dual_write(data_source, "system", 5)

    assert DataLink.objects.filter(data_link_name="5_bkcc_built_in_time_series_graph_relation").exists()


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

    binding = GraphRelationBindingConfig.objects.get(data_link_name="6_bkcc_built_in_time_series_graph_relation")
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["write_mode"] == GraphRelationBindingConfig.WRITE_MODE_VM


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
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod"]}], [{"name": "pod_node", "from": "pod", "to": "node"}]),
    )
    mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link")
    data_link_name = "3_bkcc_built_in_time_series_graph_relation"
    GraphRelationBindingConfig.objects.create(
        name=data_link_name,
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        bk_biz_id=3,
        status="Ok",
        write_mode=GraphRelationBindingConfig.WRITE_MODE_VM,
    )

    enable_relation_surrealdb_dual_write(data_source, "system", 3)

    binding = GraphRelationBindingConfig.objects.get(data_link_name=data_link_name)
    assert binding.write_mode == GraphRelationBindingConfig.WRITE_MODE_VM


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

    assert not DataLink.objects.filter(data_link_name="4_bkcc_built_in_time_series_graph_relation").exists()
