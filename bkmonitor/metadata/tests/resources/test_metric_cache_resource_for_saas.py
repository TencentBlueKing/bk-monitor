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

from metadata import models
from metadata.resources import ListResultTableResource
from metadata.tests.common_utils import consul_client

normal_table_id = '1001_bkmonitor_time_series_50010.__default__'
pre_cal_table_id = 'bkprecal_bkcc_2_unify_query_tsdb_test_new_prom_node.__default__'


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    result_table = models.ResultTable.objects.create(table_id=normal_table_id, bk_biz_id=1001, is_custom_table=False)
    dsrt = models.DataSourceResultTable.objects.create(bk_data_id=50010, table_id=normal_table_id)
    models.ResultTableField.objects.create(
        table_id=normal_table_id,
        field_name="cpu_load",
        field_type="float",
        description="test1",
        is_config_by_user=True,
        tag='metric',
    )
    models.ResultTableField.objects.create(
        table_id=normal_table_id,
        field_name="gpu_load",
        field_type="float",
        description="test2",
        is_config_by_user=True,
        tag='metric',
    )
    models.ResultTable.objects.create(table_id=pre_cal_table_id, bk_biz_id=-1002, is_custom_table=False)
    space = models.Space.objects.create(id=1002, space_type_id='bkci', space_id='test', space_name="test_space")
    record_rule = models.RecordRule.objects.create(
        table_id=pre_cal_table_id,
        space_type='bkci',
        space_id='test',
        record_name='test_record',
        dst_vm_table_id='test_vm_1002',
    )
    models.ResultTableField.objects.create(
        table_id=pre_cal_table_id,
        field_name="precal_metric1",
        field_type="float",
        description="test_precal_1",
        is_config_by_user=True,
        tag='metric',
    )
    models.ResultTableField.objects.create(
        table_id=pre_cal_table_id,
        field_name="precal_metric2",
        field_type="float",
        description="test_precal_2",
        is_config_by_user=True,
        tag='metric',
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    result_table.delete()
    dsrt.delete()
    space.delete()
    record_rule.delete()
    models.ResultTableField.objects.filter(table_id=pre_cal_table_id).delete()
    models.ResultTableField.objects.filter(table_id=normal_table_id).delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_list_result_table_resource(create_or_delete_records, mocker):
    """
    测试ListResultTableResource接口能否正常返回字段列表（常规业务+预计算）
    """
    # Case1. 常规业务查询场景
    normal_data = ListResultTableResource().request(bk_biz_id=1001)
    normal_field_list = normal_data[0]['field_list']
    expected_field_list = [
        {
            'field_name': 'cpu_load',
            'type': 'float',
            'tag': 'metric',
            'default_value': None,
            'is_config_by_user': True,
            'description': 'test1',
            'unit': '',
            'alias_name': '',
            'is_disabled': False,
            'option': {},
        },
        {
            'field_name': 'gpu_load',
            'type': 'float',
            'tag': 'metric',
            'default_value': None,
            'is_config_by_user': True,
            'description': 'test2',
            'unit': '',
            'alias_name': '',
            'is_disabled': False,
            'option': {},
        },
    ]

    assert normal_data[0]['table_id'] == normal_table_id
    assert json.dumps(normal_field_list) == json.dumps(expected_field_list)

    # Case2. 预计算且非bkcc类型查询场景
    pre_cal_data = ListResultTableResource().request(bk_biz_id=-1002)
    pre_cal_field_list = pre_cal_data[0]['field_list']
    expected_pre_cal_field_list = [
        {
            'field_name': 'precal_metric1',
            'type': 'float',
            'tag': 'metric',
            'default_value': None,
            'is_config_by_user': True,
            'description': 'test_precal_1',
            'unit': '',
            'alias_name': '',
            'is_disabled': False,
            'option': {},
        },
        {
            'field_name': 'precal_metric2',
            'type': 'float',
            'tag': 'metric',
            'default_value': None,
            'is_config_by_user': True,
            'description': 'test_precal_2',
            'unit': '',
            'alias_name': '',
            'is_disabled': False,
            'option': {},
        },
    ]
    assert pre_cal_data[0]['table_id'] == pre_cal_table_id
    assert json.dumps(pre_cal_field_list) == json.dumps(expected_pre_cal_field_list)
