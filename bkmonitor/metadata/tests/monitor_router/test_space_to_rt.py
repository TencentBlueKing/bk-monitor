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
    models.AccessVMRecord.objects.all().delete()
    models.ESStorage.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.StorageClusterRecord.objects.all().delete()
    models.Space.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.SpaceResource.objects.all().delete()

    # ---------------------空间数据--------------------- #
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id="1",
        space_name="test",
        space_code="1111test",
        bk_tenant_id="riot",
    )
    models.SpaceDataSource.objects.create(bk_data_id=50010, space_type_id="bkcc", space_id="1", bk_tenant_id="riot")
    models.SpaceDataSource.objects.create(bk_data_id=50011, space_type_id="bkcc", space_id="1", bk_tenant_id="riot")

    models.Space.objects.create(
        space_type_id="bkci",
        space_id="bkmonitor",
        space_name="bkmonitor",
        space_code="1111bkm",
        bk_tenant_id="tencent",
        id=10000,
    )
    models.SpaceResource.objects.create(
        space_type_id="bkci", space_id="bkmonitor", resource_type="bkcc", resource_id="1"
    )

    models.Space.objects.create(
        space_type_id="bksaas",
        space_id="monitor_saas",
        space_name="monitor_saas",
        space_code="1111bksaas",
        bk_tenant_id="tencent",
        id=10008,
    )
    # ---------------------空间数据--------------------- #

    # ---------------------指标数据--------------------- #
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="metric_tst",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="riot",
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_tenant_id="riot",
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_cluster_id=111,
        storage_cluster_id=111,
        vm_result_table_id="1001_vm_test_50010",
        bk_base_data_id=50010,
        bk_tenant_id="riot",
    )
    models.ResultTableField.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_tenant_id="riot",
        field_name="metric_a",
        field_type="float",
        tag="metric",
        is_config_by_user=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=50010, table_id="1001_bkmonitor_time_series_50010.__default__", bk_tenant_id="riot"
    )
    # ---------------------指标数据--------------------- #

    # ---------------------预计算数据--------------------- #
    models.RecordRule.objects.create(
        space_type="bkcc", space_id="1", bk_tenant_id="riot", table_id="bkm_1_record_rule.__default__"
    )

    # ---------------------日志数据--------------------- #
    models.ESStorage.objects.create(table_id="1001_bklog.stdout", storage_cluster_id=11, bk_tenant_id="riot")
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001",
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
    models.Space.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.SpaceResource.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_with_tenant_for_bkcc(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCC类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkcc", space_id="1", is_publish=True)

            expected = {
                "bkcc__1|riot": '{"1001_bklog.stdout":{"filters":[{"bk_biz_id":"1"}]},"1001_bkmonitor_time_series_50010.__default__":{"filters":[{"bk_biz_id":"1"}]},"bkm_1_record_rule.__default__":{"filters":[]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            actual: dict[str, str] = mock_hmset_to_redis.call_args[0][1]
            assert isinstance(actual, dict)
            assert list(actual.keys()) == list(expected.keys())
            assert json.loads(actual["bkcc__1|riot"]) == json.loads(expected["bkcc__1|riot"])

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkcc__1|riot"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_without_tenant_for_bkcc(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCC类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkcc", space_id="1", is_publish=True)

            expected = {
                "bkcc__1": '{"1001_bklog.stdout":{"filters":[{"bk_biz_id":"1"}]},"1001_bkmonitor_time_series_50010.__default__":{"filters":[{"bk_biz_id":"1"}]},"bkm_1_record_rule.__default__":{"filters":[]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            actual: dict[str, str] = mock_hmset_to_redis.call_args[0][1]
            assert isinstance(actual, dict)
            assert list(actual.keys()) == list(expected.keys())
            assert json.loads(actual["bkcc__1"]) == json.loads(expected["bkcc__1"])

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkcc__1"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_with_tenant_for_bkci(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCI类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkci", space_id="bkmonitor", is_publish=True)

            expected = {
                "bkci__bkmonitor|tencent": '{"custom_report_aggate.base":{"filters":[{"bk_biz_id":"-10000"}]},'
                '"bkm_statistics.base":{"filters":[{"bk_biz_id":"-10000"}]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:space_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkci__bkmonitor|tencent"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_without_tenant_for_bkci(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCI类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkci", space_id="bkmonitor", is_publish=True)

            expected = {
                "bkci__bkmonitor": '{"custom_report_aggate.base":{"filters":[{"bk_biz_id":"-10000"}]},'
                '"bkm_statistics.base":{"filters":[{"bk_biz_id":"-10000"}]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:space_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkci__bkmonitor"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_with_tenant_for_bksaas(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKSAAS类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bksaas", space_id="monitor_saas", is_publish=True)

            expected = {
                "bksaas__monitor_saas|tencent": '{"custom_report_aggate.base":{"filters":[{'
                '"bk_biz_id":"-10008"}]},"bkm_statistics.base":{"filters":[{'
                '"bk_biz_id":"-10008"}]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:space_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bksaas__monitor_saas|tencent"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_without_tenant_for_bksaas(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKSAAS类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bksaas", space_id="monitor_saas", is_publish=True)

            expected = {
                "bksaas__monitor_saas": '{"custom_report_aggate.base":{"filters":[{'
                '"bk_biz_id":"-10008"}]},"bkm_statistics.base":{"filters":[{'
                '"bk_biz_id":"-10008"}]}}'
            }

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:space_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bksaas__monitor_saas"],
            )
