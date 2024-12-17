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
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        is_platform_data_id=True,
    )
    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="data_link_test_2",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_time_series",
        is_custom_source=False,
        is_platform_data_id=True,
    )
    models.DataSource.objects.create(
        bk_data_id=50012,
        data_name="data_link_test_3",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_biz_id_alias='appid',
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50012.__default__", bk_biz_id=1002, is_custom_table=False
    )
    models.AccessVMRecord.objects.create(
        result_table_id='1001_bkmonitor_time_series_50010.__default__',
        bk_base_data_id=50010,
        vm_result_table_id='1001_vm_test_50010',
    )
    models.AccessVMRecord.objects.create(
        result_table_id='1001_bkmonitor_time_series_50011.__default__',
        bk_base_data_id=50011,
        vm_result_table_id='1001_vm_test_50011',
    )
    models.AccessVMRecord.objects.create(
        result_table_id='1001_bkmonitor_time_series_50012.__default__',
        bk_base_data_id=50012,
        vm_result_table_id='1001_vm_test_50012',
    )
    models.SpaceDataSource.objects.create(space_type_id='bkcc', space_id=1001, bk_data_id=50010)
    models.SpaceDataSource.objects.create(space_type_id='bkcc', space_id=1001, bk_data_id=50011)
    models.SpaceDataSource.objects.create(space_type_id='bkcc', space_id=1002, bk_data_id=50012)
    models.DataSourceResultTable.objects.create(
        table_id='1001_bkmonitor_time_series_50010.__default__', bk_data_id=50010
    )
    models.DataSourceResultTable.objects.create(
        table_id='1001_bkmonitor_time_series_50011.__default__', bk_data_id=50011
    )
    models.DataSourceResultTable.objects.create(
        table_id='1001_bkmonitor_time_series_50012.__default__', bk_data_id=50012
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_compose_data_for_space_router(create_or_delete_records):
    self = SpaceTableIDRedis()
    values_for_creator = self._compose_data('bkcc', '1001')

    # 测试全局数据源创建者业务下的空间路由
    expected_for_creator_space = {
        '1001_bkmonitor_time_series_50011.__default__': {'filters': []},
        '1001_bkmonitor_time_series_50010.__default__': {'filters': []},
    }
    assert values_for_creator == expected_for_creator_space

    # 测试全局数据源在其他业务下的空间路由
    values_for_others = self._compose_data('bkcc', '1003')
    expected_for_other_space = {
        '1001_bkmonitor_time_series_50011.__default__': {'filters': [{'bk_biz_id': '1003'}]},
        '1001_bkmonitor_time_series_50010.__default__': {'filters': [{'appid': '1003'}]},
    }
    assert values_for_others == expected_for_other_space
