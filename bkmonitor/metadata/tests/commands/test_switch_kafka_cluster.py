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
from django.core.management import CommandError, call_command

from metadata import models
from metadata.tests.common_utils import consul_client

from .conftest import DEFAULT_DATA_ID

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_or_delete_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="data_link_test2",
        mq_cluster_id=2,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=50010,
        table_id="test_50010",
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=50011,
        table_id="test_50011",
    )
    models.KafkaStorage.objects.create(
        table_id='test_50010',
        storage_cluster_id=1,
        topic="test_topic",
    )
    models.KafkaStorage.objects.create(
        table_id='test_50011',
        storage_cluster_id=1,
        topic="test_topic1",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.KafkaStorage.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_failed_switch_kafka_cluster(create_and_delete_record):
    """
    测试变更Kafka失败
    """
    # 不传递参数
    with pytest.raises(CommandError):
        call_command("switch_kafka_for_data_id")

    # 传递错误参数
    with pytest.raises(CommandError):
        call_command("switch_kafka_for_data_id", "--data_ids=-1")
    with pytest.raises(CommandError):
        call_command(
            "switch_kafka_for_data_id", f"--data_ids={DEFAULT_DATA_ID}", "--kafka_cluster_id=-1", "--kind=frontend"
        )


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_switch_frontend_kafka_cluster(create_or_delete_records, mocker):
    """
    测试变更前端Kafka
    """
    mocker.patch("metadata.models.DataSource.refresh_outer_config", return_value=True)

    # 测试批量
    call_command("switch_kafka_for_data_id", "--data_ids", "50010", "50011", "--kafka_cluster_id=2", "--kind=frontend")

    assert models.DataSource.objects.get(bk_data_id=50010).mq_cluster_id == 2
    assert models.DataSource.objects.get(bk_data_id=50011).mq_cluster_id == 2

    # 测试单个切换
    call_command("switch_kafka_for_data_id", "--data_ids", "50010", "--kafka_cluster_id=3", "--kind=frontend")
    assert models.DataSource.objects.get(bk_data_id=50010).mq_cluster_id == 3


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_switch_backend_kafka_cluster(create_or_delete_records, mocker):
    mocker.patch("metadata.models.DataSource.refresh_outer_config", return_value=True)
    # 测试批量
    call_command("switch_kafka_for_data_id", "--data_ids", "50010", "50011", "--kafka_cluster_id=3", "--kind=backend")

    assert models.KafkaStorage.objects.get(table_id='test_50010').storage_cluster_id == 3
    assert models.DataSource.objects.get(bk_data_id=50010).mq_cluster_id == 1

    assert models.KafkaStorage.objects.get(table_id='test_50011').storage_cluster_id == 3
    assert models.DataSource.objects.get(bk_data_id=50011).mq_cluster_id == 2

    # 测试单个
    call_command("switch_kafka_for_data_id", "--data_ids", "50010", "--kafka_cluster_id=1", "--kind=backend")

    assert models.KafkaStorage.objects.get(table_id='test_50010').storage_cluster_id == 1
    assert models.DataSource.objects.get(bk_data_id=50010).mq_cluster_id == 1
