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

from metadata.models.space import ds_rt

from .conftest import DEFAULT_DATA_ID, DEFAULT_TABLE_ID

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "data_id_list, table_id_list, expected_data",
    [
        (None, None, {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        ([123], None, {}),
        (None, ["test.not_exist"], {}),
        ([DEFAULT_DATA_ID], None, {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        (None, [DEFAULT_TABLE_ID], {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
        ([123], [DEFAULT_TABLE_ID], {}),
        ([DEFAULT_DATA_ID], ["test.not_exist"], {}),
        ([DEFAULT_DATA_ID], [DEFAULT_TABLE_ID], {DEFAULT_TABLE_ID: DEFAULT_DATA_ID}),
    ],
)
def test_get_result_tables_by_data_ids(create_and_delete_record, data_id_list, table_id_list, expected_data):
    assert ds_rt.get_result_tables_by_data_ids(data_id_list, table_id_list) == expected_data


def test_get_table_info_for_influxdb_and_vm(create_and_delete_record):
    data = ds_rt.get_table_info_for_influxdb_and_vm([DEFAULT_TABLE_ID])
    keys = ["cluster_name", "db", "measurement", "storage_id", "vm_rt"]
    assert set(keys) == set(data[DEFAULT_TABLE_ID].keys())

    data = ds_rt.get_table_info_for_influxdb_and_vm(["test.not_exist"])
    assert not data
