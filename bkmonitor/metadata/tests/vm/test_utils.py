"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from metadata import models
from metadata.models.vm.utils import get_timestamp_len, get_vm_cluster_id_name
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db(databases="__all__")

DEFAULT_SPACE_TYPE = "bkcc"
DEFAULT_SPACE_ID = "12345"
DEFAULT_SPACE_ID_ONE = "1234567"
DEFAULT_DATA_ID = 100010
DEFAULT_DATA_ID_ONE = 100011
DEFAULT_BCS_CLUSTER_ID = "BCS-K8S-00000"
DEFAULT_STORAGE_CLUSTER_ID = 121
DEFAULT_STORAGE_CLUSTER_ID_ONE = 122
DEFAULT_STORAGE_CLUSTER_ID_TWO = 123
DEFAULT_STORAGE_CLUSTER_ID_THREE = 124
DEFAULT_STORAGE_CLUSTER_ID_FOUR = 125
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
        data_name="test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_exporter",
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSource.objects.create(
        bk_data_id=500002,
        data_name="test2",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_exporter",
        is_custom_source=False,
        is_enable=False,
    )
    models.DataSourceOption.objects.create(
        bk_data_id=500002, name=models.DataSourceOption.OPTION_ALIGN_TIME_UNIT, value="ms"
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
        cluster_id__in=[
            DEFAULT_STORAGE_CLUSTER_ID,
            DEFAULT_STORAGE_CLUSTER_ID_ONE,
            DEFAULT_STORAGE_CLUSTER_ID_TWO,
            DEFAULT_STORAGE_CLUSTER_ID_THREE,
            DEFAULT_STORAGE_CLUSTER_ID_FOUR,
        ]
    ).delete()
    models.SpaceVMInfo.objects.all().delete()


@pytest.fixture
def create_or_delete_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=500001,
        data_name="test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_exporter",
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
@pytest.mark.django_db(databases="__all__")
def test_get_timestamp_len(data_id, etl_config, expected_value, create_and_delete_record):
    assert get_timestamp_len(data_id, etl_config) == expected_value


def create_vm_cluster(cluster_id: int, cluster_name: str, default_settings: dict | None = None):
    return models.ClusterInfo.objects.create(
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name=f"{cluster_name}.domain",
        port=9090,
        username="admin",
        password="1234",
        is_default_cluster=False,
        is_ssl_verify=False,
        default_settings=default_settings or {},
    )


@pytest.mark.django_db(databases="__all__")
def test_get_vm_cluster_id_name_priority_biz_cluster(create_and_delete_record):
    create_vm_cluster(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_TWO,
        cluster_name="biz_vm_cluster",
        default_settings={"bk_biz_id": DEFAULT_SPACE_ID},
    )

    actual = get_vm_cluster_id_name(
        bk_tenant_id="system",
        space_type=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
    )

    assert actual == {"cluster_id": DEFAULT_STORAGE_CLUSTER_ID_TWO, "cluster_name": "biz_vm_cluster"}


@pytest.mark.django_db(databases="__all__")
def test_get_vm_cluster_id_name_select_latest_biz_cluster(create_and_delete_record):
    create_vm_cluster(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_TWO,
        cluster_name="biz_vm_cluster",
        default_settings={"bk_biz_id": DEFAULT_SPACE_ID},
    )
    create_vm_cluster(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_THREE,
        cluster_name="latest_biz_vm_cluster",
        default_settings={"bk_biz_id": str(DEFAULT_SPACE_ID)},
    )

    actual = get_vm_cluster_id_name(
        bk_tenant_id="system",
        space_type=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
    )

    assert actual == {"cluster_id": DEFAULT_STORAGE_CLUSTER_ID_THREE, "cluster_name": "latest_biz_vm_cluster"}


@pytest.mark.django_db(databases="__all__")
def test_get_vm_cluster_id_name_for_bkci_related_biz(mocker, create_and_delete_record):
    bkci_space_id = "bkci_project"
    get_related_space = mocker.patch(
        "metadata.models.vm.utils.SpaceApi.get_related_space",
        return_value=SimpleNamespace(bk_biz_id=DEFAULT_SPACE_ID_ONE),
    )
    models.SpaceVMInfo.objects.create(
        space_type="bkci",
        space_id=bkci_space_id,
        vm_cluster_id=DEFAULT_STORAGE_CLUSTER_ID_ONE,
    )
    create_vm_cluster(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_TWO,
        cluster_name="bkci_related_biz_vm_cluster",
        default_settings={"bk_biz_id": DEFAULT_SPACE_ID_ONE},
    )

    actual = get_vm_cluster_id_name(
        bk_tenant_id="system",
        space_type="bkci",
        space_id=bkci_space_id,
    )

    get_related_space.assert_called_once_with(space_uid=f"bkci__{bkci_space_id}", related_space_type="bkcc")
    assert actual == {
        "cluster_id": DEFAULT_STORAGE_CLUSTER_ID_TWO,
        "cluster_name": "bkci_related_biz_vm_cluster",
    }


@pytest.mark.django_db(databases="__all__")
def test_get_vm_cluster_id_name_fallback_to_space_vm_info(create_and_delete_record):
    actual = get_vm_cluster_id_name(
        bk_tenant_id="system",
        space_type=DEFAULT_SPACE_TYPE,
        space_id=DEFAULT_SPACE_ID,
    )

    assert actual == {"cluster_id": DEFAULT_STORAGE_CLUSTER_ID_ONE, "cluster_name": "test_vm_cluster"}


@pytest.mark.django_db(databases="__all__")
def test_get_vm_cluster_id_name_fallback_to_latest_default_cluster(create_and_delete_record):
    create_vm_cluster(
        cluster_id=DEFAULT_STORAGE_CLUSTER_ID_FOUR,
        cluster_name="latest_default_vm_cluster",
    )
    models.ClusterInfo.objects.filter(cluster_id=DEFAULT_STORAGE_CLUSTER_ID_FOUR).update(is_default_cluster=True)

    actual = get_vm_cluster_id_name(
        bk_tenant_id="system",
        space_type=DEFAULT_SPACE_TYPE,
        space_id="not_access_vm",
    )

    assert actual == {"cluster_id": DEFAULT_STORAGE_CLUSTER_ID_FOUR, "cluster_name": "latest_default_vm_cluster"}
