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

DEFAULT_DOMAIN_NAME = "cluster_name_one"
DEFAULT_DATA_ID = 11000
DEFAULT_DATA_ID_TWO = 11001
DEFAULT_DATA_ID_THREE = 11002
DEFAULT_NAME = "test_data_source"
DEFAULT_NAME_TWO = "bkdata_source"
DEFAULT_NAME_THREE = "disabled_source"


@pytest.fixture
def create_and_delete_data(mocker):
    # Create the test data
    cluster = models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_DATA_ID,
        cluster_name=DEFAULT_DOMAIN_NAME,
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name=DEFAULT_DOMAIN_NAME,
        port=80,
        is_default_cluster=False,
    )

    objs = [
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID,
            data_name=DEFAULT_NAME,
            mq_cluster_id=cluster.cluster_id,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
            is_enable=True,
            created_from='bkgse',
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID_TWO,
            data_name=DEFAULT_NAME_TWO,
            mq_cluster_id=cluster.cluster_id,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
            is_enable=True,
            created_from='bkdata',
        ),
        models.DataSource(
            bk_data_id=DEFAULT_DATA_ID_THREE,
            data_name=DEFAULT_NAME_THREE,
            mq_cluster_id=cluster.cluster_id,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
            is_enable=False,
            created_from='bkgse',
        ),
    ]

    models.DataSource.objects.bulk_create(objs)
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)

    # Clean up the test data
    models.DataSource.objects.filter(
        bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID_TWO, DEFAULT_DATA_ID_THREE]
    ).delete()
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_DATA_ID).delete()


@pytest.mark.django_db(databases=['default', 'monitor_api'])
def test_query_data(create_and_delete_data):
    """
    Verify that the query_data_id_by_mq command returns the correct data source IDs
    """
    out = StringIO()
    call_command("query_data_id_by_mq", "--domain_name", DEFAULT_DOMAIN_NAME, stdout=out)
    output = out.getvalue()
    data = json.loads(output)

    # Verify the remaining valid data source IDs
    assert len(data) == 1
    assert data[0] == DEFAULT_DATA_ID
