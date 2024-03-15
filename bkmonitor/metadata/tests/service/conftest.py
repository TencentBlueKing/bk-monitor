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
from metadata.tests.common_utils import CustomConsul

from ..space.conftest import consul_client

DEFAULT_TABLE_ID = "test.test"
DEFAULT_STORAGE_CLUSTER_ID = 100001
DEFAULT_PROXY_STORAGE_CLUSTER_ID = 10001
DEFAULT_NAME = "test_query"
DEFAULT_DATA_ID = 1100000
DEFAULT_BIZ_ID = 1
DEFAULT_MQ_CLUSTER_ID = 10000
DEFAULT_MQ_CONFIG_ID = 10001
DEFAULT_SPACE_TYPE = "bkcc"
DEFAULT_CREATOR = "system"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_records(mocker):
    models.InfluxDBProxyStorage.objects.create(
        id=DEFAULT_PROXY_STORAGE_CLUSTER_ID,
        proxy_cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        service_name="bkmonitorv3",
        instance_cluster_name="default",
    )
    models.InfluxDBStorage.objects.create(
        table_id=DEFAULT_TABLE_ID, storage_cluster_id=DEFAULT_STORAGE_CLUSTER_ID, influxdb_proxy_storage_id=0
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="example.com",
        port=10,
        is_default_cluster=True,
    )
    models.AccessVMRecord.objects.create(
        data_type=models.AccessVMRecord.ACCESS_VM,
        bcs_cluster_id=None,
        result_table_id=DEFAULT_TABLE_ID,
        storage_cluster_id=1,
        vm_cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        bk_base_data_id=11001,
        vm_result_table_id="test_vm_rt",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=CustomConsul)
    models.InfluxDBProxyStorage.objects.filter(id=DEFAULT_PROXY_STORAGE_CLUSTER_ID).delete()
    models.InfluxDBStorage.objects.filter(table_id=DEFAULT_TABLE_ID).delete()
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_STORAGE_CLUSTER_ID).delete()
    models.AccessVMRecord.objects.filter(result_table_id=DEFAULT_TABLE_ID).delete()


@pytest.fixture
def create_and_delete_datalink_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_NAME,
        mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
        mq_config_id=DEFAULT_MQ_CONFIG_ID,
        etl_config="test",
        is_custom_source=False,
        is_platform_data_id=False,
        space_type_id=DEFAULT_SPACE_TYPE,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID + 1,
        data_name=f"{DEFAULT_NAME}1",
        mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
        mq_config_id=DEFAULT_MQ_CONFIG_ID,
        etl_config="test",
        is_custom_source=False,
        is_platform_data_id=True,
        space_type_id=DEFAULT_SPACE_TYPE,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID + 2,
        data_name=f"{DEFAULT_NAME}2",
        mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
        mq_config_id=DEFAULT_MQ_CONFIG_ID,
        etl_config="test",
        is_custom_source=False,
        is_platform_data_id=True,
        space_type_id=DEFAULT_SPACE_TYPE,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=DEFAULT_DATA_ID, table_id=DEFAULT_TABLE_ID, creator=DEFAULT_CREATOR
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=DEFAULT_DATA_ID + 2, table_id=f"{DEFAULT_TABLE_ID}_one", creator=DEFAULT_CREATOR
    )
    models.ResultTable.objects.create(
        table_id=DEFAULT_TABLE_ID,
        table_name_zh=DEFAULT_TABLE_ID,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=DEFAULT_BIZ_ID,
    )
    models.ResultTable.objects.create(
        table_id=f"{DEFAULT_TABLE_ID}_one",
        table_name_zh=f"{DEFAULT_TABLE_ID}_one",
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=DEFAULT_BIZ_ID,
        is_enable=False,
    )
    models.DataSourceOption.objects.create(
        bk_data_id=DEFAULT_DATA_ID, name=DEFAULT_NAME, value=DEFAULT_NAME, value_type="string"
    )
    models.ResultTableOption.objects
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSourceOption.objects.filter(bk_data_id=DEFAULT_DATA_ID, name=DEFAULT_NAME).delete()
    models.ResultTable.objects.filter(table_id__in=[DEFAULT_TABLE_ID, f"{DEFAULT_TABLE_ID}_one"]).delete()
    models.DataSourceResultTable.objects.filter(bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID + 2]).delete()
    models.DataSource.objects.filter(data_name__startswith=DEFAULT_NAME).delete()
