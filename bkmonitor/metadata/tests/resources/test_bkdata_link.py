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

import pytest

from metadata import config, models
from metadata.resources import AddBkDataTableIdsResource
from metadata.utils.redis_tools import RedisTools

DEFAULT_RT_ID = "test.demo"
DEFAULT_VM_DATA_ID = 100011
DEFAULT_VM_RT_ID = "test_demo"

pytestmark = pytest.mark.django_db


@pytest.fixture
def create_and_delete_records():
    models.AccessVMRecord.objects.create(
        result_table_id=DEFAULT_RT_ID, bk_base_data_id=DEFAULT_VM_DATA_ID, vm_result_table_id=DEFAULT_VM_RT_ID
    )
    yield
    models.AccessVMRecord.objects.filter(result_table_id=DEFAULT_RT_ID).delete()


def test_add_bkdata_table_ids_to_exist_data(create_and_delete_records, patch_redis_tools):
    """测试数据不存在"""
    RedisTools.set(config.METADATA_RESULT_TABLE_WHITE_LIST, json.dumps(["test_exist.demo"]))

    AddBkDataTableIdsResource().request(bkdata_table_ids=[DEFAULT_VM_RT_ID])

    data = RedisTools.get_list(config.METADATA_RESULT_TABLE_WHITE_LIST)
    assert {"test_exist.demo", DEFAULT_RT_ID}.issubset(set(data))


def test_add_bkdata_table_ids_without_redis_key(create_and_delete_records, patch_redis_tools):
    """测试redis中还没有key"""
    RedisTools.delete(config.METADATA_RESULT_TABLE_WHITE_LIST)

    AddBkDataTableIdsResource().request(bkdata_table_ids=[DEFAULT_VM_RT_ID])

    data = RedisTools.get_list(config.METADATA_RESULT_TABLE_WHITE_LIST)

    assert set(data) == {DEFAULT_RT_ID}
