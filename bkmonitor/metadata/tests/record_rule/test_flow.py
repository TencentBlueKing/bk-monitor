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
from django.conf import settings

from metadata.models.record_rule.rules import RecordRule, ResultTableFlow

from .conftest import TABLE_ID

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("table_id, flow_name", [("", ""), ("test", "test"), ("test.demo", "test_demo")])
def test_compose_flow_name(table_id, flow_name):
    assert ResultTableFlow.compose_flow_name(table_id) == flow_name


def test_compose_source_node():
    vm_table_ids = ["1_test", "1_test1"]
    nodes = ResultTableFlow.compose_source_node(vm_table_ids)
    assert len(nodes) == 2

    assert nodes[0]["id"] == 1
    assert nodes[1]["id"] == 2

    assert nodes[0]["result_table_id"] == vm_table_ids[0]
    assert nodes[0]["name"] == vm_table_ids[0]
    assert nodes[1]["result_table_id"] == vm_table_ids[1]
    assert nodes[1]["name"] == vm_table_ids[1]


def test_compose_process_node(create_and_delete_record):
    node = ResultTableFlow.compose_process_node(TABLE_ID, [TABLE_ID])

    assert type(node) == dict
    assert node["node_type"] == "promql_v2"

    assert node["outputs"][0]["bk_biz_id"] == settings.DEFAULT_BKDATA_BIZ_ID
    assert node["from_result_table_ids"] == [TABLE_ID]


def test_compose_vm_storage(create_and_delete_record):
    node = ResultTableFlow.compose_vm_storage(TABLE_ID, 4)

    assert type(node) == dict
    assert node["id"] == 5
    assert node["node_type"] == "vm_storage"
    assert node["from_result_table_ids"] == [RecordRule.get_dst_table_id(TABLE_ID)]


def test_create_flow(create_and_delete_record, mocker):
    flow_id = 3079
    mocker.patch(
        "core.drf_resource.api.bkdata.apply_data_flow",
        return_value={"node_ids": [18263, 18264, 18265, 18266, 18267], "flow_id": 3079},
    )
    ResultTableFlow.create_flow(TABLE_ID)

    # 校验数据
    obj = ResultTableFlow.objects.filter(table_id=TABLE_ID).first()
    assert obj is not None
    assert obj.flow_id == flow_id
