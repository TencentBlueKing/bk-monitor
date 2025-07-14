"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.utils import timezone

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client

base_time = timezone.datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def create_or_delete_records(mocker):
    """
    创建或删除测试数据
    """
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ESStorage.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.StorageClusterRecord.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    # 创建测试数据

    # ---------------------指标数据--------------------- #
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="metric_tst",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="tencent",
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_tenant_id="tencent",
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_cluster_id=111,
        storage_cluster_id=111,
        vm_result_table_id="1001_vm_test_50010",
        bk_base_data_id=50010,
        bk_tenant_id="tencent",
    )
    models.ResultTableField.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_tenant_id="tencent",
        field_name="metric_a",
        field_type="float",
        tag="metric",
        is_config_by_user=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=50010, table_id="1001_bkmonitor_time_series_50010.__default__", bk_tenant_id="tencent"
    )
    # ---------------------指标数据--------------------- #

    # ---------------------日志数据--------------------- #
    models.ESStorage.objects.create(table_id="1001_bklog.stdout", storage_cluster_id=11, bk_tenant_id="riot")
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001,bklog_index_set_1002",
        is_custom_table=False,
        bk_tenant_id="riot",
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
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=11,
        is_current=True,
        enable_time=base_time - timedelta(days=30),
        bk_tenant_id="riot",
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=12,
        is_current=False,
        enable_time=base_time - timedelta(days=60),
        disable_time=base_time - timedelta(days=30),
        bk_tenant_id="riot",
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout", cluster_id=13, is_current=True, enable_time=None, bk_tenant_id="riot"
    )
    models.DataSourceResultTable.objects.create(bk_data_id=50011, table_id="1001_bklog.stdout", bk_tenant_id="riot")

    # ---------------------日志数据--------------------- #
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ESStorage.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.StorageClusterRecord.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_push_table_id_detail_with_tenant_for_metric(create_or_delete_records):
    """测试结果表详情路由"""

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_table_id_detail(
                table_id_list=["1001_bkmonitor_time_series_50010.__default__"], bk_tenant_id="tencent", is_publish=True
            )

            expected = {
                "1001_bkmonitor_time_series_50010.__default__|tencent": '{"vm_rt":"1001_vm_test_50010",'
                '"storage_id":111,"cmdb_level_vm_rt":"","cluster_name":"",'
                '"storage_name":"","db":"",'
                '"measurement":"bk_split_measurement'
                '","tags_key":[],'
                '"storage_type":"victoria_metrics",'
                '"fields":["metric_a"],'
                '"measurement_type'
                '":"bk_traditional_measurement",'
                '"bcs_cluster_id":"",'
                '"data_label":"","bk_data_id":50010}'
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel",
                ["1001_bkmonitor_time_series_50010.__default__|tencent"],
            )
            settings.ENABLE_MULTI_TENANT_MODE = False


@pytest.mark.django_db(databases="__all__")
def test_push_table_id_detail_without_tenant_for_metric(create_or_delete_records):
    """测试结果表详情路由"""

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_table_id_detail(
                table_id_list=["1001_bkmonitor_time_series_50010.__default__"], bk_tenant_id="tencent", is_publish=True
            )

            expected = {
                "1001_bkmonitor_time_series_50010.__default__": '{"vm_rt":"1001_vm_test_50010",'
                '"storage_id":111,"cmdb_level_vm_rt":"","cluster_name":"",'
                '"storage_name":"","db":"",'
                '"measurement":"bk_split_measurement'
                '","tags_key":[],'
                '"storage_type":"victoria_metrics",'
                '"fields":["metric_a"],'
                '"measurement_type'
                '":"bk_traditional_measurement",'
                '"bcs_cluster_id":"",'
                '"data_label":"","bk_data_id":50010}'
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel",
                ["1001_bkmonitor_time_series_50010.__default__"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_table_id_detail_with_tenant_for_log(create_or_delete_records):
    """测试结果表详情路由"""

    # 新版 push_table_id_detail
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_table_id_detail(
                table_id_list=["1001_bklog.stdout"], bk_tenant_id="riot", is_publish=True, include_es_table_ids=True
            )

            expected = {
                "1001_bklog.stdout|riot": '{"storage_id":11,"db":null,"measurement":"__default__","source_type":"log","options":{},"storage_type":"elasticsearch","storage_cluster_records":[{"storage_id":13,"enable_time":0},{"storage_id":12,"enable_time":1572652800},{"storage_id":11,"enable_time":1575244800}],"data_label":"bklog_index_set_1001,bklog_index_set_1002","field_alias":{}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel", ["1001_bklog.stdout|riot"]
            )

    # ES专用路径--push_es_table_id_detail
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_es_table_id_detail(
                table_id_list=["1001_bklog.stdout"],
                bk_tenant_id="riot",
                is_publish=True,
            )

            expected = {
                "1001_bklog.stdout|riot": '{"storage_id":11,"db":null,"measurement":"__default__",'
                '"source_type":"log","options":{},"storage_type":"elasticsearch",'
                '"storage_cluster_records":[{"storage_id":13,"enable_time":0},'
                '{"storage_id":12,"enable_time":1572652800},{"storage_id":11,'
                '"enable_time":1575244800}],"data_label":"bklog_index_set_1001,bklog_index_set_1002","field_alias":{}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel", ["1001_bklog.stdout|riot"]
            )


@pytest.mark.django_db(databases="__all__")
def test_push_table_id_detail_without_tenant_for_log(create_or_delete_records):
    """测试结果表详情路由"""

    # 新版 push_table_id_detail
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_table_id_detail(
                table_id_list=["1001_bklog.stdout"], bk_tenant_id="riot", is_publish=True, include_es_table_ids=True
            )

            expected = {
                "1001_bklog.stdout": '{"storage_id":11,"db":null,"measurement":"__default__","source_type":"log","options":{},"storage_type":"elasticsearch","storage_cluster_records":[{"storage_id":13,"enable_time":0},{"storage_id":12,"enable_time":1572652800},{"storage_id":11,"enable_time":1575244800}],"data_label":"bklog_index_set_1001,bklog_index_set_1002","field_alias":{}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel", ["1001_bklog.stdout"]
            )

    # ES专用路径--push_es_table_id_detail
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_es_table_id_detail(
                table_id_list=["1001_bklog.stdout"],
                bk_tenant_id="riot",
                is_publish=True,
            )

            expected = {
                "1001_bklog.stdout": '{"storage_id":11,"db":null,"measurement":"__default__",'
                '"source_type":"log","options":{},"storage_type":"elasticsearch",'
                '"storage_cluster_records":[{"storage_id":13,"enable_time":0},'
                '{"storage_id":12,"enable_time":1572652800},{"storage_id":11,'
                '"enable_time":1575244800}],"data_label":"bklog_index_set_1001,bklog_index_set_1002","field_alias":{}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:result_table_detail", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:result_table_detail:channel", ["1001_bklog.stdout"]
            )
