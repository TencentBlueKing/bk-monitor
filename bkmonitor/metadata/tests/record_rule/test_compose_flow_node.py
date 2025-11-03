"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

import pytest

from metadata import models
from metadata.models.record_rule.rules import RecordRule, ResultTableFlow
from metadata.tests.record_rule.conftest import record_name, table_id


@pytest.mark.django_db(databases="__all__")
def test_compose_source_node_config(create_or_delete_records, create_default_record_rule):
    """
    测试根节点配置能否正常组装
    """
    rule_obj = RecordRule.objects.get(table_id=table_id)
    assert rule_obj.record_name == record_name
    assert rule_obj.dst_vm_table_id == "2_vm_cc_2_unify_query_tsdb_test_new_prom_node"

    source_node_config = ResultTableFlow.compose_source_node(rule_obj.src_vm_table_ids)
    expected = (
        '[{"id":1,"node_type":"stream_source","bk_biz_name":"2","bk_biz_id":2,'
        '"result_table_id":"2_bcs_custom_metric_result_table_00000",'
        '"name":"2_bcs_custom_metric_result_table_00000","from_result_table_ids":['
        '"2_bcs_custom_metric_result_table_00000"],"from_nodes":[]}]'
    )

    assert json.dumps(source_node_config) == expected


@pytest.mark.django_db(databases="__all__")
def test_compose_process_node_config(create_or_delete_records, create_default_record_rule):
    """
    测试计算节点配置能否正常组装
    """
    rule_obj = RecordRule.objects.get(table_id=table_id)
    assert rule_obj.record_name == record_name
    assert rule_obj.dst_vm_table_id == "2_vm_cc_2_unify_query_tsdb_test_new_prom_node"

    expected = {
        "id": 2,
        "name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
        "node_type": "promql_v2",
        "outputs": [
            {
                "bk_biz_id": 2,
                "fields": [],
                "output_name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
                "table_name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
            }
        ],
        "bk_biz_id": 2,
        "from_result_table_ids": ["2_bcs_custom_metric_result_table_00000"],
        "dedicated_config": {
            "waiting_time": 30,
            "sql_list": [
                {
                    "name": "unify_query_tsdb_request_seconds_bucket_sum_2m",
                    "count_freq": 60,
                    "sql": "sum by (workload, tsdb_type, space_uid, le, pod) ("
                    "label_replace(rate("
                    'unify_query_tsdb_request_seconds_bucket[2m]), "workload", '
                    '"$1", "pod", "bk-datalink-(.*)-([0-9a-z]+)-([0-9a-z]+)"))',
                    "metric_name": "unify_query_tsdb_request_seconds_bucket_sum_2m",
                }
            ],
        },
        "from_nodes": [{"id": 1, "from_result_table_ids": ["2_bcs_custom_metric_result_table_00000"]}],
        "serving_mode": "realtime",
    }
    process_node_config = ResultTableFlow.compose_process_node(table_id, rule_obj.src_vm_table_ids)
    assert json.dumps(expected) == json.dumps(process_node_config)


@pytest.mark.django_db(databases="__all__")
def test_compose_vm_storage_node_config(create_or_delete_records, create_default_record_rule):
    """
    测试存储节点配置能否正常组装
    """
    rule_obj = RecordRule.objects.get(table_id=table_id)
    assert rule_obj.record_name == record_name
    assert rule_obj.dst_vm_table_id == "2_vm_cc_2_unify_query_tsdb_test_new_prom_node"

    expected = {
        "id": 3,
        "node_type": "vm_storage",
        "result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"],
        "name": "vm",
        "bk_biz_id": 2,
        "cluster": "vm-plat",
        "from_result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"],
        "expires": 30,
        "schemaless": True,
        "from_nodes": [{"id": 2, "from_result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"]}],
    }

    vm_storage_node_config = ResultTableFlow.compose_vm_storage(table_id, 2)
    assert json.dumps(expected) == json.dumps(vm_storage_node_config)


@pytest.mark.django_db(databases="__all__")
def test_create_flow_with_full_config(create_or_delete_records, create_default_record_rule, mocker):
    """
    测试完整预计算配置能否正常组装
    """
    mocker.patch(
        "core.drf_resource.api.bkdata.apply_data_flow",
        return_value={"node_ids": [18263, 18264, 18265, 18266, 18267], "flow_id": 3079},
    )
    mocker.patch("core.drf_resource.api.bkdata.query_auth_projects_data", return_value={})
    ResultTableFlow.create_flow(table_id)

    result_table_flow_ins = models.ResultTableFlow.objects.get(table_id=table_id)

    expected_config = {
        "project_id": 1,
        "flow_name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
        "nodes": [
            {
                "id": 1,
                "node_type": "stream_source",
                "bk_biz_name": "2",
                "bk_biz_id": 2,
                "result_table_id": "2_bcs_custom_metric_result_table_00000",
                "name": "2_bcs_custom_metric_result_table_00000",
                "from_result_table_ids": ["2_bcs_custom_metric_result_table_00000"],
                "from_nodes": [],
            },
            {
                "id": 2,
                "name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
                "node_type": "promql_v2",
                "outputs": [
                    {
                        "bk_biz_id": 2,
                        "fields": [],
                        "output_name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
                        "table_name": "vm_cc_2_unify_query_tsdb_test_new_prom_node",
                    }
                ],
                "bk_biz_id": 2,
                "from_result_table_ids": ["2_bcs_custom_metric_result_table_00000"],
                "dedicated_config": {
                    "waiting_time": 30,
                    "sql_list": [
                        {
                            "name": "unify_query_tsdb_request_seconds_bucket_sum_2m",
                            "count_freq": 60,
                            "sql": "sum by (workload, tsdb_type, space_uid, le, pod) "
                            "(label_replace(rate("
                            "unify_query_tsdb_request_seconds_bucket[2m]), "
                            '"workload", "$1", "pod", "bk-datalink-(.*)-(['
                            "0-9a-z]+)-(["
                            '0-9a-z]+)"))',
                            "metric_name": "unify_query_tsdb_request_seconds_bucket_sum_2m",
                        }
                    ],
                },
                "from_nodes": [{"id": 1, "from_result_table_ids": ["2_bcs_custom_metric_result_table_00000"]}],
                "serving_mode": "realtime",
            },
            {
                "id": 3,
                "node_type": "vm_storage",
                "result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"],
                "name": "vm",
                "bk_biz_id": 2,
                "cluster": "vm-plat",
                "from_result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"],
                "expires": 30,
                "schemaless": True,
                "from_nodes": [{"id": 2, "from_result_table_ids": ["2_vm_cc_2_unify_query_tsdb_test_new_prom_node"]}],
            },
        ],
    }

    assert result_table_flow_ins.flow_id == 3079
    assert result_table_flow_ins.config == expected_config
