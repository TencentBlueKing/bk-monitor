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

import datetime
import json
from io import StringIO

import pytest
from django.core.management import call_command

from metadata import models

DEFAULT_DATA_ID_ONE = "110001"
DEFAULT_TABLE_ID_ONE = "test.demo1"
DEFAULT_DATA_ID_TWO = "110002"
DEFAULT_TABLE_ID_TWO = "test.demo2"


pytestmark = pytest.mark.django_db


def test_query_no_params():
    out = StringIO()
    call_command("query_es_index", stderr=out)

    output = out.getvalue()
    assert "please input [bk_data_ids]" in output


def test_query_no_data():
    out = StringIO()
    call_command("query_es_index", bk_data_ids="123", stderr=out)

    output = out.getvalue()
    assert "no es data source found" in output


@pytest.fixture
def create_and_delete_record():
    ds_rt_objs = [
        models.DataSourceResultTable(bk_data_id=DEFAULT_DATA_ID_ONE, table_id=DEFAULT_TABLE_ID_ONE),
        models.DataSourceResultTable(bk_data_id=DEFAULT_DATA_ID_TWO, table_id=DEFAULT_TABLE_ID_TWO),
    ]
    models.DataSourceResultTable.objects.bulk_create(ds_rt_objs)
    es_storage_obj = [
        models.ESStorage(table_id=DEFAULT_TABLE_ID_ONE, storage_cluster_id=1),
        models.ESStorage(table_id=DEFAULT_TABLE_ID_TWO, storage_cluster_id=1),
    ]
    models.ESStorage.objects.bulk_create(es_storage_obj)

    yield
    models.DataSourceResultTable.objects.filter(bk_data_id__in=[DEFAULT_DATA_ID_ONE, DEFAULT_DATA_ID_TWO]).delete()
    models.ESStorage.objects.filter(table_id__in=[DEFAULT_TABLE_ID_ONE, DEFAULT_TABLE_ID_TWO]).delete()


def test_query_es_index(create_and_delete_record, mocker):
    out = StringIO()
    mocker.patch(
        "metadata.service.es_storage.ESIndex._query_current_index",
        return_value={
            'index_version': 'v2',
            'datetime_object': datetime.datetime(2024, 5, 21, 0, 0),
            'index': 0,
            'size': 226,
        },
    )
    mocker.patch(
        "metadata.service.es_storage.ESIndex._query_all_index",
        return_value={
            "v2_test_demo1_20240521_0": {
                "aliases": {"test_demo1_20240521": {}},
                "settings": {"index": {"creation_date": "1716249671029"}},
            },
        },
    )
    call_command("query_es_index", bk_data_ids=f"{DEFAULT_DATA_ID_ONE}, {DEFAULT_DATA_ID_TWO}", stdout=out)
    output = out.getvalue()
    data = json.loads(output)
    assert set(data[DEFAULT_DATA_ID_ONE][0].keys()) == {"current_index", "all_index_and_alias", "can_delete_index"}
