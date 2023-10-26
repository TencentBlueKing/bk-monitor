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

from metadata import models
from metadata.tests.common_utils import generate_random_string

DEFAULT_PIPELINE_NAME = "test_demo"
DEFAULT_PIPELINE_NAME_ONE = "test_demo_one"
DEFAULT_TRANSFER_CLUSTER_ID = "transfer_demo"
DEFAULT_KAFKA_CLUSTER_NAME = "kafka_demo"
DEFAULT_INFLUXDB_CLUSTER_NAME = "influxdb_demo"
DEFAULT_BK_DATA_ID = 1
DEFAULT_BK_DATA_ID_ONE = 2
DEFAULT_SPACE = {"space_type": "bkcc", "space_id": "1"}
DEFAULT_ETL_CONFIG = "test"
DEFAULT_KAFKA_CLUSTER_ID = 100
DEFAULT_INFLUXDB_CLUSTER_ID = 101

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_or_delete_records():
    models.DataPipeline.objects.create(
        name=DEFAULT_PIPELINE_NAME,
        chinese_name=DEFAULT_PIPELINE_NAME,
        kafka_cluster_id=100,
        transfer_cluster_id=DEFAULT_TRANSFER_CLUSTER_ID,
        influxdb_storage_cluster_id=101,
    )
    models.DataPipeline.objects.create(
        name=DEFAULT_PIPELINE_NAME_ONE,
        chinese_name=DEFAULT_PIPELINE_NAME_ONE,
        kafka_cluster_id=100,
        transfer_cluster_id=DEFAULT_TRANSFER_CLUSTER_ID,
        influxdb_storage_cluster_id=101,
    )
    models.DataPipelineDataSource.objects.create(
        data_pipeline_name=DEFAULT_PIPELINE_NAME, bk_data_id=DEFAULT_BK_DATA_ID
    )
    models.DataPipelineDataSource.objects.create(
        data_pipeline_name=DEFAULT_PIPELINE_NAME_ONE, bk_data_id=DEFAULT_BK_DATA_ID_ONE
    )
    models.DataPipelineEtlConfig.objects.create(
        data_pipeline_name=DEFAULT_PIPELINE_NAME,
        etl_config=DEFAULT_ETL_CONFIG,
    )
    models.DataPipelineEtlConfig.objects.create(
        data_pipeline_name=DEFAULT_PIPELINE_NAME_ONE,
        etl_config=DEFAULT_ETL_CONFIG,
    )
    models.DataPipelineSpace.objects.create(data_pipeline_name=DEFAULT_PIPELINE_NAME, is_default=True, **DEFAULT_SPACE)
    models.DataPipelineSpace.objects.create(data_pipeline_name=DEFAULT_PIPELINE_NAME_ONE, **DEFAULT_SPACE)

    params = [
        models.ClusterInfo(
            cluster_id=DEFAULT_KAFKA_CLUSTER_ID,
            cluster_name=DEFAULT_KAFKA_CLUSTER_NAME,
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
            port="80",
            is_default_cluster=False,
        ),
        models.ClusterInfo(
            cluster_id=DEFAULT_INFLUXDB_CLUSTER_ID,
            cluster_name=DEFAULT_INFLUXDB_CLUSTER_NAME,
            cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
            port="80",
            is_default_cluster=False,
        ),
    ]
    models.ClusterInfo.objects.bulk_create(params)
    yield
    models.DataPipeline.objects.all().delete()
    models.ClusterInfo.objects.filter(cluster_id__in=[DEFAULT_KAFKA_CLUSTER_ID, DEFAULT_INFLUXDB_CLUSTER_ID]).delete()
    models.DataPipelineDataSource.objects.all().delete()
    models.DataPipelineEtlConfig.objects.all().delete()
    models.DataPipelineSpace.objects.all().delete()


def test_filter_data(create_or_delete_records):
    data = models.DataPipeline.filter_data()
    # 校验数据
    assert data["total"] == 2
    assert len(data["data"]) == 2
    # 校验返回的详细信息
    record = data["data"][0]
    assert record["name"] == DEFAULT_PIPELINE_NAME_ONE
    assert len(record["spaces"]) == 1
    assert len(record["etl_config"]) == 1


def test_filter_data_with_page(create_or_delete_records):
    data = models.DataPipeline.filter_data(page_size=1)
    # 校验基本数据
    assert data["total"] == 2
    assert len(data["data"]) == 1


def test_check_exist_default(create_or_delete_records):
    assert models.DataPipeline.check_exist_default(spaces=[DEFAULT_SPACE], etl_configs=[DEFAULT_ETL_CONFIG])


def test_create_records(create_or_delete_records, mocker):
    default_name = generate_random_string()
    etl_config = generate_random_string()
    params = {
        "name": default_name,
        "etl_configs": [etl_config],
        "spaces": [{"space_type": "bkci", "space_id": "test_dev"}],
        "kafka_cluster_id": DEFAULT_KAFKA_CLUSTER_ID,
        "transfer_cluster_id": DEFAULT_TRANSFER_CLUSTER_ID,
        "influxdb_storage_cluster_id": DEFAULT_INFLUXDB_CLUSTER_ID,
        "creator": "admin",
    }
    mocker.patch("metadata.models.data_pipeline.utils.check_transfer_cluster_exist", return_value=True)

    # 测试可以创建成功
    models.DataPipeline.create_record(**params)
    assert models.DataPipeline.objects.filter(name=default_name).exists()

    # 测试创建失败回滚
    params = {
        "name": DEFAULT_PIPELINE_NAME,
        "etl_configs": [etl_config],
        "spaces": [{"space_type": "bkci", "space_id": "test_dev"}],
        "kafka_cluster_id": DEFAULT_KAFKA_CLUSTER_ID,
        "transfer_cluster_id": DEFAULT_TRANSFER_CLUSTER_ID,
        "influxdb_storage_cluster_id": DEFAULT_INFLUXDB_CLUSTER_ID,
    }
    with pytest.raises(Exception):
        models.DataPipeline.create_record(**params)


def test_update_record(create_or_delete_records):
    # 更新描述信息
    default_description = "this is a test"
    params = {"name": DEFAULT_PIPELINE_NAME, "description": default_description, "updater": "admin"}

    data = models.DataPipeline.update_record(**params)
    assert data["description"] == default_description
    # 校验空间信息
    assert data["spaces"][0]["space_id"] == DEFAULT_SPACE["space_id"]
    # 校验使用场景
    assert data["etl_config"][0]["etl_config"] == DEFAULT_ETL_CONFIG

    # 调整默认管道
    assert (
        models.DataPipelineSpace.objects.get(data_pipeline_name=DEFAULT_PIPELINE_NAME, **DEFAULT_SPACE).is_default
        is True
    )
    params = {"name": DEFAULT_PIPELINE_NAME, "spaces": [DEFAULT_SPACE], "is_default": False, "updater": "admin"}
    data = models.DataPipeline.update_record(**params)
    assert data["spaces"][0]["is_default"] is False
