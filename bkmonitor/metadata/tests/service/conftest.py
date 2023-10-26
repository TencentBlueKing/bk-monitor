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
from metadata.tests.common_utils import CustomConsul

DEFAULT_TABLE_ID = "test.test"
DEFAULT_STORAGE_CLUSTER_ID = 100001
DEFAULT_PROXY_STORAGE_CLUSTER_ID = 10001

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_records(mocker):
    models.InfluxDBProxyStorage.objects.create(
        id=DEFAULT_PROXY_STORAGE_CLUSTER_ID,
        proxy_cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        service_name="bkmonitorv3",
        instance_cluster_name="default",
    )
    models.InfluxDBStorage.objects.create(
        table_id=DEFAULT_TABLE_ID, storage_cluster_id=DEFAULT_STORAGE_CLUSTER_ID, influxdb_proxy_storage_id=0
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="example.com",
        port=10,
        is_default_cluster=True,
    )
    models.AccessVMRecord.objects.create(
        data_type=models.AccessVMRecord.ACCESS_VM,
        bcs_cluster_id=None,
        result_table_id=DEFAULT_TABLE_ID,
        storage_cluster_id=1,
        vm_cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        bk_base_data_id=11001,
        vm_result_table_id="test_vm_rt",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=CustomConsul)
    models.InfluxDBProxyStorage.objects.filter(id=DEFAULT_PROXY_STORAGE_CLUSTER_ID).delete()
    models.InfluxDBStorage.objects.filter(table_id=DEFAULT_TABLE_ID).delete()
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_STORAGE_CLUSTER_ID).delete()
    models.AccessVMRecord.objects.filter(result_table_id=DEFAULT_TABLE_ID).delete()
