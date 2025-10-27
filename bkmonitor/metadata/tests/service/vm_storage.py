"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from metadata.service.vm_storage import (
    disable_influxdb_router_for_vm_table,
    query_vm_datalink,
    query_vm_datalink_all,
)
from metadata.tests.common_utils import CustomConsul, consul_client

from .conftest import (
    DEFAULT_DATA_ID,
    DEFAULT_PROXY_STORAGE_CLUSTER_ID,
    DEFAULT_TABLE_ID,
)

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="system",
    )
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
        bk_tenant_id="system",
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system",
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_data_id=50010,
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_result_table_id="1001_vm_test_50010",
        bk_tenant_id="system",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    result_table.delete()


def test_disable_influxdb_router_for_vm_table(create_and_delete_records, mocker):
    mocker.patch("metadata.models.DataSource.refresh_outer_config", return_value=True)
    mocker.patch("metadata.models.InfluxDBStorage.refresh_consul_cluster_config", return_value=True)
    mocker.patch("metadata.service.vm_storage.consul_tools.refresh_router_version", return_value=True)
    mocker.patch("metadata.models.AccessVMRecord.refresh_vm_router", return_value=True)

    # 测试使用默认
    disable_influxdb_router_for_vm_table(table_ids=[DEFAULT_TABLE_ID])
    assert (
        models.InfluxDBStorage.objects.get(table_id=DEFAULT_TABLE_ID).influxdb_proxy_storage_id
        == DEFAULT_PROXY_STORAGE_CLUSTER_ID
    )

    # 测试删除记录的场景
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=CustomConsul)
    disable_influxdb_router_for_vm_table(table_ids=[DEFAULT_TABLE_ID], can_deleted=True)
    assert not models.InfluxDBStorage.objects.filter(table_id=DEFAULT_TABLE_ID).exists()


def test_not_enable_datasource_dl(create_and_delete_datalink_records, mocker):
    data = query_vm_datalink(DEFAULT_DATA_ID + 1)

    assert data["is_enabled"] is False
    assert "result_table_list" not in data


def test_not_enable_rt_dl(create_and_delete_datalink_records, mocker):
    data = query_vm_datalink(DEFAULT_DATA_ID + 2)

    assert data["is_enabled"] is True
    assert data["result_table_list"] == []


def test_rt_dl(create_and_delete_datalink_records, mocker):
    data = query_vm_datalink(DEFAULT_DATA_ID)

    assert data["is_enabled"] is True
    assert "result_table_list" in data
    result_table_list = data["result_table_list"]
    assert len(result_table_list) == 1
    assert result_table_list[0]["result_table"] == DEFAULT_TABLE_ID


def test_query_vm_datalink_all(create_or_delete_records):
    """
    测试查询VM数据链路
    """
    res = query_vm_datalink_all(bk_data_id=50010)
    expected = None
    assert res == expected
