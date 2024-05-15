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

pytestmark = pytest.mark.django_db

SPACE_TYPE = "bkcc"
SPACE_ID = "1"
TABLE_ID = "test.demo"
TABLE_FIELD_NAME = "cpu_load"


@pytest.fixture
def create_and_delete_record():
    """创建和删除记录"""
    models.Space.objects.create(id=1, space_type_id=SPACE_TYPE, space_id=SPACE_ID, space_name="test")
    models.ResultTable.objects.create(
        table_id=TABLE_ID,
        table_name_zh=TABLE_ID,
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
        bk_biz_id=int(SPACE_ID),
    )
    models.ResultTableField.objects.create(
        table_id=TABLE_ID,
        field_name=TABLE_FIELD_NAME,
        field_type="string",
        description="test",
        is_config_by_user=True,
    )
    models.AccessVMRecord.objects.create(
        result_table_id=TABLE_ID,
        bk_base_data_id=1,
        vm_result_table_id=TABLE_ID,
    )
    models.RecordRule.objects.create(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        table_id=TABLE_ID,
        record_name="test_demo",
        rule_config="",
        bk_sql_config=[],
        vm_cluster_id=1,
        dst_vm_table_id="2_test_demo",
    )
    models.SpaceVMInfo.objects.create(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        vm_cluster_id=1,
    )
    yield
    models.SpaceVMInfo.objects.filter(space_type=SPACE_TYPE, space_id=SPACE_ID, vm_cluster_id=1).delete()
    models.RecordRule.objects.filter(space_type=SPACE_TYPE, space_id=SPACE_ID, table_id=TABLE_ID).delete()
    models.AccessVMRecord.objects.filter(result_table_id=TABLE_ID).delete()
    models.ResultTableField.objects.filter(table_id=TABLE_ID).delete()
    models.ResultTable.objects.filter(table_id=TABLE_ID).delete()
    models.Space.objects.filter(space_type_id=SPACE_TYPE, space_id=SPACE_ID).delete()
