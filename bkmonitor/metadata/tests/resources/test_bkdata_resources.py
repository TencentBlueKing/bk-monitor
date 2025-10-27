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
from metadata.resources import SyncBkBaseRtMetaByBizIdResource


@pytest.fixture
def create_or_delete_records(mocker):
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id="123456789",
        status="normal",
        space_code="test_bkcc_space",
        space_name="test_bkcc_space",
    )
    yield
    models.Space.objects.all().delete()


# 计算平台Meta接口的返回值(这里只Mock了监控平台需要关注的部分)
bkbase_rt_meta_api_return_data = [
    {
        "result_table_name": "test_treat_diversion_plan_1",
        "bk_biz_id": 7,
        "created_at": "2024-09-26 14:29:35",
        "sensitivity": "private",
        "result_table_name_alias": "test_treat_diversion_plan_1",
        "updated_by": "admin",
        "created_by": "admin",
        "result_table_id": "test_treat_diversion_plan_1",
        "count_freq": 0,
        "description": "test_treat_diversion_plan_1",
        "updated_at": "2024-09-26 14:31:40",
        "generate_type": "user",
        "result_table_type": None,
        "processing_type": "stream",
        "project_id": 1,
        "platform": "bk_data",
        "is_managed": 1,
        "count_freq_unit": "S",
        "data_category": "UTF8",
        "project_name": "\\u84dd\\u9cb8\\u76d1\\u63a7",
        "fields": [
            {
                "roles": {"event_time": False},
                "field_type": "timestamp",
                "description": "timestamp",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "timestamp",
                "field_name": "timestamp",
                "id": 825962,
                "field_index": 1,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_startTime_",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "_startTime_",
                "field_name": "_startTime_",
                "id": 825963,
                "field_index": 2,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_endTime_",
                "created_at": "2024-09-26 14:29:35",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:40",
                "origins": "",
                "field_alias": "_endTime_",
                "field_name": "_endTime_",
                "id": 825964,
                "field_index": 3,
                "updated_by": "admin",
            },
        ],
        "storages": {
            "pulsar": {"id": 1234567, "updated_by": "admin"},
            "tspider": {
                "id": 12345678,
                "updated_by": "admin",
                "generate_type": "user",
                "active": True,
                "priority": 0,
                "created_by": "admin",
            },
        },
        "tags": {"manage": {"geog_area": [{"code": "inland", "alias": "\\u4e2d\\u56fd\\u5185\\u5730"}]}},
    },
    {
        "result_table_name": "test_ss_entry_61_INPUT",
        "bk_biz_id": 2,
        "created_at": "2024-09-26 14:30:37",
        "sensitivity": "private",
        "result_table_name_alias": "instance_61_entry_INPUT",
        "updated_by": "admin",
        "created_by": "admin",
        "result_table_id": "2_test_ss_entry_61_INPUT",
        "count_freq": 0,
        "description": "instance_61_entry_INPUT",
        "updated_at": "2024-09-26 14:31:24",
        "generate_type": "user",
        "result_table_type": None,
        "processing_type": "stream",
        "project_id": 1,
        "platform": "bk_data",
        "is_managed": 1,
        "count_freq_unit": "S",
        "data_category": "UTF8",
        "project_name": "\\u84dd\\u9cb8\\u76d1\\u63a7",
        "fields": [
            {
                "roles": {"event_time": False},
                "field_type": "timestamp",
                "description": "timestamp",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": True,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "timestamp",
                "field_name": "timestamp",
                "id": 825975,
                "field_index": 1,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_startTime_",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "_startTime_",
                "field_name": "_startTime_",
                "id": 825976,
                "field_index": 2,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "string",
                "description": "_endTime_",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "_endTime_",
                "field_name": "_endTime_",
                "id": 825977,
                "field_index": 3,
                "updated_by": "admin",
            },
            {
                "roles": {"event_time": False},
                "field_type": "double",
                "description": "value",
                "created_at": "2024-09-26 14:30:37",
                "is_dimension": False,
                "created_by": "admin",
                "updated_at": "2024-09-26 14:31:24",
                "origins": "",
                "field_alias": "value",
                "field_name": "value",
                "id": 825978,
                "field_index": 4,
                "updated_by": "admin",
            },
        ],
        "storages": {
            "pulsar": {"id": 193678, "storage_config": "{}", "active": True, "priority": 10},
            "hdfs": {
                "id": 193679,
                "physical_table_name": "test.test",
                "updated_by": "admin",
                "result_table_id": "2_test_ss_entry_61_INPUT",
            },
        },
        "tags": {"manage": {"geog_area": [{"code": "inland", "alias": "\\u4e2d\\u56fd\\u5185\\u5730"}]}},
    },
]


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_rt_by_biz_id(mocker, create_or_delete_records):
    mocker.patch(
        "core.drf_resource.api.bkdata.bulk_list_result_table",
        return_value=bkbase_rt_meta_api_return_data,
    )
    mocker.patch("django.conf.settings.ENABLE_SYNC_BKBASE_META_TASK", True)

    SyncBkBaseRtMetaByBizIdResource().request(bk_biz_id=7)

    rt_ins_1 = models.ResultTable.objects.get(table_id="test_treat_diversion_plan_1.__default__")
    assert rt_ins_1.bk_biz_id == 7
    assert rt_ins_1.table_name_zh == "test_treat_diversion_plan_1"
    assert rt_ins_1.default_storage == "bkdata"

    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="timestamp"
        ).tag
        == "metric"
    )
    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="_startTime_"
        ).tag
        == "metric"
    )
    assert (
        models.ResultTableField.objects.get(
            table_id="test_treat_diversion_plan_1.__default__", field_name="_endTime_"
        ).tag
        == "metric"
    )
