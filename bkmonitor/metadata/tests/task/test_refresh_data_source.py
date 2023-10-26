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

import pytest
from mockredis import mock_redis_client

from metadata.tests.common_utils import generate_random_string

pytestmark = pytest.mark.django_db

DEFAULT_DATA_ID = 100001
DEFAULT_DATA_ID_ONE = 100002
DEFAULT_DATA_NAME = generate_random_string(5)
DEFAULT_DATA_NAME_ONE = generate_random_string(5)


@pytest.fixture
def create_and_delete_record(username, table_id, mocker):
    from metadata import models

    all_dsrt = list(models.DataSourceResultTable.objects.all())
    models.DataSourceResultTable.objects.all().delete()
    models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID, table_id=table_id, creator=username)
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_DATA_NAME,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
        is_platform_data_id=True,
        space_type_id="bkcc",
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID_ONE,
        data_name=DEFAULT_DATA_NAME_ONE,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
        etl_config="bk_system_basereport",
        is_platform_data_id=True,
        space_type_id="bkcc",
    )
    models.KafkaTopicInfo.objects.create(bk_data_id=DEFAULT_DATA_ID, topic=DEFAULT_DATA_NAME, partition=1)
    yield
    models.DataSourceResultTable.objects.all().delete()
    models.DataSourceResultTable.objects.bulk_create(all_dsrt)
    from metadata.tests.conftest import HashConsulMocker

    mock_hash_consul = HashConsulMocker()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=mock_hash_consul)
    models.DataSource.objects.filter(bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID_ONE]).delete()
    models.KafkaTopicInfo.objects.filter(bk_data_id=DEFAULT_DATA_ID, topic=DEFAULT_DATA_NAME).delete()


def test_refresh_datasource(create_and_delete_record, mocker):
    from metadata.tests.conftest import HashConsulMocker

    mock_hash_consul = HashConsulMocker()
    mocker.patch("metadata.utils.consul_tools.HashConsul", return_value=mock_hash_consul)
    mocker.patch("metadata.models.data_source.DataSource.refresh_gse_config", return_value=True)

    from metadata.task.config_refresh import refresh_datasource

    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=mock_redis_client())
    refresh_datasource()

    data = list(mock_hash_consul.result_list.values())
    assert len(data) == 1
    assert data[0]["bk_data_id"] == DEFAULT_DATA_ID
