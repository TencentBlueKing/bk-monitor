"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from metadata.resources import ListBkBaseRtInfoByBizIdResource
from metadata.task.bkbase import sync_all_bkbase_cluster_info, sync_bkbase_rt_meta_info_all
from metadata.task.tasks import sync_bkbase_v4_metadata
from metadata.tests.common_utils import consul_client

# 定义 Mock 的 Redis hgetall 返回值
redis_value_for_metric_when_cluster_not_exists = {
    b"kafka": json.dumps(
        {
            "host": "test.kafka.db",
            "port": 9092,
            "auth": None,
            "topic": "bkm_test_metric_topic",
            "partitions": 1,
        }
    ).encode("utf-8"),
    b"vm": json.dumps(
        {
            "vm_test_metric_1": {
                "namespace": "test_ns",
                "name": "test_vm",
                "insert_host": "insert_host.test",
                "insert_port": 80,
                "select_host": "select_host.test",
                "select_port": 80,
            }
        }
    ).encode("utf-8"),
}


redis_value_for_metric_when_cluster_exists = {
    b"kafka": json.dumps(
        {
            "host": "test2.kafka.db",
            "port": 9092,
            "auth": None,
            "topic": "bkm_test2_metric_topic",
            "partitions": 3,
        }
    ).encode("utf-8"),
    b"vm": json.dumps(
        {
            "vm_test_metric_2": {
                "namespace": "test_ns",
                "name": "test_vm",
                "insert_host": "insert_host.test",
                "insert_port": 80,
                "select_host": "select_host.test",
                "select_port": 80,
            }
        }
    ).encode("utf-8"),
}

# 测试数据
es_info = [
    {
        "host": "test.es.db",
        "port": 9200,
        "user": "admin",
        "password": "password",
        "update_time": "2025-02-07 11:14:21.784665876 UTC",
    },
    {
        "host": "test2.es.db",
        "port": 9200,
        "user": "admin",
        "password": "password",
        "update_time": "2025-02-09 11:14:21.784665876 UTC",
    },
]

# Mock redis value
# redis_value_for_log = {
#     b"bkmonitor_test_result_log_table": json.dumps(
#         {
#             "kafka": {
#                 "host": "test2.kafka.db",
#                 "port": 9092,
#                 "auth": None,
#                 "topic": "bkm_test_log_topic",
#                 "partitions": 6,
#             },
#             "es": es_info,
#         }
#     ).encode("utf-8")
# }

redis_value_for_log = {
    b"kafka": json.dumps(
        {
            "host": "test2.kafka.db",
            "port": 9092,
            "auth": None,
            "topic": "bkm_test_log_topic",
            "partitions": 6,
        }
    ).encode("utf-8"),
    b"es": json.dumps(
        {
            "bkmonitor_test_result_log_table": es_info,
        }
    ).encode("utf-8"),
}


@pytest.fixture
def create_or_delete_records(mocker):
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id="123456789",
        status="normal",
        space_code="test_bkcc_space",
        space_name="test_bkcc_space",
    )

    # Case1. （指标链路） Kafka集群不存在 + VM集群不存在
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from="bkdata",
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
        bk_base_data_id=50010,
    )

    # Case2.Kafka集群变更 + Topic变更 + VM集群变更
    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="data_link_test_metric_2",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from="bkdata",
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
        vm_result_table_id="vm_test_metric_2",
        vm_cluster_id=2,
        bk_base_data_id=50011,
    )
    models.ClusterInfo.objects.create(
        domain_name="test2.kafka.db",
        cluster_name="test2",
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
        created_from="bkdata",
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
        domain_name="test.es.db",
        cluster_name="testes",
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        domain_name="test2.es.db",
        cluster_name="testes2",
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=False,
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bkmonitor_log_60010.__default__",
        cluster_id=1000,
        is_deleted=False,
    )

    # 计算平台元数据RT同步
    models.ResultTableOption.objects.create(
        table_id="2_test_ss_entry_61_INPUT.__default__",
        name="bkbase_rt_storage_types",
        value_type="list",
        value=json.dumps(["hdfs"]),
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.Space.objects.all().delete()
    models.ResultTableOption.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_v4_metadata_for_metric(create_or_delete_records, mocker):
    """
    测试计算平台元数据同步更新能力 -- 指标链路
    Case1. Kafka集群不存在 + VM集群不存在
    Case2. Kafka集群变更 + Topic变更 + VM集群变更
    """

    mocker.patch("django.conf.settings.ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE", True)
    mocker.patch("django.conf.settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB", True)

    # Case1. Kafka集群不存在 + VM集群不存在
    with patch(
        "redis.StrictRedis.hgetall", return_value=redis_value_for_metric_when_cluster_not_exists
    ) as mock_hgetall:  # noqa
        # 定义测试输入
        key = "databus_v4_dataid:50010"

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=50010)
        kafka_cluster_new = models.ClusterInfo.objects.get(domain_name="test.kafka.db")
        vm_cluster_new = models.ClusterInfo.objects.get(domain_name="insert_host.test")
        mq_config = models.KafkaTopicInfo.objects.get(bk_data_id=50010)
        vm_record = models.AccessVMRecord.objects.get(result_table_id="1001_bkmonitor_time_series_50010.__default__")

        assert ds.mq_cluster_id == kafka_cluster_new.cluster_id
        assert ds.mq_config_id == mq_config.id
        assert vm_record.vm_cluster_id == vm_cluster_new.cluster_id

    with patch("redis.StrictRedis.hgetall", return_value=redis_value_for_metric_when_cluster_exists) as mock_hgetall:  # noqa
        key = "databus_v4_dataid:50011"

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=50011)
        kafka_cluster_new = models.ClusterInfo.objects.get(domain_name="test2.kafka.db")
        vm_cluster_new = models.ClusterInfo.objects.get(domain_name="insert_host.test")
        mq_config = models.KafkaTopicInfo.objects.get(bk_data_id=50011)
        vm_record = models.AccessVMRecord.objects.get(result_table_id="1001_bkmonitor_time_series_50011.__default__")

        assert ds.mq_cluster_id == kafka_cluster_new.cluster_id
        assert ds.mq_config_id == mq_config.id
        assert vm_record.vm_cluster_id == vm_cluster_new.cluster_id
        assert mq_config.partition == 3
        assert mq_config.topic == "bkm_test2_metric_topic"


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_v4_metadata_for_log(create_or_delete_records, mocker):
    """
    测试计算平台元数据同步更新能力 -- 日志链路
    Case. Kafka集群变更+ES集群变更
    """
    # Case1. Kafka集群不存在 + VM集群不存在
    with patch("redis.StrictRedis.hgetall", return_value=redis_value_for_log) as mock_hgetall:  # noqa
        # 定义测试输入
        key = "databus_v4_dataid:60010"
        table_id = "1001_bkmonitor_log_60010.__default__"

        mocker.patch("django.conf.settings.ENABLE_SYNC_HISTORY_ES_CLUSTER_RECORD_FROM_BKBASE", True)
        mocker.patch("django.conf.settings.ENABLE_SYNC_BKBASE_METADATA_TO_DB", True)

        # 调用测试函数
        sync_bkbase_v4_metadata(key)

        ds = models.DataSource.objects.get(bk_data_id=60010)
        kafka_cluster = models.ClusterInfo.objects.get(domain_name="test2.kafka.db")
        es_cluster = models.ClusterInfo.objects.get(domain_name="test.es.db")
        es_cluster2 = models.ClusterInfo.objects.get(domain_name="test2.es.db")
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


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_clusters(create_or_delete_records):
    mock_es_data = [
        {
            "kind": "ElasticSearch",
            "metadata": {
                "namespace": "bklog",
                "name": "test_es_cluster",
            },
            "spec": {
                "host": "es.example.com",
                "port": 9200,
                "user": "es_user",  # 注意这里键名是 user
                "password": "es_password",
            },
        }
    ]

    mock_vm_data = [
        {
            "kind": "VmStorage",
            "metadata": {
                "namespace": "bkmonitor",
                "name": "test_vm_cluster",
            },
            "spec": {"insertHost": "vm.example.com", "insertPort": 8480, "user": "vm_user", "password": "vm_password"},
        }
    ]

    mock_doris_data = [
        {
            "kind": "Doris",
            "metadata": {"namespace": "bklog", "name": "doris_test", "labels": {}, "annotations": {}},
            "spec": {
                "host": "doris_test.test",
                "port": 9030,
                "write_port": 8030,
                "user": "testuser",
                "password": "testpwd",
                "table_bucket_num": None,
                "shard_minutes": 1,
                "v3_rename": None,
            },
            "status": {
                "phase": "Ok",
                "start_time": "2035-03-18 06:30:34.245777341 UTC",
                "update_time": "2035-03-18 06:30:39.630946716 UTC",
                "message": "",
            },
        }
    ]
    with patch("core.drf_resource.api.bkdata.list_data_link") as mock_api:
        mock_api.side_effect = [mock_es_data, mock_vm_data, mock_doris_data]
        sync_all_bkbase_cluster_info()

        es_cluster = models.ClusterInfo.objects.get(domain_name="es.example.com")
        assert es_cluster.username == "es_user"
        assert es_cluster.password == "es_password"
        assert es_cluster.cluster_type == models.ClusterInfo.TYPE_ES

        vm_cluster = models.ClusterInfo.objects.get(domain_name="vm.example.com")
        assert vm_cluster.username == "vm_user"
        assert vm_cluster.password == "vm_password"
        assert vm_cluster.cluster_type == models.ClusterInfo.TYPE_VM

        doris_cluster = models.ClusterInfo.objects.get(domain_name="doris_test.test")
        assert doris_cluster.username == "testuser"
        assert doris_cluster.password == "testpwd"
        assert doris_cluster.cluster_type == models.ClusterInfo.TYPE_DORIS


# 计算平台Meta接口的返回值(这里只Mock了监控平台需要关注的部分)
bkbase_rt_meta_api_return_data = [
    {
        "result_table_name": "test_treat_diversion_plan_1",
        "bk_biz_id": 7,
        "created_at": "2024-09-26 14:29:35",
        "sensitivity": "private",
        "result_table_name_alias": "test_treat_diversion_plan_1",
        "updated_by": "admin",
        "created_by": "admin",
        "result_table_id": "test_treat_diversion_plan_1",
        "count_freq": 0,
        "description": "test_treat_diversion_plan_1",
        "updated_at": "2024-09-26 14:31:40",
        "generate_type": "user",
        "result_table_type": None,
        "processing_type": "stream",
        "project_id": 1,
        "platform": "bk_data",
        "is_managed": 1,
        "count_freq_unit": "S",
        "data_category": "UTF8",
        "project_name": "\\u84dd\\u9cb8\\u76d1\\u63a7",
        "fields": [
            {
                "roles": {"event_time": False},
                "field_type": "timestamp",
                "description": "timestamp",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "timestamp",
                "field_name": "timestamp",
                "id": 825962,
                "field_index": 1,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_startTime_",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "_startTime_",
                "field_name": "_startTime_",
                "id": 825963,
                "field_index": 2,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_endTime_",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "_endTime_",
                "field_name": "_endTime_",
                "id": 825964,
                "field_index": 3,
                "updated_by": "admin",
            },
        ],
        "storages": {
            "pulsar": {"id": 1234567, "updated_by": "admin"},
            "tspider": {
                "id": 12345678,
                "updated_by": "admin",
                "generate_type": "user",
                "active": True,
                "priority": 0,
                "created_by": "admin",
            },
        },
        "tags": {"manage": {"geog_area": [{"code": "inland", "alias": "\\u4e2d\\u56fd\\u5185\\u5730"}]}},
    },
    {
        "result_table_name": "test_ss_entry_61_INPUT",
        "bk_biz_id": 2,
        "created_at": "2024-09-26 14:30:37",
        "sensitivity": "private",
        "result_table_name_alias": "instance_61_entry_INPUT",
        "updated_by": "admin",
        "created_by": "admin",
        "result_table_id": "2_test_ss_entry_61_INPUT",
        "count_freq": 0,
        "description": "instance_61_entry_INPUT",
        "updated_at": "2024-09-26 14:31:24",
        "generate_type": "user",
        "result_table_type": None,
        "processing_type": "stream",
        "project_id": 1,
        "platform": "bk_data",
        "is_managed": 1,
        "count_freq_unit": "S",
        "data_category": "UTF8",
        "project_name": "\\u84dd\\u9cb8\\u76d1\\u63a7",
        "fields": [
            {
                "roles": {"event_time": False},
                "field_type": "timestamp",
                "description": "timestamp",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": True,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "timestamp",
                "field_name": "timestamp",
                "id": 825975,
                "field_index": 1,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_startTime_",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "_startTime_",
                "field_name": "_startTime_",
                "id": 825976,
                "field_index": 2,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_endTime_",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "_endTime_",
                "field_name": "_endTime_",
                "id": 825977,
                "field_index": 3,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "double",
                "description": "value",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "value",
                "field_name": "value",
                "id": 825978,
                "field_index": 4,
                "updated_by": "admin",
            },
        ],
        "storages": {
            "pulsar": {"id": 193678, "storage_config": "{}", "active": True, "priority": 10},
            "hdfs": {
                "id": 193679,
                "physical_table_name": "test.test",
                "updated_by": "admin",
                "result_table_id": "2_test_ss_entry_61_INPUT",
            },
        },
        "tags": {"manage": {"geog_area": [{"code": "inland", "alias": "\\u4e2d\\u56fd\\u5185\\u5730"}]}},
    },
]


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_rt_meta_info_all(mocker, create_or_delete_records):
    mocker.patch(
        "core.drf_resource.api.bkdata.bulk_list_result_table",
        return_value=bkbase_rt_meta_api_return_data,
    )
    mocker.patch("django.conf.settings.ENABLE_SYNC_BKBASE_META_TASK", True)

    sync_bkbase_rt_meta_info_all()

    rt_ins_1 = models.ResultTable.objects.get(table_id="test_treat_diversion_plan_1.__default__")
    assert rt_ins_1.bk_biz_id == 7
    assert rt_ins_1.table_name_zh == "test_treat_diversion_plan_1"
    assert rt_ins_1.default_storage == "bkdata"

    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="timestamp"
        ).tag
        == "metric"
    )
    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="_startTime_"
        ).tag
        == "dimension"
    )
    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="_endTime_"
        ).tag
        == "dimension"
    )

    assert (
        models.ResultTableOption.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", name="bkbase_rt_storage_types"
        ).value
        == '["pulsar","tspider"]'
    )

    rt_ins_2 = models.ResultTable.objects.get(table_id="2_test_ss_entry_61_INPUT.__default__")
    assert rt_ins_2.bk_biz_id == 2
    assert rt_ins_2.table_name_zh == "test_ss_entry_61_INPUT"
    assert rt_ins_1.default_storage == "bkdata"

    assert (
        models.ResultTableField.objects.get(
            table_id="2_test_ss_entry_61_INPUT.__default__", field_name="_startTime_"
        ).tag
        == "dimension"
    )
    assert (
        models.ResultTableField.objects.get(table_id="2_test_ss_entry_61_INPUT.__default__", field_name="_endTime_").tag
        == "dimension"
    )
    assert (
        models.ResultTableField.objects.get(table_id="2_test_ss_entry_61_INPUT.__default__", field_name="value").tag
        == "metric"
    )
    # 不同步is_dimension为False的字段
    assert models.ResultTableField.objects.filter(
        table_id="2_test_ss_entry_61_INPUT.__default__", field_name="timestamp"
    ).exists()

    assert (
        models.ResultTableOption.objects.get(
            table_id="2_test_ss_entry_61_INPUT.__default__", name="bkbase_rt_storage_types"
        ).value
        == '["pulsar","hdfs"]'
    )

    # 测试元信息拉取接口
    data = ListBkBaseRtInfoByBizIdResource().request(bk_biz_id=7)
    expected = [
        {
            "bk_biz_id": 7,
            "bk_data_id": None,
            "bk_tenant_id": "system",
            "create_time": "2025-05-20 06:29:46",
            "creator": "system",
            "data_label": "",
            "default_storage": "bkdata",
            "field_list": [
                {
                    "alias_name": "",
                    "default_value": None,
                    "description": "",
                    "field_name": "_endTime_",
                    "is_config_by_user": False,
                    "is_disabled": False,
                    "option": {},
                    "tag": "dimension",
                    "type": "string",
                    "unit": "",
                },
                {
                    "alias_name": "",
                    "default_value": None,
                    "description": "",
                    "field_name": "_startTime_",
                    "is_config_by_user": False,
                    "is_disabled": False,
                    "option": {},
                    "tag": "dimension",
                    "type": "string",
                    "unit": "",
                },
                {
                    "alias_name": "",
                    "default_value": None,
                    "description": "",
                    "field_name": "timestamp",
                    "is_config_by_user": False,
                    "is_disabled": False,
                    "option": {},
                    "tag": "metric",
                    "type": "timestamp",
                    "unit": "",
                },
            ],
            "is_custom_table": False,
            "is_enable": True,
            "label": "others",
            "last_modify_time": "2025-05-20 06:29:46",
            "last_modify_user": "system",
            "option": {"bkbase_rt_storage_types": ["pulsar", "tspider"]},
            "scheme_type": "free",
            "storage_list": [],
            "table_id": "test_treat_diversion_plan_1.__default__",
            "table_name_zh": "test_treat_diversion_plan_1",
        }
    ]
    # assert data == expected
    assert data[0]["table_id"] == expected[0]["table_id"]
