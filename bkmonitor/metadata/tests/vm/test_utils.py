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
from metadata.models.vm.utils import get_timestamp_len
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db

DEFAULT_SPACE_TYPE = "bkcc"
DEFAULT_SPACE_ID = "12345"
DEFAULT_SPACE_ID_ONE = "1234567"
DEFAULT_DATA_ID = 100010
DEFAULT_DATA_ID_ONE = 100011
DEFAULT_BCS_CLUSTER_ID = "BCS-K8S-00000"
DEFAULT_STORAGE_CLUSTER_ID = 121
DEFAULT_STORAGE_CLUSTER_ID_ONE = 122
DEFAULT_BKDATA_ID = 1000010
DEFAULT_VM_RT_ID = "bkdata_test_demo"
TABLE_ID = "test_table_id.demo"
VM_ETL_CONFIG = "bk_standard_v2_time_series"
EXPORTER_ETL_CONFIG = "bk_exporter"


@pytest.fixture
def create_and_delete_record(mocker):
    models.Space.objects.create(space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, space_name="test_demo")
    models.Space.objects.create(
        space_type_id=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID_ONE, space_name="test_demo2"
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_DATA_ID,
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=VM_ETL_CONFIG,
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID_ONE,
        data_name=DEFAULT_DATA_ID_ONE,
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EXPORTER_ETL_CONFIG,
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSource.objects.create(
        bk_data_id=500001,
        data_name='test',
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config='bk_exporter',
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSource.objects.create(
        bk_data_id=500002,
        data_name='test2',
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config='bk_exporter',
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSourceOption.objects.create(
        bk_data_id=500002, name=models.DataSourceOption.OPTION_ALIGN_TIME_UNIT, value='ms'
    )
    models.BCSClusterInfo.objects.create(
        **{
            "cluster_id": DEFAULT_BCS_CLUSTER_ID,
            "bcs_api_cluster_id": DEFAULT_BCS_CLUSTER_ID,
            "bk_biz_id": 2,
            "project_id": "2",
            "status": "running",
            "domain_name": "domain_name_2",
            "port": 8000,
            "server_address_path": "clusters",
            "api_key_type": "authorization",
            "api_key_content": "",
            "api_key_prefix": "Bearer",
            "is_skip_ssl_verify": True,
            "cert_content": None,
            "K8sMetricDataID": DEFAULT_DATA_ID,
            "CustomMetricDataID": 6,
            "K8sEventDataID": 7,
            "CustomEventDataID": 8,
            "SystemLogDataID": 0,
            "CustomLogDataID": 0,
            "creator": "admin",
            "last_modify_user": "",
        }
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID,
        cluster_name="test_kafka_cluster",
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        domain_name="test.domain.mq",
        port=9090,
        username="admin",
        password="1234",
        is_default_cluster=True,
        is_ssl_verify=False,
    )
    models.ClusterInfo.objects.create(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_ONE,
        cluster_name="test_vm_cluster",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.mq",
        port=9090,
        username="admin",
        password="1234",
        is_default_cluster=True,
        is_ssl_verify=False,
    )
    models.SpaceVMInfo.objects.create(
        space_type=DEFAULT_SPACE_TYPE, space_id=DEFAULT_SPACE_ID, vm_cluster_id=DEFAULT_STORAGE_CLUSTER_ID_ONE
    )
    yield
    models.Space.objects.all().delete()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID_ONE]).delete()
    models.BCSClusterInfo.objects.all().delete()
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_STORAGE_CLUSTER_ID).delete()
    models.KafkaStorage.objects.filter(table_id=TABLE_ID).delete()
    models.AccessVMRecord.objects.all().delete()
    models.ClusterInfo.objects.filter(
        cluster_id__in=[DEFAULT_STORAGE_CLUSTER_ID_ONE, DEFAULT_STORAGE_CLUSTER_ID]
    ).delete()
    models.SpaceVMInfo.objects.all().delete()


@pytest.fixture
def create_or_delete_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=500001,
        data_name='test',
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config='bk_exporter',
        is_custom_source=False,
        is_enable=False,
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(bk_data_id__in=[500001]).delete()


@pytest.mark.parametrize(
    "data_id, etl_config, expected_value",
    [
        (None, None, 13),
        (12321, None, 13),
        (DEFAULT_DATA_ID, None, 13),
        (DEFAULT_DATA_ID_ONE, None, 10),
        (None, "bk_exporter", 13),
        (DEFAULT_DATA_ID, "bk_exporter", 13),
        (DEFAULT_DATA_ID_ONE, "bk_exporter", 10),
        (12321, "bk_exporter", 13),
        (1100006, "bk_exporter", 19),
        (500001, None, 10),
        (500002, "bk_exporter", 13),  # 存在Option，则以Option为主
    ],
)
@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_get_timestamp_len(data_id, etl_config, expected_value, create_and_delete_record):
    assert get_timestamp_len(data_id, etl_config) == expected_value
