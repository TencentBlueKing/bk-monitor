"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta
from django.utils import timezone

import pytest

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

base_time = timezone.datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def create_or_delete_records(mocker):
    models.ESStorage.objects.create(
        table_id="1001_bklog.stdout",
        storage_cluster_id=11,
        index_set="bklog_index_set_1001",
    )
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001",
        labels={"scene": "log"},
        is_custom_table=False,
    )

    models.ESStorage.objects.create(
        table_id="1001_bklog.stdout_fake",
        storage_cluster_id=11,
        origin_table_id="1001_bklog.stdout",
    )
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout_fake",
        table_name_zh="stdout",
        data_label="bklog_index_set_fake",
        labels={"scene": "log-fake"},
        is_custom_table=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=11,
        cluster_name="test_es_1",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es_test.1",
        port=9090,
        description="",
        is_default_cluster=True,
        version="5.x",
    )
    models.ClusterInfo.objects.create(
        cluster_id=12,
        cluster_name="test_es_2",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es_test.2",
        port=9090,
        description="",
        is_default_cluster=False,
        version="5.x",
    )

    # 日志链路必备的两个查询Option： need_add_time & time_field
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout", name="need_add_time", value_type="bool", value="true"
    )
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout",
        name="time_field",
        value_type="dict",
        value='{"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"}',
    )

    # 日志链路必备的两个查询Option： need_add_time & time_field
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout_fake", name="need_add_time", value_type="bool", value="true"
    )
    models.ResultTableOption.objects.create(
        table_id="1001_bklog.stdout_fake",
        name="time_field",
        value_type="dict",
        value='{"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"}',
    )

    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=11,
        is_current=True,
        enable_time=base_time - timedelta(days=30),
        bk_tenant_id="system",
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=12,
        is_current=False,
        enable_time=base_time - timedelta(days=60),
        disable_time=base_time - timedelta(days=30),
        bk_tenant_id="system",
    )

    # 创建一些字段查询别名
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout", field_path="__ext.pod_name", query_alias="pod_name", is_deleted=False
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout", field_path="__ext.pod_ip", query_alias="pod_ip", is_deleted=False
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout",
        field_path="__ext.container_name",
        query_alias="container_name",
        is_deleted=True,  # 软删除的别名不会出现
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout_fake",
        field_path="__ext.fake_pod_name",
        query_alias="fake_pod_name",
        is_deleted=False,
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout_fake",
        field_path="__ext.fake_pod_ip",
        query_alias="fake_pod_ip",
        is_deleted=False,
    )
    models.ESFieldQueryAliasOption.objects.create(
        table_id="1001_bklog.stdout_fake",
        field_path="__ext.container_name",
        query_alias="container_name",
        is_deleted=True,  # 软删除的别名不会出现
    )
    yield
    table_ids = ["1001_bklog.stdout", "1001_bklog.stdout_fake"]
    models.ESStorage.objects.filter(table_id__in=table_ids).delete()
    models.ResultTable.objects.filter(table_id__in=table_ids).delete()
    models.ResultTableOption.objects.filter(table_id__in=table_ids).delete()
    models.ESFieldQueryAliasOption.objects.filter(table_id__in=table_ids).delete()
    models.ClusterInfo.objects.filter(cluster_id__in=[11, 12]).delete()


@pytest.mark.django_db(databases="__all__")
def test_compose_es_table_detail(create_or_delete_records):
    """
    测试生成ES结果表详情路由
    """
    client = SpaceTableIDRedis()
    res = client._compose_es_table_id_detail(table_id_list=["1001_bklog.stdout"], bk_tenant_id="system")
    expected = {
        "1001_bklog.stdout": {
            "storage_id": 11,
            "db": "bklog_index_set_1001",
            "measurement": "__default__",
            "source_type": "log",
            "options": {
                "need_add_time": True,
                "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
            },
            "storage_type": "elasticsearch",
            "storage_cluster_records": [
                {
                    "enable_time": 1572652800,
                    "storage_id": 12,
                    "storage_name": "test_es_2",
                    "cluster_name": "test_es_2",
                    "storage_type": "elasticsearch",
                    "db": "bklog_index_set_1001",
                    "measurement": "__default__",
                    "source_type": "log",
                },
                {
                    "enable_time": 1575244800,
                    "storage_id": 11,
                    "storage_name": "test_es_1",
                    "cluster_name": "test_es_1",
                    "storage_type": "elasticsearch",
                    "db": "bklog_index_set_1001",
                    "measurement": "__default__",
                    "source_type": "log",
                },
            ],
            "data_label": "bklog_index_set_1001",
            "labels": {"scene": "log"},
            "field_alias": {
                "pod_name": "__ext.pod_name",
                "pod_ip": "__ext.pod_ip",
            },
        }
    }

    assert res == expected


@pytest.mark.django_db(databases="__all__")
def test_compose_es_table_detail_for_fake_rt(create_or_delete_records):
    """
    测试虚拟RT的路由生成
    """
    client = SpaceTableIDRedis()
    res = client._compose_es_table_id_detail(table_id_list=["1001_bklog.stdout_fake"], bk_tenant_id="system")
    expected = {
        "1001_bklog.stdout_fake": {
            "storage_id": 11,
            "db": None,
            "measurement": "__default__",
            "source_type": "log",
            "options": {
                "need_add_time": True,
                "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
            },
            "storage_type": "elasticsearch",
            "storage_cluster_records": [
                {
                    "enable_time": 1572652800,
                    "storage_id": 12,
                    "storage_name": "test_es_2",
                    "cluster_name": "test_es_2",
                    "storage_type": "elasticsearch",
                    "db": "bklog_index_set_1001",
                    "measurement": "__default__",
                    "source_type": "log",
                },
                {
                    "enable_time": 1575244800,
                    "storage_id": 11,
                    "storage_name": "test_es_1",
                    "cluster_name": "test_es_1",
                    "storage_type": "elasticsearch",
                    "db": "bklog_index_set_1001",
                    "measurement": "__default__",
                    "source_type": "log",
                },
            ],
            "data_label": "bklog_index_set_fake",
            "labels": {"scene": "log-fake"},
            "field_alias": {
                "fake_pod_name": "__ext.fake_pod_name",
                "fake_pod_ip": "__ext.fake_pod_ip",
            },
        }
    }

    assert res == expected
