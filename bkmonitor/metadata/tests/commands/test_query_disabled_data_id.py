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
from io import StringIO

import pytest
from django.core.management import call_command

from metadata import models
from metadata.tests.commands.conftest import consul_client

DEFAULT_DATA_ID = 11000
DEFAULT_NAME = "test_data_source"
DEFAULT_DATA_ID_TWO = 11001
DEFAULT_NAME_TWO = "test_data_source_delete_20240520161416"
DEFAULT_DATA_ID_THREE = 11002
DEFAULT_NAME_THREE = "test_data_source1"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_data(mocker):
    objs = [
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID,
            data_name=DEFAULT_NAME,
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID_TWO,
            data_name=DEFAULT_NAME_TWO,
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID_THREE,
            data_name=DEFAULT_NAME_THREE,
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
            is_enable=False,
        ),
    ]
    models.DataSource.objects.bulk_create(objs)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(
        bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID_TWO, DEFAULT_DATA_ID_THREE]
    ).delete()


@pytest.mark.django_db(databases=['default', 'monitor_api'])
def test_query_data(create_and_delete_data):
    out = StringIO()
    call_command("query_disabled_data_id", "--all", stdout=out)
    output = out.getvalue()
    data = json.loads(output)
    assert data["count"] == 2
    assert isinstance(data["result"], list)
    assert set(data["result"]) == {11001, 11002}
