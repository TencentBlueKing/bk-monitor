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
import json

import pytest
from django.conf import settings

from metadata import models

DEFAULT_NAME = "test_query.base"
DEFAULT_NAME_ONE = "cluster_name_one"
DEFAULT_DATA_ID = 11000
DEFAULT_DATA_ID_ONE = 110001
DEFAULT_BIZ_ID = 1
DEFAULT_MQ_CLUSTER_ID = 10000
DEFAULT_MQ_CLUSTER_ID_ONE = 10001
DEFAULT_INFLUXDB_CLUSTER_ID = 9999
DEFAULT_VM_CLUSTER_ID = 9998
DEFAULT_VM_CLUSTER_ID_ONE = 9997
DEFAULT_MQ_CONFIG_ID = 10001
DEFAULT_HOST_NAME = "default_cluster"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_table_storage():
    table_id = f"{DEFAULT_NAME}1"
    models.ESStorage.objects.create(table_id=table_id, storage_cluster_id=190000)
    yield
    models.ESStorage.objects.filter(table_id=table_id).delete()


@pytest.fixture
def create_and_delete_record(mocker):
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.ResultTable.objects.create(
        table_id=DEFAULT_NAME,
        table_name_zh=DEFAULT_NAME,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        bk_biz_id=DEFAULT_BIZ_ID,
    )
    models.ResultTableField.objects.create(
        table_id=DEFAULT_NAME,
        field_name="test_field",
        field_type="string",
        tag="dimension",
        default_value=None,
        is_config_by_user=True,
        description="test field",
        unit="",
        alias_name="test_field",
    )
    models.DataSourceResultTable.objects.create(table_id=DEFAULT_NAME, bk_data_id=DEFAULT_DATA_ID)
    kafka_topic_info = models.KafkaTopicInfo.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        topic=DEFAULT_NAME,
        partition=1,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_NAME,
        mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
        mq_config_id=kafka_topic_info.id,
        etl_config="test",
        is_custom_source=False,
    )

    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID_ONE,
        data_name=f"{DEFAULT_NAME}_1",
        mq_cluster_id=DEFAULT_MQ_CLUSTER_ID,
        mq_config_id=kafka_topic_info.id,
        etl_config="test",
        is_custom_source=False,
    )

    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_MQ_CLUSTER_ID,
        cluster_name=DEFAULT_NAME,
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name=DEFAULT_NAME,
        port=80,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_MQ_CLUSTER_ID_ONE,
        cluster_name=DEFAULT_NAME_ONE,
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name=DEFAULT_NAME,
        port=80,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_INFLUXDB_CLUSTER_ID,
        cluster_name=f"{DEFAULT_NAME}_influxdb",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name=DEFAULT_NAME,
        port=80,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_VM_CLUSTER_ID,
        cluster_name=f"{DEFAULT_NAME}_vm",
        cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
        domain_name=DEFAULT_NAME,
        port=80,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_VM_CLUSTER_ID_ONE,
        cluster_name=f"{DEFAULT_NAME}_vm_one",
        cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
        domain_name=DEFAULT_NAME,
        port=80,
        is_default_cluster=False,
    )
    models.AccessVMRecord.objects.create(
        result_table_id=DEFAULT_NAME,
        vm_cluster_id=DEFAULT_VM_CLUSTER_ID,
        bk_base_data_id=-1,
        vm_result_table_id=DEFAULT_NAME,
    )
    setattr(settings, "INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME", DEFAULT_NAME)
    models.InfluxDBClusterInfo.objects.create(
        host_name=DEFAULT_HOST_NAME,
        cluster_name=DEFAULT_NAME,
        host_readable=True,
    )
    models.InfluxDBProxyStorage.objects.create(
        proxy_cluster_id=DEFAULT_INFLUXDB_CLUSTER_ID,
        instance_cluster_name=DEFAULT_NAME,
    )
    yield
    models.ResultTable.objects.filter(table_id=DEFAULT_NAME).delete()
    models.ResultTableField.objects.filter(table_id=DEFAULT_NAME).delete()
    models.DataSourceResultTable.objects.filter(table_id=DEFAULT_NAME).delete()
    models.KafkaTopicInfo.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.DataSource.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.ClusterInfo.objects.filter(
        cluster_id__in=[
            DEFAULT_MQ_CLUSTER_ID,
            DEFAULT_INFLUXDB_CLUSTER_ID,
            DEFAULT_MQ_CLUSTER_ID_ONE,
            DEFAULT_VM_CLUSTER_ID,
            DEFAULT_VM_CLUSTER_ID_ONE,
        ]
    ).delete()
    models.InfluxDBClusterInfo.objects.filter(cluster_name=DEFAULT_NAME).delete()
    models.InfluxDBProxyStorage.objects.filter(instance_cluster_name=DEFAULT_NAME).delete()
    models.AccessVMRecord.objects.filter(result_table_id=DEFAULT_NAME).delete()


def consul_client(*args, **kwargs):
    return CustomConsul()


class CustomConsul:
    def __init__(self):
        self.kv = KV()

    def put(self, *args, **kwargs):
        pass

    def delete(self, *args, **kwargs):
        pass


class KV:
    def delete(self, *args, **kwargs):
        return True

    def get(self, *args, **kwargs):
        return [{"Value": json.dumps({"value": "test"})}, {"Value": json.dumps({"value": "test1"})}]

    def put(self, *args, **kwargs):
        return True
