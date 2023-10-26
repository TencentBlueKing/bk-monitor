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

from metadata import models

pytestmark = pytest.mark.django_db

DEFAULT_NAME = "test_query"


@pytest.fixture
def clean_records():
    yield
    models.InfluxDBHostInfo.objects.filter(host_name=DEFAULT_NAME).delete()
    models.InfluxDBClusterInfo.objects.filter(cluster_name=DEFAULT_NAME).delete()


def test_add_influxdb_instance(clean_records):
    influxdb_hosts = [{"host_name": DEFAULT_NAME, "domain": "test.host", "port": 8086, "is_disabled": False}]
    params = {"influxdb_cluster_name": DEFAULT_NAME, "influxdb_hosts": influxdb_hosts}
    call_command("add_influxdb_instance", **params)
    assert models.InfluxDBHostInfo.objects.filter(host_name=DEFAULT_NAME).exists()
    assert models.InfluxDBClusterInfo.objects.filter(cluster_name=DEFAULT_NAME).exists()
