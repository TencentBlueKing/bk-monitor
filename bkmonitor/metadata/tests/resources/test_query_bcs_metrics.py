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
from metadata.resources import QueryBCSMetricsResource

pytestmark = pytest.mark.django_db

DEFAULT_ID = 1000
DEFAULT_BCS_CLUSTER_ID = "BCS-K8S-00000"
BUILD_IN_DATA_ID = 1000
CUSTOM_DATA_ID = 1001


@pytest.fixture
def create_and_delete_records():
    models.TimeSeriesGroup.objects.create(
        bk_data_id=DEFAULT_ID,
        bk_biz_id=DEFAULT_ID,
        table_id="test.demo",
        time_series_group_id=DEFAULT_ID,
        time_series_group_name="test",
    )
    yield
    models.TimeSeriesGroup.objects.filter(bk_data_id=DEFAULT_ID, table_id="test.demo").delete()


def test_query_bcs_metric_without_dimensions(mocker, create_and_delete_records):
    """测试不带有维度的场景"""

    mocker.patch(
        "metadata.resources.resources.get_built_in_k8s_metrics",
        return_value=[
            {
                'description': '',
                'field_name': 'go_threads',
                'tag_list': [
                    {'description': '', 'field_name': 'monitor_type'},
                    {'description': '', 'field_name': 'instance'},
                    {'description': '', 'field_name': 'service'},
                ],
            }
        ],
    )
    mocker.patch(
        "metadata.resources.resources.get_bcs_dataids",
        return_value=(
            [DEFAULT_ID],
            {
                "built_in_metric_data_id_list": [],
                BUILD_IN_DATA_ID: DEFAULT_BCS_CLUSTER_ID,
                CUSTOM_DATA_ID: DEFAULT_BCS_CLUSTER_ID,
            },
        ),
    )
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metric_info_list_with_label",
        return_value=[
            {
                'field_name': 'promhttp_metric_handler_requests_total',
                'metric_display_name': '',
                'unit': '',
                'type': 'float',
                'label': 'kubernetes',
                'tag_list': [{'field_name': 'target', 'description': '', 'unit': '', 'type': 'string'}],
                'tag_value_list': [],
                'table_id': 'test.demo',
                'description': '',
            }
        ],
    )

    # 无 0 业务
    params = {"bk_biz_ids": [DEFAULT_ID], "cluster_ids": [DEFAULT_BCS_CLUSTER_ID]}

    metrics = QueryBCSMetricsResource().request(params)
    assert len(metrics) == 1

    # 包含 0 业务
    params = {"bk_biz_ids": [DEFAULT_ID, 0], "cluster_ids": [DEFAULT_BCS_CLUSTER_ID]}

    metrics = QueryBCSMetricsResource().request(params)
    assert len(metrics) == 2


def test_query_bcs_metric_with_dimensions(mocker, create_and_delete_records):
    """测试带有维度的场景"""
    mocker.patch(
        "metadata.resources.resources.get_built_in_k8s_metrics",
        return_value=[
            {
                'description': '',
                'field_name': 'go_threads',
                'tag_list': [
                    {'description': '', 'field_name': 'monitor_type'},
                    {'description': '', 'field_name': 'instance'},
                    {'description': '', 'field_name': 'service'},
                ],
            }
        ],
    )
    mocker.patch(
        "metadata.resources.resources.get_bcs_dataids",
        return_value=(
            [DEFAULT_ID],
            {
                "built_in_metric_data_id_list": [],
                BUILD_IN_DATA_ID: DEFAULT_BCS_CLUSTER_ID,
                CUSTOM_DATA_ID: DEFAULT_BCS_CLUSTER_ID,
            },
        ),
    )
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metric_info_list_with_label",
        return_value=[
            {
                'field_name': 'go_threads',
                'metric_display_name': '',
                'unit': '',
                'type': 'float',
                'label': 'kubernetes',
                'tag_list': [{'field_name': 'target', 'description': '', 'unit': '', 'type': 'string'}],
                'tag_value_list': [],
                'table_id': 'test.demo',
                'description': '',
            },
            {
                'field_name': 'promhttp_metric_handler_requests_total',
                'metric_display_name': '',
                'unit': '',
                'type': 'float',
                'label': 'kubernetes',
                'tag_list': [{'field_name': 'target', 'description': '', 'unit': '', 'type': 'string'}],
                'tag_value_list': [],
                'table_id': 'test.demo',
                'description': '',
            },
        ],
    )

    params = {
        "bk_biz_ids": [DEFAULT_ID],
        "cluster_ids": [DEFAULT_BCS_CLUSTER_ID],
        "dimension_name": "target",
        "dimension_value": "val",
    }

    metrics = QueryBCSMetricsResource().request(params)
    assert len(metrics) == 2

    # 内置的不存在
    mocker.patch(
        "metadata.models.custom_report.time_series.TimeSeriesGroup.get_metric_info_list_with_label",
        return_value=[
            {
                'field_name': 'go_threads_not_match',
                'metric_display_name': '',
                'unit': '',
                'type': 'float',
                'label': 'kubernetes',
                'tag_list': [{'field_name': 'target', 'description': '', 'unit': '', 'type': 'string'}],
                'tag_value_list': [],
                'table_id': 'test.demo',
                'description': '',
            }
        ],
    )
    params = {
        "bk_biz_ids": [DEFAULT_ID],
        "cluster_ids": [DEFAULT_BCS_CLUSTER_ID],
        "dimension_name": "target",
        "dimension_value": "val",
    }

    metrics = QueryBCSMetricsResource().request(params)
    assert len(metrics) == 1
