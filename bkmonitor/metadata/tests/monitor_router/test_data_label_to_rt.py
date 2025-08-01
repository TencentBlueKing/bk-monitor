"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import patch

import pytest
from django.conf import settings

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    """
    创建或删除测试数据
    """
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()

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
        data_label="metric_data_label",
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_tenant_id="tencent",
        data_label="metric_data_label,metric_data_label_2",
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
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_push_data_label_table_ids_for_table_ids(create_or_delete_records):
    """
    测试DATA_LABEL_TO_RESULT_TABLE 在多租户环境下的路由推送
    """
    # 多租户
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_data_label_table_ids(
                table_id_list=["1001_bkmonitor_time_series_50011.__default__"], bk_tenant_id="tencent", is_publish=True
            )
            expected = {
                "metric_data_label|tencent": '["1001_bkmonitor_time_series_50010.__default__","1001_bkmonitor_time_series_50011.__default__"]',
                "metric_data_label_2|tencent": '["1001_bkmonitor_time_series_50011.__default__"]',
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:data_label_to_result_table", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:data_label_to_result_table:channel",
                ["metric_data_label|tencent", "metric_data_label_2|tencent"],
            )

    # 单租户
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_data_label_table_ids(
                table_id_list=["1001_bkmonitor_time_series_50010.__default__"], bk_tenant_id="tencent", is_publish=True
            )
            expected = {
                "metric_data_label": '["1001_bkmonitor_time_series_50010.__default__","1001_bkmonitor_time_series_50011.__default__"]'
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:data_label_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:data_label_to_result_table:channel", ["metric_data_label"]
            )


@pytest.mark.django_db(databases="__all__")
def test_push_data_label_table_ids_for_data_labels(create_or_delete_records):
    """
    测试DATA_LABEL_TO_RESULT_TABLE 在多租户环境下的路由推送
    """
    # 多租户
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_data_label_table_ids(
                data_label_list=["metric_data_label"], bk_tenant_id="tencent", is_publish=True
            )
            expected = {
                "metric_data_label|tencent": '["1001_bkmonitor_time_series_50010.__default__","1001_bkmonitor_time_series_50011.__default__"]'
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:data_label_to_result_table", expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:data_label_to_result_table:channel", ["metric_data_label|tencent"]
            )

    # 单租户
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_data_label_table_ids(
                data_label_list=["metric_data_label"], bk_tenant_id="tencent", is_publish=True
            )
            expected = {
                "metric_data_label": '["1001_bkmonitor_time_series_50010.__default__","1001_bkmonitor_time_series_50011.__default__"]'
            }
            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            mock_hmset_to_redis.assert_called_once_with("bkmonitorv3:spaces:data_label_to_result_table", expected)
            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:data_label_to_result_table:channel", ["metric_data_label"]
            )
