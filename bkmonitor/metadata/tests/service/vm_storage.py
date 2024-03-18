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
from metadata.service.vm_storage import (
    disable_influxdb_router_for_vm_table,
    query_vm_datalink,
)
from metadata.tests.common_utils import CustomConsul

from .conftest import (
    DEFAULT_DATA_ID,
    DEFAULT_PROXY_STORAGE_CLUSTER_ID,
    DEFAULT_TABLE_ID,
)

pytestmark = pytest.mark.django_db


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
