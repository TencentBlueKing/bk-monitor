"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

import pytest
from django.conf import settings
from django.test import override_settings

from bkmonitor.utils.cipher import transform_data_id_to_token
from metadata import models
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.data_link import SURREALDB_RT_SUFFIX
from metadata.models.data_link.utils import compose_bkdata_table_id
from metadata.task import sync_cmdb_relation
from metadata.task.sync_cmdb_relation import (
    _graph_definitions_changed,
    enable_relation_surrealdb_dual_write,
    sync_relation_redis_data,
)
from metadata.tests.common_utils import consul_client

mock_redis_hgetall_return_value = {
    b"bkcc__2": b'{"token":"testtokenxxxxxx","modifyTime":"1733132051"}',
    b"bkcc__3": b'{"token":""}',
}


@pytest.fixture
def create_and_delete_records(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.Label.objects.update_or_create(
        label_id="bk_monitor",
        defaults={"label_name": "蓝鲸监控", "label_type": models.Label.LABEL_TYPE_SOURCE},
    )
    models.Label.objects.update_or_create(
        label_id="time_series",
        defaults={"label_name": "时序数据", "label_type": models.Label.LABEL_TYPE_TYPE},
    )
    models.Label.objects.update_or_create(
        label_id=models.Label.RESULT_TABLE_LABEL_OTHER,
        defaults={"label_name": "其他", "label_type": models.Label.LABEL_TYPE_RESULT_TABLE},
    )
    models.ClusterInfo.objects.update_or_create(
        cluster_id=900001,
        defaults={
            "cluster_name": "default_kafka",
            "cluster_type": models.ClusterInfo.TYPE_KAFKA,
            "domain_name": "kafka.service",
            "port": 9092,
            "description": "",
            "is_default_cluster": True,
            "bk_tenant_id": "system",
            "registered_to_bkbase": True,
        },
    )
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="2_bkcc_built_in_time_series",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.KafkaTopicInfo.objects.create(
        bk_data_id=50010,
        topic="test_50010",
        partition=0,
    )
    models.ResultTable.objects.create(
        table_id="2_bkcc_built_in_time_series.__default__",
        table_name_zh="2_bkcc_built_in_time_series.__default__",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=2,
        is_builtin=True,
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    models.KafkaStorage.objects.all().delete()
    models.ResultTable.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_sync_relation_redis_data(create_and_delete_records):
    """
    测试验证 CMDB Relation同步任务能否正确工作
    1. Token和DB中不一致，更新并回写
    2. 不存在对应内置RT和数据源，创建之
    """
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0) as mock_hset_to_redis,
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True) as mock_refresh_consul,
        patch(
            "metadata.models.TimeSeriesGroup.create_time_series_group",
            return_value=created_group,
        ),
    ):
        sync_relation_redis_data()

        bkcc_2_expected_token = transform_data_id_to_token(
            metric_data_id=50010, bk_biz_id=2, app_name="2_bkcc_built_in_time_series"
        )
        bkcc_2_builtin_ds = models.DataSource.objects.get(bk_data_id=50010)
        assert bkcc_2_expected_token == bkcc_2_builtin_ds.token

        bkcc_3_expected_token = transform_data_id_to_token(
            metric_data_id=50011, bk_biz_id=3, app_name="3_bkcc_built_in_time_series"
        )
        bkcc_3_builtin_ds = models.DataSource.objects.get(bk_data_id=50011)
        assert bkcc_3_expected_token == bkcc_3_builtin_ds.token

        # 应调用两次hset
        assert mock_hset_to_redis.call_count == 2

        # 预期参数
        expected_bkcc_3_timestamp = int(created_group.last_modify_time.timestamp())

        expected_calls = [
            call(
                f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
                "bkcc__2",
                f'{{"token":"{bkcc_2_expected_token}","modifyTime":"1733198214"}}',
            ),
            call(
                f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
                "bkcc__3",
                f'{{"token":"{bkcc_3_expected_token}","modifyTime":{expected_bkcc_3_timestamp}}}',
            ),
        ]
        assert mock_hset_to_redis.call_args_list == expected_calls
        assert {call_args.args[0].bk_data_id for call_args in mock_refresh_consul.call_args_list} == {50010, 50011}


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_SYNC_GRAPH_DEFINITION_TO_BKBASE=False)
def test_sync_relation_redis_data_skips_graph_dual_write_when_feature_disabled(create_and_delete_records):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch("metadata.models.TimeSeriesGroup.create_time_series_group", return_value=created_group),
        patch("metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write") as mock_enable_dual_write,
    ):
        sync_relation_redis_data()

    mock_enable_dual_write.assert_not_called()
    assert not models.DataLink.objects.filter(data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES).exists()


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_SYNC_GRAPH_DEFINITION_TO_BKBASE=True)
def test_sync_relation_redis_data_calls_graph_dual_write_when_feature_enabled(create_and_delete_records):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch("metadata.models.TimeSeriesGroup.create_time_series_group", return_value=created_group),
        patch("metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write") as mock_enable_dual_write,
    ):
        sync_relation_redis_data()

    assert [call_args.args[0].bk_data_id for call_args in mock_enable_dual_write.call_args_list] == [50010, 50011]
    assert [call_args.args[2] for call_args in mock_enable_dual_write.call_args_list] == [2, 3]


@pytest.mark.django_db(databases="__all__")
def test_sync_relation_redis_data_uses_existing_time_series_group_token(create_and_delete_records, mocker):
    models.TimeSeriesGroup.objects.create(
        bk_data_id=50010,
        bk_biz_id=2,
        time_series_group_name="2_bkcc_built_in_time_series",
        table_id="2_bkcc_built_in_time_series.__default__",
        label=models.Label.RESULT_TABLE_LABEL_OTHER,
        token="group-token",
        creator="system",
        last_modify_user="system",
    )
    redis_data = {b"bkcc__2": b'{"token":"testtokenxxxxxx","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0) as mock_hset_to_redis,
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True) as mock_refresh_consul,
    ):
        token_spy = mocker.spy(sync_cmdb_relation, "_get_builtin_relation_token")
        sync_relation_redis_data()

    builtin_ds = models.DataSource.objects.get(bk_data_id=50010)
    assert builtin_ds.token == "group-token"
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3].token == "group-token"
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__2",
        '{"token":"group-token","modifyTime":"1733198214"}',
    )
    assert [call_args.args[0].bk_data_id for call_args in mock_refresh_consul.call_args_list] == [50010]


@pytest.mark.django_db(databases="__all__")
def test_sync_relation_redis_data_existing_rt_without_group_uses_generated_token(create_and_delete_records, mocker):
    redis_data = {b"bkcc__2": b'{"token":"testtokenxxxxxx","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0) as mock_hset_to_redis,
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True) as mock_refresh_consul,
    ):
        token_spy = mocker.spy(sync_cmdb_relation, "_get_builtin_relation_token")
        sync_relation_redis_data()

    expected_token = transform_data_id_to_token(
        metric_data_id=50010, bk_biz_id=2, app_name="2_bkcc_built_in_time_series"
    )
    builtin_ds = models.DataSource.objects.get(bk_data_id=50010)
    assert builtin_ds.token == expected_token
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3] is None
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__2",
        f'{{"token":"{expected_token}","modifyTime":"1733198214"}}',
    )
    assert [call_args.args[0].bk_data_id for call_args in mock_refresh_consul.call_args_list] == [50010]


@pytest.mark.django_db(databases="__all__")
def test_sync_relation_redis_data_new_rt_uses_created_group_token(create_and_delete_records, mocker):
    redis_data = {b"bkcc__3": b'{"token":""}'}
    created_group = Mock(
        token="created-group-token", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc)
    )
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0) as mock_hset_to_redis,
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True) as mock_refresh_consul,
        patch("metadata.models.TimeSeriesGroup.create_time_series_group", return_value=created_group),
    ):
        token_spy = mocker.spy(sync_cmdb_relation, "_get_builtin_relation_token")
        sync_relation_redis_data()

    builtin_ds = models.DataSource.objects.get(bk_data_id=50011)
    assert builtin_ds.token == "created-group-token"
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3] is created_group
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__3",
        '{"token":"created-group-token","modifyTime":1733198214}',
    )
    assert [call_args.args[0].bk_data_id for call_args in mock_refresh_consul.call_args_list] == [50011]


def _create_relation_graph_source(bk_data_id: int, data_name: str, bk_tenant_id: str, table_id: str):
    ds = models.DataSource.objects.create(
        bk_data_id=bk_data_id,
        data_name=data_name,
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        bk_tenant_id=bk_tenant_id,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=bk_data_id,
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
        creator="test",
    )
    return ds


def _create_relation_graph_clusters(bk_tenant_id: str, cluster_id_offset: int = 0):
    models.ClusterInfo.objects.create(
        cluster_id=910001 + cluster_id_offset,
        cluster_name=f"vm-default-{bk_tenant_id}",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.service",
        port=9090,
        description="",
        is_default_cluster=True,
        bk_tenant_id=bk_tenant_id,
        registered_to_bkbase=True,
    )
    models.ClusterInfo.objects.create(
        cluster_id=910101 + cluster_id_offset,
        cluster_name=f"surreal-default-{bk_tenant_id}",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surreal.service",
        port=8000,
        description="",
        is_default_cluster=True,
        bk_tenant_id=bk_tenant_id,
        registered_to_bkbase=True,
    )


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_link_namespaces_generated_name_by_tenant(mocker):
    data_name = "bkcc_built_in_time_series"
    first_table_id = "2_bkcc_built_in_time_series.__default__"
    second_table_id = "2_bkcc_built_in_time_series_other.__default__"
    first_ds = _create_relation_graph_source(61001, data_name, "system", first_table_id)
    second_ds = _create_relation_graph_source(61002, data_name, "tenant_b", second_table_id)
    _create_relation_graph_clusters("system", 0)
    _create_relation_graph_clusters("tenant_b", 10)
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "host", "id_fields": ["bk_host_id"]}], [{"name": "host_service"}]),
    )
    mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link", return_value=None)

    enable_relation_surrealdb_dual_write(first_ds, "system", 2)
    enable_relation_surrealdb_dual_write(second_ds, "tenant_b", 2)

    first_name = compose_bkdata_table_id("system_bkcc_built_in_time_series_graph_relation")
    second_name = compose_bkdata_table_id("tenant_b_bkcc_built_in_time_series_graph_relation")
    assert first_name != second_name
    assert models.DataLink.objects.filter(bk_tenant_id="system", data_link_name=first_name).exists()
    assert models.DataLink.objects.filter(bk_tenant_id="tenant_b", data_link_name=second_name).exists()


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_link_reuses_existing_vm_result_table_name(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_name = "bkcc_built_in_time_series"
    ds = _create_relation_graph_source(61004, data_name, "system", table_id)
    _create_relation_graph_clusters("system", 30)
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
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "host", "id_fields": ["bk_host_id"]}], [{"name": "host_service"}]),
    )
    mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link", return_value=None)

    enable_relation_surrealdb_dual_write(ds, "system", 2)

    graph_binding = models.GraphRelationBindingConfig.objects.get()
    assert graph_binding.bkbase_result_table_name == "vm_bkcc_built_in_time_series"


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_link_applies_vm_fallback_when_existing_config_unchanged(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_name = "bkcc_built_in_time_series"
    graph_link_name = compose_bkdata_table_id("system_bkcc_built_in_time_series_graph_relation")
    ds = _create_relation_graph_source(61003, data_name, "system", table_id)
    _create_relation_graph_clusters("system", 20)
    graph_table_id = table_id.replace(".__default__", f"{SURREALDB_RT_SUFFIX}.__default__", 1)
    vertices = [{"name": "host", "id_fields": ["bk_host_id"]}]
    relations = [{"name": "host_service"}]
    models.GraphRelationBindingConfig.objects.create(
        name=graph_link_name,
        data_link_name=graph_link_name,
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        vm_cluster_name="vm-default-system",
        surrealdb_cluster_name="surreal-default-system",
        table_id=table_id,
        bkbase_result_table_name=compose_bkdata_table_id(table_id, models.DataLink.BK_STANDARD_V2_TIME_SERIES),
        graph_result_table_name=compose_bkdata_table_id(graph_table_id, models.DataLink.BK_STANDARD_V2_TIME_SERIES),
        table_type="temporary",
        vertices=vertices,
        relations=relations,
        write_mode=models.GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
        status=DataLinkResourceStatus.OK.value,
    )
    mocker.patch("metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions", return_value=([], []))
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link", return_value=None)

    enable_relation_surrealdb_dual_write(ds, "system", 2)

    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs["write_mode"] == models.GraphRelationBindingConfig.WRITE_MODE_VM
    assert mock_apply.call_args.kwargs["persist_graph_write_mode"] is False
    graph_binding = models.GraphRelationBindingConfig.objects.get(name=graph_link_name)
    assert graph_binding.write_mode == models.GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB


@pytest.mark.django_db(databases="__all__")
def test_graph_definitions_changed_uses_stored_surrealdb_binding_name():
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    graph_binding = models.GraphRelationBindingConfig.objects.create(
        name="graph_binding",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
        graph_result_table_name="graph_rt",
        surrealdb_binding_name="rebuilt_surreal_binding",
        graph_databus_name="graph_databus",
        vertices=vertices,
        relations=relations,
        write_mode=models.GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
    )
    models.ResultTableConfig.objects.create(
        name="graph_rt",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
    )
    models.SurrealDBBindingConfig.objects.create(
        name="rebuilt_surreal_binding",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
        bkbase_result_table_name="graph_rt",
        surrealdb_cluster_name="surreal-default",
        vertices=vertices,
        relations=relations,
    )
    models.GraphDataBusConfig.objects.create(
        name="graph_databus",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        sink_names=["SurrealDBBinding:rebuilt_surreal_binding"],
    )

    assert not _graph_definitions_changed(graph_binding, vertices, relations)


@pytest.mark.django_db(databases="__all__")
def test_graph_definitions_changed_compares_surrealdb_binding_definitions():
    vertices = [{"name": "pod", "id_fields": ["pod_name"]}]
    relations = [{"name": "pod_node", "from": "pod", "to": "node"}]
    graph_binding = models.GraphRelationBindingConfig.objects.create(
        name="graph_binding",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
        graph_result_table_name="graph_rt",
        surrealdb_binding_name="surreal_binding",
        graph_databus_name="graph_databus",
        vertices=vertices,
        relations=relations,
        write_mode=models.GraphRelationBindingConfig.WRITE_MODE_SURREALDB,
    )
    models.ResultTableConfig.objects.create(
        name="graph_rt",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
    )
    models.SurrealDBBindingConfig.objects.create(
        name="surreal_binding",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
        bkbase_result_table_name="graph_rt",
        surrealdb_cluster_name="surreal-default",
        vertices=[{"name": "stale", "id_fields": ["id"]}],
        relations=relations,
    )
    models.GraphDataBusConfig.objects.create(
        name="graph_databus",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        sink_names=["SurrealDBBinding:surreal_binding"],
    )

    assert _graph_definitions_changed(graph_binding, vertices, relations)


@pytest.mark.django_db(databases="__all__")
def test_graph_definitions_changed_skips_vm_only_definition_diff():
    graph_binding = models.GraphRelationBindingConfig.objects.create(
        name="graph_binding",
        data_link_name="graph_link",
        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        bk_tenant_id="system",
        bk_biz_id=2,
        table_id="2_bkcc_built_in_time_series.__default__",
        graph_result_table_name="graph_rt",
        surrealdb_binding_name="historical_surreal_binding",
        vertices=[{"name": "pod", "id_fields": ["pod_name"]}],
        relations=[{"name": "pod_node", "from": "pod", "to": "node"}],
        write_mode=models.GraphRelationBindingConfig.WRITE_MODE_VM,
    )

    changed_vertices = [{"name": "service", "id_fields": ["bk_service_id"]}]
    changed_relations = [{"name": "service_module", "from": "service", "to": "module"}]
    assert not _graph_definitions_changed(graph_binding, changed_vertices, changed_relations)


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_link_falls_back_to_synced_surrealdb_cluster(mocker):
    table_id = "10_bkcc_built_in_time_series.__default__"
    data_source = _create_relation_graph_source(61010, "10_bkcc_built_in_time_series", "system", table_id)
    models.ClusterInfo.objects.create(
        cluster_id=910500,
        cluster_name="vm-default-system",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.service",
        port=9090,
        description="",
        is_default_cluster=True,
        bk_tenant_id="system",
        registered_to_bkbase=True,
    )
    models.ClusterInfo.objects.create(
        cluster_id=910600,
        cluster_name="surreal-synced",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surreal.service",
        port=8000,
        description="",
        is_default_cluster=False,
        bk_tenant_id="system",
        registered_to_bkbase=True,
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "pod", "id_fields": ["pod_name"]}], [{"name": "pod_node"}]),
    )
    mock_apply = mocker.patch("metadata.models.data_link.data_link.DataLink.apply_data_link", return_value=None)

    enable_relation_surrealdb_dual_write(data_source, "system", 10)

    mock_apply.assert_called_once()
    graph_binding = models.GraphRelationBindingConfig.objects.get()
    assert graph_binding.surrealdb_cluster_name == "surreal-synced"
