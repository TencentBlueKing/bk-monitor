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
from metadata.models.record_rule.service import RecordRuleService

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


rule_config = """
---
name: record/unify_query_tsdb_test_new_prom_node
rules:
- expr: |
    sum(label_replace(rate(bkmonitor:unify_query_tsdb_request_seconds_bucket{}[2m]), "workload", "$1", "pod", "bk-datalink-(.*)-([0-9a-z]+)-([0-9a-z]+)")) by (workload, tsdb_type, space_uid, le, pod)
  record: unify_query_tsdb_request_seconds_bucket_sum_2m
"""

space_type = 'bkcc'
space_id = '2'
record_name = 'unify_query_tsdb_test_new_prom_node'
table_id = 'bkprecal_bkcc_2_unify_query_tsdb_test_new_prom_node.__default__'


@pytest.fixture
def create_or_delete_records(mocker):
    models.ClusterInfo.objects.create(
        cluster_name="vm-plat",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.vm",
        port=9090,
        description="",
        cluster_id=100111,
        is_default_cluster=True,
        version="5.x",
    )
    space = models.Space.objects.create(space_type_id=space_type, space_id=space_id, space_name="test_biz")
    yield
    models.ClusterInfo.objects.all().delete()
    space.delete()


@pytest.fixture
def create_default_record_rule(create_or_delete_records, mocker):
    mocker.patch(
        'metadata.models.RecordRule.get_src_table_ids', return_value=['2_bcs_custom_metric_result_table_00000']
    )
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
    mocker.patch('django.conf.settings.BK_DATA_BK_BIZ_ID', 2)
    service = RecordRuleService(
        space_type=space_type, space_id=space_id, record_name=record_name, rule_config=rule_config
    )
    service.create_record_rule()
    yield
    models.RecordRule.objects.all().delete()
    models.ResultTableField.objects.filter(table_id=table_id).delete()
