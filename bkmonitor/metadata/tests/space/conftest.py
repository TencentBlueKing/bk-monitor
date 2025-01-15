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

DEFAULT_NAME = "test_query"
DEFAULT_DATA_ID = 11000
DEFAULT_BIZ_ID = 1
DEFAULT_MQ_CLUSTER_ID = 10000
DEFAULT_MQ_CONFIG_ID = 10001
DEFAULT_SPACE_TYPE = "bkcc"
DEFAULT_SPACE_ID = "test"
DEFAULT_SPACE_ID_ONE = "test1"
DEFAULT_OTHER_SPACE_ID = "other"
DEFAULT_TABLE_ID = "demo.test"
DEFAULT_CREATOR = "system"
DEFAULT_BCS_CLUSTER_ID_ONE = "BCS-K8S-10001"
DEFAULT_BCS_CLUSTER_ID_TWO = "BCS-K8S-10002"
DEFAULT_K8S_METRIC_DATA_ID_ONE = 101010
DEFAULT_K8S_METRIC_DATA_ID_TWO = 101011
DEFAULT_LOG_ES_TABLE_ID = "space_1_bklog.stag_20"
DEFAULT_EVENT_ES_TABLE_ID = "bkmonitor_event_1"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_record(mocker):
    # 创建三条记录
    # - 普通的 data id
    # - 空间级的 data id
    # - 全空间的 data id
    params = [
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID,
            data_name=DEFAULT_NAME,
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=False,
            space_type_id=DEFAULT_SPACE_TYPE,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID + 1,
            data_name=f"{DEFAULT_NAME}1",
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=True,
            space_type_id=DEFAULT_SPACE_TYPE,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID + 2,
            data_name=f"{DEFAULT_NAME}2",
            mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
            mq_config_id=DEFAULT_MQ_CONFIG_ID,
            etl_config="test",
            is_custom_source=False,
            is_platform_data_id=True,
            space_type_id="all",
        ),
    ]
    models.DataSourceResultTable.objects.create(
        bk_data_id=DEFAULT_DATA_ID, table_id=DEFAULT_TABLE_ID, creator=DEFAULT_CREATOR
    )
    models.ResultTable.objects.create(
        table_id=DEFAULT_TABLE_ID,
        table_name_zh=DEFAULT_TABLE_ID,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=DEFAULT_BIZ_ID,
    )
    models.DataSource.objects.bulk_create(params)
    models.SpaceDataSource.objects.create(
        space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, bk_data_id=DEFAULT_DATA_ID
    )
    models.SpaceDataSource.objects.create(
        space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, bk_data_id=DEFAULT_DATA_ID + 1
    )
    models.Space.objects.create(space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, space_name="")
    models.SpaceResource.objects.create(
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        resource_type=DEFAULT_SPACE_TYPE,
        resource_id=DEFAULT_SPACE_ID,
    )
    models.SpaceResource.objects.create(
        space_type_id=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
        resource_type=DEFAULT_SPACE_TYPE,
        resource_id=DEFAULT_SPACE_ID_ONE,
    )
    models.InfluxDBStorage.objects.create(
        table_id=DEFAULT_TABLE_ID,
        storage_cluster_id=1,
        influxdb_proxy_storage_id=1,
        database="demo",
        real_table_name="test",
    )
    models.InfluxDBProxyStorage.objects.create(
        id=1, instance_cluster_name="test_cluster", is_default=True, proxy_cluster_id=1
    )
    models.BCSClusterInfo.objects.create(
        cluster_id=DEFAULT_BCS_CLUSTER_ID_ONE,
        bcs_api_cluster_id=DEFAULT_BCS_CLUSTER_ID_ONE,
        bk_biz_id=DEFAULT_BIZ_ID,
        project_id="test",
        domain_name="test",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=DEFAULT_K8S_METRIC_DATA_ID_ONE,
    )
    models.BCSClusterInfo.objects.create(
        cluster_id=DEFAULT_BCS_CLUSTER_ID_TWO,
        bcs_api_cluster_id=DEFAULT_BCS_CLUSTER_ID_TWO,
        bk_biz_id=DEFAULT_BIZ_ID,
        project_id="test",
        domain_name="test",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=DEFAULT_K8S_METRIC_DATA_ID_TWO,
    )
    models.ESStorage.objects.create(table_id=DEFAULT_LOG_ES_TABLE_ID, storage_cluster_id=1)
    models.ESStorage.objects.create(table_id=DEFAULT_EVENT_ES_TABLE_ID, storage_cluster_id=1)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(data_name__startswith=DEFAULT_NAME).delete()
    models.SpaceDataSource.objects.all().delete()
    models.ResultTable.objects.filter(table_id=DEFAULT_TABLE_ID).delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.InfluxDBStorage.objects.filter(table_id=DEFAULT_TABLE_ID).delete()
    models.InfluxDBProxyStorage.objects.filter(id=1).delete()
    models.BCSClusterInfo.objects.filter(
        cluster_id__in=[DEFAULT_BCS_CLUSTER_ID_ONE, DEFAULT_BCS_CLUSTER_ID_TWO]
    ).delete()
    models.SpaceResource.objects.filter(space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID).delete()
    models.ESStorage.objects.filter(table_id__in=[DEFAULT_LOG_ES_TABLE_ID, DEFAULT_EVENT_ES_TABLE_ID]).delete()


def consul_client(*args, **kwargs):
    return CustomConsul()


class CustomConsul:
    def __init__(self):
        self.kv = KVDelete()


class KVDelete:
    def delete(self, *args, **kwargs):
        return True
