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
from metadata.resources.vm import QueryBizByBkBase, QueryVmRtBySpace
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db

DEFAULT_DATA_ID = 10000011
DEFAULT_DATA_ID_ONE = 10000012
DEFAULT_DATA_ID_TWO = 10000013
DEFAULT_DATA_ID_NAME = "vm_test"
DEFAULT_DATA_ID_NAME_ONE = "10011_vm_test"
DEFAULT_DATA_ID_NAME_TWO = "vm_test_10011"
DEFAULT_RT_ID = "test.demo"
DEFAULT_RT_ID_ONE = "test.demo1"
DEFAULT_RT_ID_TWO = "test.demo2"
DEFAULT_BIZ_ID = 10011
DEFAULT_BIZ_ID_ONE = 0
DEFAULT_BIZ_ID_TWO = 0
DEFAULT_VM_DATA_ID = 100011
DEFAULT_VM_DATA_ID_ONE = 100012
DEFAULT_VM_DATA_ID_TWO = 100013
DEFAULT_VM_RT_ID = "vm_test"
DEFAULT_VM_RT_ID_ONE = "vm_test1"
DEFAULT_VM_RT_ID_TWO = "vm_test2"


@pytest.fixture
def create_and_delete_records(mocker):
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID,
        data_name=DEFAULT_DATA_ID_NAME,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID_ONE,
        data_name=DEFAULT_DATA_ID_NAME_ONE,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
    )
    models.DataSource.objects.create(
        bk_data_id=DEFAULT_DATA_ID_TWO,
        data_name=DEFAULT_DATA_ID_NAME_TWO,
        mq_cluster_id=1,
        mq_config_id=1,
        is_custom_source=True,
    )
    models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID, table_id=DEFAULT_RT_ID)
    models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID_ONE, table_id=DEFAULT_RT_ID_ONE)
    models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID_TWO, table_id=DEFAULT_RT_ID_TWO)
    models.ResultTable.objects.create(table_id=DEFAULT_RT_ID, bk_biz_id=DEFAULT_BIZ_ID, is_custom_table=True)
    models.ResultTable.objects.create(table_id=DEFAULT_RT_ID_ONE, bk_biz_id=DEFAULT_BIZ_ID_ONE, is_custom_table=True)
    models.ResultTable.objects.create(table_id=DEFAULT_RT_ID_TWO, bk_biz_id=DEFAULT_BIZ_ID_TWO, is_custom_table=True)
    models.AccessVMRecord.objects.create(
        result_table_id=DEFAULT_RT_ID, bk_base_data_id=DEFAULT_VM_DATA_ID, vm_result_table_id=DEFAULT_VM_RT_ID
    )
    models.AccessVMRecord.objects.create(
        result_table_id=DEFAULT_RT_ID_ONE,
        bk_base_data_id=DEFAULT_VM_DATA_ID_ONE,
        vm_result_table_id=DEFAULT_VM_RT_ID_ONE,
    )
    models.AccessVMRecord.objects.create(
        result_table_id=DEFAULT_RT_ID_TWO,
        bk_base_data_id=DEFAULT_VM_DATA_ID_TWO,
        vm_result_table_id=DEFAULT_VM_RT_ID_TWO,
    )
    models.EventGroup.objects.create(
        table_id=DEFAULT_RT_ID_TWO,
        bk_data_id=DEFAULT_DATA_ID_TWO,
        bk_biz_id=DEFAULT_BIZ_ID_TWO,
    )
    models.TimeSeriesGroup.objects.create(
        table_id=DEFAULT_RT_ID_ONE,
        bk_data_id=DEFAULT_DATA_ID_ONE,
        bk_biz_id=DEFAULT_BIZ_ID_ONE,
    )
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id=DEFAULT_BIZ_ID_ONE,
        space_name="test_demo",
    )
    yield
    models.Space.objects.filter(space_type_id="bkcc", space_id__in=[DEFAULT_BIZ_ID_ONE]).delete()
    models.EventGroup.objects.filter(table_id=DEFAULT_RT_ID_TWO).delete()
    models.TimeSeriesGroup.objects.filter(table_id=DEFAULT_RT_ID_ONE).delete()
    models.AccessVMRecord.objects.filter(
        result_table_id__in=[DEFAULT_RT_ID, DEFAULT_RT_ID_ONE, DEFAULT_RT_ID_TWO]
    ).delete()
    models.ResultTable.objects.filter(table_id__in=[DEFAULT_RT_ID, DEFAULT_RT_ID_ONE, DEFAULT_RT_ID_TWO]).delete()
    models.DataSourceResultTable.objects.filter(
        table_id__in=[DEFAULT_RT_ID, DEFAULT_RT_ID_ONE, DEFAULT_RT_ID_TWO]
    ).delete()
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.filter(
        bk_data_id__in=[DEFAULT_DATA_ID, DEFAULT_DATA_ID_ONE, DEFAULT_DATA_ID_TWO]
    ).delete()


def test_query_biz_by_bk_base_params_error():
    with pytest.raises(ValueError):
        QueryBizByBkBase().request()


def test_query_biz_by_bk_base_with_vm_table_id(create_and_delete_records):
    params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID

    # 测试为 0 业务，并且在 ts group 中场景
    params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID_ONE]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])

    # 测试为 0 业务，并且在 event group 中场景
    params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID_TWO]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])

    # 包含三个场景
    params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID, DEFAULT_VM_RT_ID_ONE, DEFAULT_VM_RT_ID_TWO]}
    resp = QueryBizByBkBase().request(params)
    assert len(resp) == 3
    assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID
    assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])
    assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])


def test_query_biz_by_bk_base_with_vm_data_id(create_and_delete_records):
    params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID

    # 测试为 0 业务，并且在 ts group 中场景
    params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID_ONE]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])

    # 测试为 0 业务，并且在 event group 中场景
    params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID_TWO]}
    resp = QueryBizByBkBase().request(params)
    assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])

    # 包含三个场景
    params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID, DEFAULT_VM_DATA_ID_ONE, DEFAULT_VM_DATA_ID_TWO]}
    resp = QueryBizByBkBase().request(params)
    assert len(resp) == 3
    assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID
    assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])
    assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])


def test_query_biz_by_bk_base_with_error_id(create_and_delete_records):
    params = {"bk_base_data_id_list": [123123123123]}
    resp = QueryBizByBkBase().request(params)
    assert len(resp) == 0


def test_query_vm_rt_without_plugin(create_and_delete_records):
    params = {"space_type": "bkcc", "space_id": "0"}
    resp = QueryVmRtBySpace().request(params)
    assert len(resp) == 3
    assert {DEFAULT_VM_RT_ID, DEFAULT_VM_RT_ID_ONE, DEFAULT_VM_RT_ID_TWO} == set(resp)
