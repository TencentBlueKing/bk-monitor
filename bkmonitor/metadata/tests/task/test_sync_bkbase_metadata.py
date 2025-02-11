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
from unittest.mock import patch

import pytest

from metadata import models
from metadata.task.tasks import sync_bkbase_v4_metadata
from metadata.tests.common_utils import consul_client

# 定义 Mock 的 Redis hgetall 返回值
redis_value_for_metric_when_cluster_not_exists = {
    b'bkmonitor_test_result_metric_table': json.dumps(
        {
            "kafka": {
                "host": "test.kafka.db",
                "port": 9092,
                "auth": None,
                "topic": "bkm_test_metric_topic",
                "partitions": 1,
            },
            "vm": {
                "namespace": "test_ns",
                "name": "test_vm",
                "insert_host": "insert_host.test",
                "select_host": "select_host.test",
                "select_port": 80,
            },
        }
    ).encode('utf-8')
}

redis_value_for_metric_when_cluster_exists = {
    b'bkmonitor_test_result_metric_table': json.dumps(
        {
            "kafka": {
                "host": "test2.kafka.db",
                "port": 9092,
                "auth": None,
                "topic": "bkm_test2_metric_topic",
                "partitions": 3,
            },
            "vm": {
                "namespace": "test_ns",
                "name": "test_vm",
                "insert_host": "insert_host.test",
                "select_host": "select_host.test",
                "select_port": 80,
            },
        }
    ).encode('utf-8')
}

# 测试数据
es_info = [
    {
        "host": "test.es.db",
        "port": 9200,
        "user": "admin",
        "password": "password",
        "update_time": '2025-02-07 11:14:21.784665876 UTC',
    },
    {
        "host": "test2.es.db",
        "port": 9200,
        "user": "admin",
        "password": "password",
        "update_time": '2025-02-09 11:14:21.784665876 UTC',
    },
]

# Mock redis value
redis_value_for_log = {
    b'bkmonitor_test_result_log_table': json.dumps(
        {
            "kafka": {
                "host": "test2.kafka.db",
                "port": 9092,
                "auth": None,
                "topic": "bkm_test_log_topic",
                "partitions": 6,
            },
            "es": es_info,
        }
    ).encode('utf-8')
}


@pytest.fixture
def create_or_delete_records(mocker):
    # Case1. （指标链路） Kafka集群不存在 + VM集群不存在
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from='bkdata',
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_data_id=50010
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_result_table_id="vm_test_metric_1",
        bk_base_data_id=10010,
    )

    # Case2.Kafka集群变更 + Topic变更 + VM集群变更
    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="data_link_test_metric_2",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from='bkdata',
    )
    models.KafkaTopicInfo.objects.create(
        bk_data_id=50011,
        topic="bkm_topic",
        partition=1,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__", bk_data_id=50011
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50011.__default__",
        vm_result_table_id="vm_test_metric_1",
        vm_cluster_id=2,
        bk_base_data_id=10011,
    )
    models.ClusterInfo.objects.create(
        domain_name='test2.kafka.db',
        cluster_name='test2',
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        port=9092,
        is_default_cluster=False,
    )

    # Case3.（日志链路） Kafka集群变更 + ES集群变更
    models.DataSource.objects.create(
        bk_data_id=60010,
        data_name="data_link_test_log",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from='bkdata',
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_log_60010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(table_id="1001_bkmonitor_log_60010.__default__", bk_data_id=60010)
    models.KafkaTopicInfo.objects.create(
        bk_data_id=60010,
        topic="bkm_topic",
        partition=1,
    )
    models.ESStorage.objects.create(
        table_id="1001_bkmonitor_log_60010.__default__",
        storage_cluster_id=1,
    )
    models.ClusterInfo.objects.create(
        domain_name='test.es.db',
        cluster_name='testes',
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        domain_name='test2.es.db',
        cluster_name='testes2',
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=False,
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bkmonitor_log_60010.__default__",
        cluster_id=1000,
        is_deleted=False,
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ClusterInfo.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_sync_bkbase_v4_metadata_for_metric(create_or_delete_records, mocker):
    """
    测试计算平台元数据同步更新能力 -- 指标链路
    Case1. Kafka集群不存在 + VM集群不存在
    Case2. Kafka集群变更 + Topic变更 + VM集群变更
    """

    mocker.patch('django.conf.settings.ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE', True)
    mocker.patch('django.conf.settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB', True)

    # Case1. Kafka集群不存在 + VM集群不存在
    with patch(
        "redis.StrictRedis.hgetall", return_value=redis_value_for_metric_when_cluster_not_exists
    ) as mock_hgetall:  # noqa
        # 定义测试输入
        key = "databus_v4_dataid:50010"

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=50010)
        kafka_cluster_new = models.ClusterInfo.objects.get(domain_name='test.kafka.db')
        vm_cluster_new = models.ClusterInfo.objects.get(domain_name='select_host.test')
        mq_config = models.KafkaTopicInfo.objects.get(bk_data_id=50010)
        vm_record = models.AccessVMRecord.objects.get(result_table_id="1001_bkmonitor_time_series_50010.__default__")

        assert ds.mq_cluster_id == kafka_cluster_new.cluster_id
        assert ds.mq_config_id == mq_config.id
        assert vm_record.vm_cluster_id == vm_cluster_new.cluster_id

    with patch(
        "redis.StrictRedis.hgetall", return_value=redis_value_for_metric_when_cluster_exists
    ) as mock_hgetall:  # noqa
        key = "databus_v4_dataid:50011"

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=50011)
        kafka_cluster_new = models.ClusterInfo.objects.get(domain_name='test2.kafka.db')
        vm_cluster_new = models.ClusterInfo.objects.get(domain_name='select_host.test')
        mq_config = models.KafkaTopicInfo.objects.get(bk_data_id=50011)
        vm_record = models.AccessVMRecord.objects.get(result_table_id="1001_bkmonitor_time_series_50011.__default__")

        assert ds.mq_cluster_id == kafka_cluster_new.cluster_id
        assert ds.mq_config_id == mq_config.id
        assert vm_record.vm_cluster_id == vm_cluster_new.cluster_id
        assert mq_config.partition == 3
        assert mq_config.topic == "bkm_test2_metric_topic"


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_sync_bkbase_v4_metadata_for_log(create_or_delete_records, mocker):
    """
    测试计算平台元数据同步更新能力 -- 日志链路
    Case. Kafka集群变更+ES集群变更
    """
    # Case1. Kafka集群不存在 + VM集群不存在
    with patch("redis.StrictRedis.hgetall", return_value=redis_value_for_log) as mock_hgetall:  # noqa
        # 定义测试输入
        key = "databus_v4_dataid:60010"
        table_id = '1001_bkmonitor_log_60010.__default__'

        mocker.patch('django.conf.settings.ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE', True)
        mocker.patch('django.conf.settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB', True)

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=60010)
        kafka_cluster = models.ClusterInfo.objects.get(domain_name='test2.kafka.db')
        es_cluster = models.ClusterInfo.objects.get(domain_name='test.es.db')
        es_cluster2 = models.ClusterInfo.objects.get(domain_name='test2.es.db')
        mq_config = models.KafkaTopicInfo.objects.get(bk_data_id=60010)
        es_storage = models.ESStorage.objects.get(table_id=table_id)

        assert ds.mq_cluster_id == kafka_cluster.cluster_id
        assert ds.mq_config_id == mq_config.id
        assert es_storage.storage_cluster_id == es_cluster2.cluster_id
        assert mq_config.partition == 6
        assert mq_config.topic == "bkm_test_log_topic"

        # 验证StorageClusterRecord记录是否被正确同步
        cluster_records = models.StorageClusterRecord.objects.filter(table_id=table_id, is_deleted=False)
        assert cluster_records.count() == 2  # 确保有2个集群记录

        current_record = models.StorageClusterRecord.objects.get(is_current=True, table_id=table_id)
        assert current_record.cluster_id == es_cluster2.cluster_id

        old_record = models.StorageClusterRecord.objects.get(table_id=table_id, cluster_id=es_cluster.cluster_id)
        assert not old_record.is_current

        deleted_record = models.StorageClusterRecord.objects.get(cluster_id=1000)
        assert deleted_record.is_deleted
