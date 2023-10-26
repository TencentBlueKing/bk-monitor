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
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db

DEFAULT_NAME = "test_query"
DEFAULT_DATA_ID = 11000
DEFAULT_BIZ_ID = 1
DEFAULT_MQ_CLUSTER_ID = 10000
DEFAULT_MQ_CONFIG_ID = 10001
DEFAULT_CREATOR = "system"
DEFAULT_TABLE_ID = "test.query"
DEFAULT_TABLE_ID_LIST = ["test.query", "test.query1", "test.query2"]


@pytest.fixture
def create_or_delete_records(mocker):
    params = [
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID,
            data_name=DEFAULT_NAME,
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=False,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID + 1,
            data_name=f"{DEFAULT_NAME}1",
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=True,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID + 2,
            data_name=f"{DEFAULT_NAME}_2",
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=True,
        ),
    ]
    models.DataSource.objects.bulk_create(params)

    rt_params = [
        models.ResultTable(
            table_id=DEFAULT_TABLE_ID,
            table_name_zh=DEFAULT_TABLE_ID,
            is_custom_table=True,
            creator=DEFAULT_CREATOR,
            bk_biz_id=DEFAULT_BIZ_ID,
        ),
        models.ResultTable(
            table_id=f"{DEFAULT_TABLE_ID}1",
            table_name_zh=f"{DEFAULT_TABLE_ID}1",
            is_custom_table=True,
            creator=DEFAULT_CREATOR,
        ),
        models.ResultTable(
            table_id=f"{DEFAULT_TABLE_ID}2",
            table_name_zh=f"{DEFAULT_TABLE_ID}2",
            is_custom_table=True,
            creator=DEFAULT_CREATOR,
        ),
    ]
    models.ResultTable.objects.bulk_create(rt_params)

    ds_rt_params = [
        models.DataSourceResultTable(
            bk_data_id=DEFAULT_DATA_ID,
            table_id=DEFAULT_TABLE_ID,
            creator=DEFAULT_CREATOR,
        ),
        models.DataSourceResultTable(
            bk_data_id=DEFAULT_DATA_ID + 1,
            table_id=f"{DEFAULT_TABLE_ID}1",
            creator=DEFAULT_CREATOR,
        ),
        models.DataSourceResultTable(
            bk_data_id=DEFAULT_DATA_ID + 2,
            table_id=f"{DEFAULT_TABLE_ID}2",
            creator=DEFAULT_CREATOR,
        ),
    ]
    models.DataSourceResultTable.objects.bulk_create(ds_rt_params)

    influxdb_router_params = [
        models.InfluxDBStorage(
            table_id=DEFAULT_TABLE_ID,
            storage_cluster_id=1,
            real_table_name="query",
            database="test",
            proxy_cluster_name="default",
        ),
        models.InfluxDBStorage(
            table_id=f"{DEFAULT_TABLE_ID}1",
            storage_cluster_id=1,
            real_table_name="query1",
            database="test",
            proxy_cluster_name="default",
        ),
        models.InfluxDBStorage(
            table_id=f"{DEFAULT_TABLE_ID}2",
            storage_cluster_id=1,
            real_table_name="query2",
            database="test",
            proxy_cluster_name="default",
        ),
    ]
    models.InfluxDBStorage.objects.bulk_create(influxdb_router_params)

    models.EventGroup.objects.create(bk_data_id=DEFAULT_DATA_ID + 2, bk_biz_id=0)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(data_name__startswith=DEFAULT_NAME).delete()
    models.DataSourceResultTable.objects.filter(table_id__startswith=DEFAULT_TABLE_ID).delete()
    models.ResultTable.objects.filter(table_id__startswith=DEFAULT_TABLE_ID).delete()
    models.InfluxDBStorage.objects.filter(table_id__startswith=DEFAULT_TABLE_ID).delete()
    models.EventGroup.objects.filter(bk_data_id=DEFAULT_DATA_ID + 2, bk_biz_id=0).delete()


def test_get_table_info_by_table_ids(create_or_delete_records):
    table_info = models.InfluxDBStorage._get_table_info_by_table_ids(DEFAULT_TABLE_ID_LIST)
    assert set(table_info.keys()) == set(DEFAULT_TABLE_ID_LIST)
    # 校验字段存在
    val = table_info[DEFAULT_TABLE_ID_LIST[0]]
    assert set(val.keys()) == {"table_id", "schema_type", "bk_biz_id"}


def test_get_data_source_by_table_ids(create_or_delete_records):
    data_source = models.InfluxDBStorage._get_data_source_by_table_ids(DEFAULT_TABLE_ID_LIST)
    assert set(data_source.keys()) == set(DEFAULT_TABLE_ID_LIST)
    # 校验字段存在
    val = data_source[DEFAULT_TABLE_ID_LIST[0]]
    assert set(val.keys()) == {"data_id", "data_name", "space_uid"}
    # 校验返回的数据源 ID 类型为字符串
    assert isinstance(data_source[DEFAULT_TABLE_ID_LIST[0]]["data_id"], str)


def test_get_biz_id_by_table_ids(create_or_delete_records):
    table_id_map = models.InfluxDBStorage._get_table_info_by_table_ids(DEFAULT_TABLE_ID_LIST)
    table_id_data_source_map = models.InfluxDBStorage._get_data_source_by_table_ids(DEFAULT_TABLE_ID_LIST)
    table_id_biz_id_map = models.InfluxDBStorage._get_biz_id_by_table_ids(table_id_map, table_id_data_source_map)
    assert table_id_biz_id_map[DEFAULT_TABLE_ID] == "1"
    assert table_id_biz_id_map[f"{DEFAULT_TABLE_ID}1"] == "0"
    assert table_id_biz_id_map[f"{DEFAULT_TABLE_ID}2"] == "2"
