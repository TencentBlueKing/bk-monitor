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
from metadata.resources import NotifyEsDataLinkAdaptNano
from metadata.tests.common_utils import consul_client

table_id = "1001_test_log.__default__"


@pytest.fixture
def create_or_delete_records(mocker):
    models.ResultTable.objects.create(
        table_id=table_id,
        bk_biz_id=1001,
        is_custom_table=False,
    )
    models.ResultTableField.objects.create(
        table_id=table_id,
        field_name='dtEventTimeStamp',
        field_type='timestamp',
        description='数据时间',
        tag='dimension',
        is_config_by_user=True,
    )
    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name='dtEventTimeStamp',
        name='es_format',
        value='strict_date_optional_time_nanos',
        value_type='string',
    )
    models.ResultTableFieldOption.objects.create(
        table_id=table_id,
        field_name='time',
        name='es_format',
        value='strict_date_optional_time_nanos',
        value_type='string',
    )
    models.DataSource.objects.create(
        bk_data_id=100111,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(table_id=table_id, bk_data_id=100111)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.ResultTable.objects.filter(table_id=table_id).delete()
    models.ResultTableField.objects.filter(table_id=table_id).delete()
    models.ResultTableFieldOption.objects.filter(table_id=table_id).delete()
    models.DataSource.objects.filter(bk_data_id=100111).delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=100111).delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_notify_es_data_link_adapt_nano(create_or_delete_records):
    data = NotifyEsDataLinkAdaptNano().request(table_id=table_id)
    expected = [
        {
            'field_name': 'dtEventTimeStamp',
            'type': 'timestamp',
            'tag': 'dimension',
            'default_value': None,
            'is_config_by_user': True,
            'description': '数据时间',
            'unit': '',
            'alias_name': '',
            'option': {'es_format': 'strict_date_optional_time_nanos||epoch_millis'},
            'is_disabled': False,
        },
        {
            'field_name': 'dtEventTimeStampNanos',
            'type': 'timestamp',
            'tag': 'dimension',
            'default_value': None,
            'is_config_by_user': True,
            'description': '数据时间',
            'unit': '',
            'alias_name': '',
            'option': {'es_type': 'date_nanos', 'es_format': 'strict_date_optional_time_nanos||epoch_millis'},
            'is_disabled': False,
        },
    ]
    assert json.dumps(data) == json.dumps(expected)
