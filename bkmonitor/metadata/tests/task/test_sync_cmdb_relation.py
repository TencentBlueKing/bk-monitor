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
    mocker.patch("metadata.models.data_source.api.bkdata.apply_data_link", return_value=None)
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
        patch("metadata.models.DataSource.apply_for_data_id_from_gse", return_value=50011),
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
@override_settings(GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=[3])
def test_sync_relation_redis_data_skips_missing_rt_with_existing_redis_token(create_and_delete_records):
    redis_data = {b"bkcc__3": b'{"token":"existing-token","modifyTime":"1733132051"}'}
    with (
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=redis_data),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis") as mock_hset_to_redis,
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.create_data_source") as mock_create_data_source,
        patch("metadata.models.TimeSeriesGroup.create_time_series_group") as mock_create_group,
        patch("metadata.task.sync_cmdb_relation.logger.warning") as mock_warning,
    ):
        sync_relation_redis_data()

    mock_create_data_source.assert_not_called()
    mock_create_group.assert_not_called()
    mock_hset_to_redis.assert_not_called()
    assert any(
        "result table is missing but redis token exists" in call_args.args[0]
        for call_args in mock_warning.call_args_list
    )


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("query_biz_ids", [[], [2, 3]])
@pytest.mark.parametrize("old_biz_ids", [[], [2, 3]])
def test_query_rollout_does_not_provision_dual_write(create_and_delete_records, query_biz_ids, old_biz_ids):
    created_group = Mock(token="", last_modify_time=datetime.fromtimestamp(1733198214, tz=timezone.utc))
    with (
        override_settings(
            RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST=query_biz_ids,
            GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=old_biz_ids,
        ),
        patch("metadata.utils.redis_tools.RedisTools.hgetall", return_value=mock_redis_hgetall_return_value),
        patch("metadata.utils.redis_tools.RedisTools.hset_to_redis", return_value=0),
        patch("metadata.models.DataSource.apply_for_data_id_from_gse", return_value=50011),
        patch("time.time", return_value=1733198214),
        patch("metadata.task.sync_cmdb_relation.metrics.report_all", return_value=None),
        patch("metadata.models.DataSource.refresh_consul_config", autospec=True),
        patch(
            "metadata.models.TimeSeriesGroup.create_time_series_group",
            return_value=created_group,
        ) as mock_create_group,
        patch("metadata.models.ResultTable.modify", autospec=True) as mock_modify,
    ):
        sync_relation_redis_data()

    mock_create_group.assert_called_once()
    assert mock_create_group.call_args.kwargs["is_sync_db"] is True
    mock_modify.assert_not_called()
    assert not models.SurrealDBStorage.objects.exists()
    assert not models.ResultTableOption.objects.filter(
        name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
    ).exists()
    assert not models.DataLink.objects.filter(data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES).exists()


@pytest.mark.django_db(databases="__all__")
@override_settings(RELATION_QUERY_V1BETA3_BIZ_ID_WHITE_LIST=[2], GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=[2])
def test_sync_relation_redis_data_preserves_existing_storage(create_and_delete_records):
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
        patch("metadata.models.ResultTable.modify", autospec=True) as mock_modify,
    ):
        sync_relation_redis_data()

    mock_modify.assert_not_called()
    storage = models.SurrealDBStorage.objects.get(bk_tenant_id="system", table_id=table_id)
    for name, value in storage_config.items():
        assert getattr(storage, name) == value
    option = models.ResultTableOption.objects.get(
        bk_tenant_id="system", table_id=table_id, name=models.ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK
    )
    assert option.get_value() == {"write_targets": ["vm", "surrealdb"]}


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
        patch("metadata.models.DataSource.apply_for_data_id_from_gse", return_value=50011),
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
