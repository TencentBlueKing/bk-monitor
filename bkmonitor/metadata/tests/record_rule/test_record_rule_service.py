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

from metadata import models
from metadata.models.record_rule.rules import RecordRule
from metadata.models.record_rule.service import RecordRuleService
from metadata.tests.record_rule.conftest import (
    record_name,
    rule_config,
    space_id,
    space_type,
    table_id,
)
from metadata.utils.data_link import get_record_rule_metrics_by_biz_id


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_create_record_rule(create_or_delete_records, mocker):
    """
    测试预计算流程能否正常工作，组装配置+申请+创建对应Flow记录
    """
    mocker.patch(
        'metadata.models.RecordRule.get_src_table_ids', return_value=['2_bcs_custom_metric_result_table_00000']
    )
    mocker.patch('django.conf.settings.DEFAULT_BKDATA_BIZ_ID', 2)
    mocker.patch(
        'metadata.models.record_rule.utils.refine_bk_sql_and_metrics',
        return_value={
            'promql': 'sum by (workload, tsdb_type, space_uid, le, pod) (label_replace(rate('
            'unify_query_tsdb_request_seconds_bucket[2m]), "workload", "$1", "pod", "bk-datalink-(.*)-(['
            '0-9a-z]+)-([0-9a-z]+)"))',
            'metrics': {'unify_query_tsdb_request_seconds_bucket'},
        },
    )
    mocker.patch('django.conf.settings.DEFAULT_BKDATA_BIZ_ID', 2)
    service = RecordRuleService(
        space_type=space_type, space_id=space_id, record_name=record_name, rule_config=rule_config, count_freq=30
    )
    service.create_record_rule()

    rule_ins = RecordRule.objects.get(table_id=table_id)
    assert rule_ins.count_freq == 30
    assert rule_ins.dst_vm_table_id == '2_vm_cc_2_unify_query_tsdb_test_new_prom_node'
    rt = models.ResultTable.objects.get(table_id=table_id)
    assert rt.bk_biz_id == 2

    metrics_cache_data = get_record_rule_metrics_by_biz_id(bk_biz_id=2)[0]['field_list']
    expected_cache_data = [
        {
            'field_name': 'unify_query_tsdb_request_seconds_bucket_sum_2m',
            'type': 'string',
            'tag': 'metric',
            'default_value': None,
            'is_config_by_user': True,
            'description': 'unify_query_tsdb_request_seconds_bucket_sum_2m',
            'unit': '',
            'alias_name': '',
            'is_disabled': False,
            'option': {},
        }
    ]
    assert json.dumps(metrics_cache_data) == json.dumps(expected_cache_data)

    expected_bksql_config = [
        {
            'name': 'unify_query_tsdb_request_seconds_bucket_sum_2m',
            'count_freq': 60,
            'sql': 'sum by (workload, tsdb_type, space_uid, le, pod) (label_replace(rate('
            'unify_query_tsdb_request_seconds_bucket[2m]), "workload", "$1", "pod", "bk-datalink-(.*)-(['
            '0-9a-z]+)-(['
            '0-9a-z]+)"))',
            'metric_name': 'unify_query_tsdb_request_seconds_bucket_sum_2m',
        }
    ]
    assert rule_ins.space_type == 'bkcc'
    assert rule_ins.record_name == 'unify_query_tsdb_test_new_prom_node'
    assert rule_ins.rule_type == 'prometheus'
    assert rule_ins.bk_sql_config == expected_bksql_config
    assert rule_ins.rule_metrics == {
        'unify_query_tsdb_request_seconds_bucket_sum_2m': 'unify_query_tsdb_request_seconds_bucket_sum_2m'
    }

    field_ins = models.ResultTableField.objects.get(table_id=table_id)
    assert field_ins.field_name == 'unify_query_tsdb_request_seconds_bucket_sum_2m'
    assert field_ins.tag == 'metric'

    vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
    assert vm_record.vm_result_table_id == '2_vm_cc_2_unify_query_tsdb_test_new_prom_node'
