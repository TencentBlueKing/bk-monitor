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

from metadata.models.record_rule import RecordRule

from .conftest import SPACE_ID, SPACE_TYPE, TABLE_FIELD_NAME, TABLE_ID

pytestmark = pytest.mark.django_db


def test_transform_bk_sql_and_metrics(mocker):
    rule_config = """
---
interval: 3m
name: happy-record/k8s.rules
rules:
- expr: |
    sum(rate(container_cpu_usage_seconds_total{job=~"kubelet|cadvisor", container!="POD", container!=""}[5m])) by (cluster, namespace)
  record: namespace:container_cpu_usage_seconds_total:sum_rate
    """  # noqa
    mocker_data = {
        "promql": """sum(rate(container_cpu_usage_seconds_total{job=~"kubelet|cadvisor", container!="POD", container!=""}[5m])) by (cluster, namespace)""",  # noqa
        "metrics": {"container_cpu_usage_seconds_total"},
    }
    mocker.patch("metadata.models.record_rule.rules.utils.refine_bk_sql_and_metrics", return_value=mocker_data)
    mocker.patch(
        "metadata.models.record_rule.rules.utils.transform_record_to_metric_name",
        return_value="namespace_container_cpu_usage_seconds_total_sum_rate",
    )

    data = RecordRule.transform_bk_sql_and_metrics(rule_config)
    assert {"bksql", "metrics", "rule_metrics"} == set(data.keys())
    assert mocker_data["promql"] == data["bksql"][0]["sql"]


def test_get_src_table_ids(create_and_delete_record, mocker):
    mocker.patch("metadata.models.record_rule.rules.get_space_table_id_data_id", return_value={TABLE_ID: 1})
    vm_rts = RecordRule.get_src_table_ids(space_type=SPACE_TYPE, space_id=SPACE_ID, metrics=[TABLE_FIELD_NAME])
    assert {TABLE_ID} == set(vm_rts)


@pytest.mark.parametrize(
    "table_id, dst_table_id",
    [
        ("test", "0_test"),
        ("test.demo", "0_test_demo"),
        (
            "test111111111111111111111111111111111111111111111111111111111111.demo",
            "0_11111111111111111111111111111111111_demo",
        ),
    ],
)
def test_get_dst_table_id(table_id, dst_table_id):
    assert RecordRule.get_dst_table_id(table_id) == dst_table_id
