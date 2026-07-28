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
from metadata.task import sync_cmdb_relation
from metadata.task.sync_cmdb_relation import (
    _compose_relation_graph_v4_storage_config,
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
    models.ClusterInfo.objects.filter(
        bk_tenant_id="system",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        is_default_cluster=True,
    ).exclude(cluster_id=900001).update(is_default_cluster=False)
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
    1. 根据 TimeSeriesGroup 或兼容规则生成 Redis token
    2. 不存在对应内置RT和数据源，创建之
    3. 不覆盖 DataSource 自身的独立上报 token
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
        assert bkcc_2_builtin_ds.token == ""

        bkcc_3_expected_token = transform_data_id_to_token(
            metric_data_id=50011, bk_biz_id=3, app_name="3_bkcc_built_in_time_series"
        )
        bkcc_3_builtin_ds = models.DataSource.objects.get(bk_data_id=50011)
        assert bkcc_3_builtin_ds.token
        assert bkcc_3_builtin_ds.token != bkcc_3_expected_token

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
        mock_refresh_consul.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[3])
def test_sync_relation_redis_data_skips_missing_rt_with_existing_redis_token(create_and_delete_records):
    redis_data = {b"bkcc__3": b'{"token":"existing-token","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis") as mock_hset_to_redis,
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.create_data_source") as mock_create_data_source,
        patch(
            "metadata.task.sync_cmdb_relation._compose_relation_graph_v4_storage_config"
        ) as mock_compose_graph_config,
        patch("metadata.task.sync_cmdb_relation.logger.warning") as mock_warning,
    ):
        sync_relation_redis_data()

    mock_create_data_source.assert_not_called()
    mock_compose_graph_config.assert_not_called()
    mock_hset_to_redis.assert_not_called()
    assert any(
        "result table is missing but redis token exists" in call_args.args[0]
        for call_args in mock_warning.call_args_list
    )


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[])
def test_sync_relation_redis_data_skips_graph_dual_write_when_whitelist_empty(create_and_delete_records):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.models.TimeSeriesGroup.create_time_series_group",
            return_value=created_group,
        ),
        patch("metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write") as mock_enable_dual_write,
    ):
        sync_relation_redis_data()

    mock_enable_dual_write.assert_not_called()
    assert not models.DataLink.objects.filter(data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES).exists()


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[2])
def test_sync_relation_redis_data_configures_graph_v4_for_whitelist(create_and_delete_records):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    storage_config = {
        "storage_cluster_id": 900002,
        "table_type": "temporary",
        "vertices": [{"name": "host"}],
        "relations": [{"name": "host_service"}],
    }
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.models.TimeSeriesGroup.create_time_series_group",
            return_value=created_group,
        ) as mock_create_time_series_group,
        patch(
            "metadata.task.sync_cmdb_relation._compose_relation_graph_v4_storage_config",
            return_value=storage_config,
        ) as mock_compose_storage,
        patch("metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write") as mock_enable_dual_write,
    ):
        sync_relation_redis_data()

    mock_compose_storage.assert_called_once_with("system", 2, "2_bkcc_built_in_time_series.__default__")
    mock_enable_dual_write.assert_called_once()
    assert mock_enable_dual_write.call_args.args[0].bk_data_id == 50010
    assert mock_enable_dual_write.call_args.args[1:] == ("system", 2)
    assert mock_enable_dual_write.call_args.kwargs == {"storage_config": storage_config}
    assert mock_create_time_series_group.call_args.kwargs["is_sync_db"] is True


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[2])
def test_sync_relation_graph_v4_apply_failure_does_not_block_token_sync(create_and_delete_records):
    storage_config = {
        "storage_cluster_id": 900002,
        "table_type": "temporary",
        "vertices": [{"name": "host"}],
        "relations": [{"name": "host_service"}],
    }
    redis_data = {b"bkcc__2": b'{"token":"original-token","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0) as mock_hset_to_redis,
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.task.sync_cmdb_relation._compose_relation_graph_v4_storage_config",
            return_value=storage_config,
        ),
        patch(
            "metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write",
            side_effect=RuntimeError("graph apply failed"),
        ),
        patch("metadata.task.sync_cmdb_relation.logger.warning") as mock_warning,
    ):
        sync_relation_redis_data()

    expected_token = transform_data_id_to_token(
        metric_data_id=50010,
        bk_biz_id=2,
        app_name="2_bkcc_built_in_time_series",
    )
    assert models.DataSource.objects.get(bk_data_id=50010).token == ""
    mock_hset_to_redis.assert_called_once_with(
        settings.BUILTIN_DATA_RT_REDIS_KEY,
        "bkcc__2",
        f'{{"token":"{expected_token}","modifyTime":"1733198214"}}',
    )
    assert any(
        "graph relation dual-write best-effort setup failed" in call_args.args[0]
        for call_args in mock_warning.call_args_list
    )


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[2])
def test_sync_relation_redis_data_skips_modify_when_graph_v4_config_unchanged(create_and_delete_records):
    table_id = "2_bkcc_built_in_time_series.__default__"
    storage_config = {
        "storage_cluster_id": 900002,
        "table_type": "temporary",
        "vertices": [{"name": "host"}],
        "relations": [{"name": "host_service"}],
    }
    models.SurrealDBStorage.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        **storage_config,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        bk_data_id=50010,
        table_id=table_id,
        creator="system",
    )
    models.ResultTableOption.create_option(
        table_id=table_id,
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
        value={"write_targets": ["vm", "surrealdb"]},
        creator="system",
        bk_tenant_id="system",
    )
    redis_data = {b"bkcc__2": b'{"token":"testtokenxxxxxx","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.task.sync_cmdb_relation._compose_relation_graph_v4_storage_config",
            return_value=storage_config,
        ),
        patch("metadata.models.ResultTable.modify", autospec=True) as mock_modify,
    ):
        sync_relation_redis_data()

    mock_modify.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST="2, invalid, 3")
def test_sync_relation_redis_data_configures_each_graph_v4_whitelist_biz(create_and_delete_records):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    storage_config = {
        "storage_cluster_id": 900002,
        "table_type": "temporary",
        "vertices": [{"name": "host"}],
        "relations": [{"name": "host_service"}],
    }
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.models.TimeSeriesGroup.create_time_series_group",
            return_value=created_group,
        ) as mock_create_time_series_group,
        patch(
            "metadata.task.sync_cmdb_relation._compose_relation_graph_v4_storage_config",
            return_value=storage_config,
        ) as mock_compose_storage,
        patch("metadata.task.sync_cmdb_relation.enable_relation_surrealdb_dual_write") as mock_enable_dual_write,
    ):
        sync_relation_redis_data()

    assert mock_compose_storage.call_args_list == [
        call("system", 2, "2_bkcc_built_in_time_series.__default__"),
        call("system", 3, "3_bkcc_built_in_time_series.__default__"),
    ]
    assert [args.args[2] for args in mock_enable_dual_write.call_args_list] == [2, 3]
    assert all(args.kwargs == {"storage_config": storage_config} for args in mock_enable_dual_write.call_args_list)
    assert mock_create_time_series_group.call_args.kwargs["is_sync_db"] is False


@pytest.mark.django_db(databases="__all__")
@override_settings(GRAPH_RELATION_BKBASE_SYNC_BIZ_ID_WHITE_LIST=[2])
@pytest.mark.parametrize(
    ("create_cluster", "definitions", "error"),
    [
        (False, ([{"name": "host"}], [{"name": "host_service"}]), "default SurrealDB cluster"),
        (True, ([], [{"name": "host_service"}]), "graph vertices are empty"),
        (True, ([{"name": "host"}], []), "graph relations are empty"),
    ],
)
def test_sync_relation_graph_v4_dependency_failure_does_not_block_relation_sync(
    create_and_delete_records,
    create_cluster,
    definitions,
    error,
):
    table_id = "2_bkcc_built_in_time_series.__default__"
    models.ClusterInfo.objects.filter(
        bk_tenant_id="system",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        is_default_cluster=True,
    ).update(is_default_cluster=False)
    if create_cluster:
        models.ClusterInfo.objects.update_or_create(
            cluster_id=900002,
            defaults={
                "cluster_name": "default_surrealdb",
                "cluster_type": models.ClusterInfo.TYPE_SURREALDB,
                "domain_name": "surreal.service",
                "port": 8000,
                "description": "",
                "is_default_cluster": True,
                "bk_tenant_id": "system",
                "registered_to_bkbase": True,
            },
        )

    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis") as mock_hset_to_redis,
        patch("metadata.models.DataSource.apply_for_data_id_from_bkdata", return_value=50011),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch("metadata.models.TimeSeriesGroup.create_time_series_group", return_value=created_group),
        patch(
            "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
            return_value=definitions,
        ),
        patch("metadata.task.sync_cmdb_relation.logger.warning") as mock_warning,
    ):
        sync_relation_redis_data()

    assert models.DataSource.objects.get(bk_data_id=50010).token == ""
    assert models.DataSource.objects.filter(bk_data_id=50011).exists()
    assert not models.ResultTableOption.objects.filter(
        bk_tenant_id="system",
        table_id=table_id,
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
    ).exists()
    assert not models.SurrealDBStorage.objects.filter(bk_tenant_id="system", table_id=table_id).exists()
    assert [call_args.args[1] for call_args in mock_hset_to_redis.call_args_list] == ["bkcc__2", "bkcc__3"]
    assert any(error in str(arg) for call_args in mock_warning.call_args_list for arg in call_args.args)


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
    assert builtin_ds.token == ""
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3].token == "group-token"
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__2",
        '{"token":"group-token","modifyTime":"1733198214"}',
    )
    mock_refresh_consul.assert_not_called()


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
    assert builtin_ds.token == ""
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3] is None
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__2",
        f'{{"token":"{expected_token}","modifyTime":"1733198214"}}',
    )
    mock_refresh_consul.assert_not_called()


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
    assert builtin_ds.token
    assert builtin_ds.token != "created-group-token"
    token_spy.assert_called_once()
    assert token_spy.call_args.args[3] is created_group
    mock_hset_to_redis.assert_called_once_with(
        f"{settings.BUILTIN_DATA_RT_REDIS_KEY}",
        "bkcc__3",
        '{"token":"created-group-token","modifyTime":1733198214}',
    )
    mock_refresh_consul.assert_not_called()


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
    models.ResultTable.objects.create(
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=int(table_id.split("_", 1)[0]),
        is_builtin=True,
        bk_tenant_id=bk_tenant_id,
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
def test_time_series_group_create_forwards_is_sync_db(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    custom_group = Mock(
        bk_data_id=61000,
        bk_biz_id=2,
        custom_group_id=1,
        get_datasource_options=Mock(return_value=[]),
    )
    mocker.patch.object(models.TimeSeriesGroup, "pre_check", return_value={})
    mocker.patch.object(models.TimeSeriesGroup, "_create", return_value=(table_id, custom_group))
    mocker.patch.object(models.TimeSeriesGroup, "_post_process_create")
    mocker.patch.object(models.TimeSeriesGroup, "process_default_storage_config")
    mock_create_result_table = mocker.patch.object(models.ResultTable, "create_result_table")
    mocker.patch("metadata.task.tasks.refresh_custom_report_config.delay")
    mocker.patch.object(models.DataSource.objects, "get", return_value=Mock())

    models.TimeSeriesGroup.create_time_series_group(
        bk_data_id=61000,
        bk_biz_id=2,
        time_series_group_name="2_bkcc_built_in_time_series",
        label=models.Label.RESULT_TABLE_LABEL_OTHER,
        operator="system",
        table_id=table_id,
        is_builtin=True,
        bk_tenant_id="system",
        is_sync_db=False,
    )

    assert mock_create_result_table.call_args.kwargs["is_sync_db"] is False


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_v4_uses_result_table_modify(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = _create_relation_graph_source(61001, "2_bkcc_built_in_time_series", "system", table_id)
    _create_relation_graph_clusters("system")
    vertices = [{"name": "host", "id_fields": ["bk_host_id"]}]
    relations = [{"name": "host_service"}]
    models.ResultTableOption.create_option(
        table_id=table_id,
        name=models.ResultTableOption.OPTION_CMDB_LEVEL_CONFIG,
        value=["host"],
        creator="test",
        bk_tenant_id="system",
    )
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=(vertices, relations),
    )
    mock_apply = mocker.patch("metadata.models.ResultTable.apply_datalink")

    assert enable_relation_surrealdb_dual_write(data_source, "system", 2) is True
    assert enable_relation_surrealdb_dual_write(data_source, "system", 2) is False

    storage = models.SurrealDBStorage.objects.get(bk_tenant_id="system", table_id=table_id)
    assert storage.storage_cluster_id == 910101
    assert storage.table_type == models.SurrealDBStorage.TEMPORARY_TABLE_TYPE
    assert storage.vertices == vertices
    assert storage.relations == relations
    assert models.ResultTableOption.get_option(table_id) == {
        models.ResultTableOption.OPTION_CMDB_LEVEL_CONFIG: ["host"],
        models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK: {
            "write_targets": ["vm", "surrealdb"],
        },
    }
    mock_apply.assert_called_once()
    assert mock_apply.call_args.kwargs == {"force_update": True}
    assert not models.StorageClusterRecord.objects.filter(
        bk_tenant_id="system",
        table_id=table_id,
        cluster_id=910101,
    ).exists()
    assert not models.DataLink.objects.exists()


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_v4_reapplies_when_graph_definitions_change(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = _create_relation_graph_source(61004, "2_bkcc_built_in_time_series", "system", table_id)
    _create_relation_graph_clusters("system")
    query_definitions = mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=([{"name": "host"}], [{"name": "host_service"}]),
    )
    mock_apply = mocker.patch("metadata.models.ResultTable.apply_datalink")

    assert enable_relation_surrealdb_dual_write(data_source, "system", 2) is True
    models.ClusterInfo.objects.filter(cluster_id=910101).update(is_default_cluster=False)
    models.ClusterInfo.objects.create(
        cluster_id=910102,
        cluster_name="surreal-next-system",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surreal-next.service",
        port=8000,
        description="",
        is_default_cluster=True,
        bk_tenant_id="system",
        registered_to_bkbase=True,
    )
    query_definitions.return_value = (
        [{"name": "host"}, {"name": "service"}],
        [{"name": "host_service"}, {"name": "service_module"}],
    )
    assert enable_relation_surrealdb_dual_write(data_source, "system", 2) is True

    storage = models.SurrealDBStorage.objects.get(bk_tenant_id="system", table_id=table_id)
    assert storage.storage_cluster_id == 910101
    assert storage.vertices == [{"name": "host"}, {"name": "service"}]
    assert storage.relations == [{"name": "host_service"}, {"name": "service_module"}]
    assert mock_apply.call_count == 2


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_v4_updates_existing_surrealdb_storage(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = _create_relation_graph_source(61002, "2_bkcc_built_in_time_series", "system", table_id)
    _create_relation_graph_clusters("system")
    models.ClusterInfo.objects.create(
        cluster_id=910102,
        cluster_name="surreal-next-system",
        cluster_type=models.ClusterInfo.TYPE_SURREALDB,
        domain_name="surreal-next.service",
        port=8000,
        description="",
        is_default_cluster=False,
        bk_tenant_id="system",
        registered_to_bkbase=True,
    )
    models.SurrealDBStorage.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        storage_cluster_id=910101,
        table_type=models.SurrealDBStorage.NORMAL_TABLE_TYPE,
        vertices=[{"name": "old"}],
        relations=[{"name": "old_relation"}],
    )
    mocker.patch("metadata.models.ResultTable.apply_datalink")
    storage_config = {
        "storage_cluster_id": 910102,
        "table_type": models.SurrealDBStorage.TEMPORARY_TABLE_TYPE,
        "vertices": [{"name": "host"}],
        "relations": [{"name": "host_service"}],
    }

    enable_relation_surrealdb_dual_write(data_source, "system", 2, storage_config=storage_config)

    storage = models.SurrealDBStorage.objects.get(bk_tenant_id="system", table_id=table_id)
    assert storage.storage_cluster_id == 910102
    assert storage.table_type == models.SurrealDBStorage.TEMPORARY_TABLE_TYPE
    assert storage.vertices == storage_config["vertices"]
    assert storage.relations == storage_config["relations"]
    assert not models.StorageClusterRecord.objects.filter(
        bk_tenant_id="system",
        table_id=table_id,
        cluster_id__in=[910101, 910102],
    ).exists()


@pytest.mark.django_db(databases="__all__")
def test_enable_relation_graph_v4_storage_failure_rolls_back_option(mocker):
    table_id = "2_bkcc_built_in_time_series.__default__"
    data_source = _create_relation_graph_source(61003, "2_bkcc_built_in_time_series", "system", table_id)
    _create_relation_graph_clusters("system")
    models.SurrealDBStorage.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        storage_cluster_id=910101,
        table_type=models.SurrealDBStorage.NORMAL_TABLE_TYPE,
        vertices=[{"name": "old"}],
        relations=[{"name": "old_relation"}],
    )
    mock_apply = mocker.patch("metadata.models.ResultTable.apply_datalink")

    with pytest.raises(ValueError, match="SurrealDB存储集群配置有误"):
        enable_relation_surrealdb_dual_write(
            data_source,
            "system",
            2,
            storage_config={
                "storage_cluster_id": 999999,
                "table_type": models.SurrealDBStorage.TEMPORARY_TABLE_TYPE,
                "vertices": [{"name": "host"}],
                "relations": [{"name": "host_service"}],
            },
        )

    storage = models.SurrealDBStorage.objects.get(bk_tenant_id="system", table_id=table_id)
    assert storage.storage_cluster_id == 910101
    assert storage.table_type == models.SurrealDBStorage.NORMAL_TABLE_TYPE
    assert storage.vertices == [{"name": "old"}]
    assert storage.relations == [{"name": "old_relation"}]
    assert not models.ResultTableOption.objects.filter(
        bk_tenant_id="system",
        table_id=table_id,
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
    ).exists()
    mock_apply.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_relation_graph_v4_storage_config_requires_default_surrealdb_cluster():
    with pytest.raises(ValueError, match="requires exactly one default SurrealDB cluster"):
        _compose_relation_graph_v4_storage_config("system", 10, "10_bkcc_built_in_time_series.__default__")


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize(
    ("definitions", "error"),
    [
        (([], [{"name": "host_service"}]), "graph vertices are empty"),
        (([{"name": "host"}], []), "graph relations are empty"),
    ],
)
def test_relation_graph_v4_storage_config_requires_complete_graph_definitions(mocker, definitions, error):
    _create_relation_graph_clusters("system")
    mocker.patch(
        "metadata.task.sync_cmdb_relation.EntityMeta.auto_query_graph_definitions",
        return_value=definitions,
    )

    with pytest.raises(ValueError, match=error):
        _compose_relation_graph_v4_storage_config("system", 10, "10_bkcc_built_in_time_series.__default__")
