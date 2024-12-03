# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from unittest.mock import call, patch

import pytest
from django.conf import settings

from bkmonitor.utils.cipher import transform_data_id_to_token
from metadata import models
from metadata.task.sync_cmdb_relation import sync_relation_redis_data
from metadata.tests.common_utils import consul_client

mock_redis_hgetall_return_value = {
    b'bkcc__2': b'{"token":"testtokenxxxxxx","modifyTime":"1733132051"}',
    b'bkcc__3': b'{"token":""}',
}


@pytest.fixture
def create_and_delete_records(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
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
        topic='test_50010',
        partition=0,
    )
    models.ResultTable.objects.create(
        table_id='2_bkcc_built_in_time_series.__default__',
        table_name_zh='2_bkcc_built_in_time_series.__default__',
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


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_sync_relation_redis_data(create_and_delete_records):
    """
    测试验证 CMDB Relation同步任务能否正确工作
    1. Token和DB中不一致，更新并回写
    2. 不存在对应内置RT和数据源，创建之
    """
    with patch('metadata.utils.redis_tools.RedisTools.hgetall', return_value=mock_redis_hgetall_return_value), patch(
        'metadata.utils.redis_tools.RedisTools.hset_to_redis', return_value=0
    ) as mock_hset_to_redis, patch("metadata.models.DataSource.apply_for_data_id_from_gse", return_value=50011), patch(
        "time.time", return_value=1733198214
    ), patch(
        "metadata.models.TimeSeriesGroup.create_time_series_group", return_value=models.TimeSeriesGroup.objects.first()
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
        expected_bkcc_3_timestamp = int(models.TimeSeriesGroup.objects.first().last_modify_time.timestamp())

        expected_calls = [
            call(
                f'{settings.BUILTIN_DATA_RT_REDIS_KEY}',
                'bkcc__2',
                f'{{"token":"{bkcc_2_expected_token}","modifyTime":"1733198214"}}',
            ),
            call(
                f'{settings.BUILTIN_DATA_RT_REDIS_KEY}',
                'bkcc__3',
                f'{{"token":"{bkcc_3_expected_token}","modifyTime":{expected_bkcc_3_timestamp}}}',
            ),
        ]
        assert mock_hset_to_redis.call_args_list == expected_calls
