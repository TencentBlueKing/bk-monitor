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
from django.core.management import call_command
from mockredis import mock_redis_client

from metadata import models
from metadata.models.space.constants import SpaceTypes

from .conftest import DEFAULT_DATA_ID, consul_client

pytestmark = pytest.mark.django_db


@pytest.fixture
def clean_record():
    proxy_storage = models.InfluxDBProxyStorage.objects.get(instance_cluster_name="test_query.base")
    models.InfluxDBStorage.objects.all().update(influxdb_proxy_storage_id=proxy_storage.id)
    yield
    models.SpaceDataSource.objects.filter(space_id="bkciplatform").delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=DEFAULT_DATA_ID).delete()
    models.InfluxDBStorage.objects.all().update(influxdb_proxy_storage_id=None)
    models.Space.objects.filter(space_type_id="bkci").delete()
    models.SpaceDataSource.objects.filter(space_type_id="bkcc").delete()
    models.SpaceResource.objects.filter(resource_type="bkci").delete()


def test_exist_data_id(create_and_delete_record, clean_record, mocker):
    mocker.patch("metadata.utils.consul_tools.HashConsul", side_effect=consul_client)
    mocker.patch("metadata.utils.redis_tools.setup_client", side_effect=mock_redis_client)
    mocker.patch("celery.app.task.Task.delay", return_value=True)
    call_command("add_bkci_metrics_and_dimensions", f"--bk_data_id={DEFAULT_DATA_ID}", "--mq_cluster_id=1")
    assert models.DataSource.objects.get(bk_data_id=DEFAULT_DATA_ID).space_type_id == SpaceTypes.BKCI.value


def test_create_space(create_and_delete_record, clean_record, mocker):
    mocker.patch("metadata.utils.consul_tools.HashConsul", side_effect=consul_client)
    mocker.patch("metadata.utils.redis_tools.setup_client", side_effect=mock_redis_client)
    space_id = "bkciplatform"
    call_command(
        "add_bkci_metrics_and_dimensions",
        f"--space_id={space_id}",
        f"--bk_data_id={DEFAULT_DATA_ID}",
        "--mq_cluster_id=1",
    )
    assert models.Space.objects.filter(space_id=space_id).exists()
