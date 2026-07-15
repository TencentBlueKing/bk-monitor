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
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client

base_time = timezone.datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def create_or_delete_records(mocker):
    models.ESStorage.objects.create(table_id="1001_bklog.stdout", storage_cluster_id=11, index_set="bklog_stdout")
    models.ESStorage.objects.create(table_id="test_system_event", storage_cluster_id=11, index_set="test_system_event")
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
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001",
        labels={"scene": "log"},
        is_custom_table=False,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    models.ClusterInfo.objects.create(
        cluster_id=12,
        cluster_name="test_es_2",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es_test.2",
        port=9090,
        description="",
        is_default_cluster=True,
        version="5.x",
    )
    models.ClusterInfo.objects.create(
        cluster_id=13,
        cluster_name="test_es_3",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es_test.3",
        port=9090,
        description="",
        is_default_cluster=True,
        version="5.x",
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout", cluster_id=11, is_current=True, enable_time=base_time - timedelta(days=30)
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=12,
        is_current=False,
        enable_time=base_time - timedelta(days=60),
        disable_time=base_time - timedelta(days=30),
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout", cluster_id=13, is_current=True, enable_time=None
    )

    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.ESStorage.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.StorageClusterRecord.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_push_es_details_through_unified_entry(create_or_delete_records):
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            client = SpaceTableIDRedis()

            table_id = "1001_bklog.stdout"

            client.push_table_id_detail(
                bk_tenant_id="system",
                table_id_list=["1001_bklog.stdout", "test_system_event"],
                is_publish=True,
            )

            redis_key, redis_values = mock_hmset_to_redis.call_args.args
            details = {key: json.loads(value) for key, value in redis_values.items()}
            expected = {
                "1001_bklog.stdout": {
                    "storage_id": 11,
                    "db": "bklog_stdout",
                    "measurement": "__default__",
                    "source_type": "log",
                    "options": {},
                    "storage_type": "elasticsearch",
                    "storage_cluster_records": [
                        {
                            "storage_id": 11,
                            "storage_type": "elasticsearch",
                            "db": "bklog_stdout",
                            "measurement": "__default__",
                            "source_type": "log",
                            "enable_time": 1575244800,
                        },
                        {
                            "storage_id": 12,
                            "storage_type": "elasticsearch",
                            "db": "bklog_stdout",
                            "measurement": "__default__",
                            "source_type": "log",
                            "enable_time": 1572652800,
                        },
                        {
                            "storage_id": 13,
                            "storage_type": "elasticsearch",
                            "db": "bklog_stdout",
                            "measurement": "__default__",
                            "source_type": "log",
                            "enable_time": 0,
                        },
                    ],
                    "data_label": "bklog_index_set_1001",
                    "labels": {"scene": "log"},
                    "field_alias": {},
                },
                "test_system_event.__default__": {
                    "storage_id": 11,
                    "db": "test_system_event",
                    "measurement": "__default__",
                    "source_type": "log",
                    "options": {},
                    "storage_type": "elasticsearch",
                    "storage_cluster_records": [],
                    "data_label": "",
                    "labels": {},
                    "field_alias": {},
                },
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            assert redis_key == "bkmonitorv3:spaces:result_table_detail"
            assert details == expected

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel", [table_id, "test_system_event.__default__"]
            )
