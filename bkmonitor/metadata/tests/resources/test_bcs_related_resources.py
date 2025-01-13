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
from metadata.resources import GetBCSClusterRelatedDataLinkResource
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    cluster = models.BCSClusterInfo.objects.create(
        cluster_id="BCS-K8S-10001",
        bk_biz_id=1,
        bcs_api_cluster_id='test',
        project_id='1',
        domain_name='test.bcs',
        port=8080,
        server_address_path="clusters",
        K8sMetricDataID=50010,
        CustomMetricDataID=50011,
        K8sEventDataID=50012,
    )
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="BCS-K8S-10001-k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id='1001_bkmonitor_time_series_50010.__default__', bk_data_id=50010
    )

    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_base_data_id=60010,
        vm_result_table_id="1001_vm_bkmonitor_time_series_50010.__default__",
    )

    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="BCS-K8S-10001-custom_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__",
        bk_data_id=50011,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50011.__default__",
        bk_base_data_id=60011,
        vm_result_table_id="1001_vm_bkmonitor_time_series_50011.__default__",
    )

    models.DataSource.objects.create(
        bk_data_id=50012,
        data_name="BCS-K8S-10001-k8s_event",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50012.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50012.__default__",
        bk_data_id=50012,
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50012.__default__",
        bk_base_data_id=60012,
        vm_result_table_id="1001_vm_bkmonitor_time_series_50012.__default__",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    cluster.delete()
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_get_bcs_cluster_related_data_link_resource(create_or_delete_records):
    """
    测试查询BCS集群关联信息接口
    """
    actual_data = GetBCSClusterRelatedDataLinkResource().request(bcs_cluster_id='BCS-K8S-10001')
    expected_data = {
        "K8SMetric": {
            "bk_data_id": 50010,
            "data_name": "BCS-K8S-10001-k8s_metric",
            "result_table_id": "1001_bkmonitor_time_series_50010.__default__",
            "vm_result_table_id": "1001_vm_bkmonitor_time_series_50010.__default__",
        },
        "CustomMetric": {
            "bk_data_id": 50011,
            "data_name": "BCS-K8S-10001-custom_metric",
            "result_table_id": "1001_bkmonitor_time_series_50011.__default__",
            "vm_result_table_id": "1001_vm_bkmonitor_time_series_50011.__default__",
        },
        "K8SEvent": {
            "bk_data_id": 50012,
            "data_name": "BCS-K8S-10001-k8s_event",
            "result_table_id": "1001_bkmonitor_time_series_50012.__default__",
            "vm_result_table_id": "1001_vm_bkmonitor_time_series_50012.__default__",
        },
    }
    assert json.dumps(actual_data) == json.dumps(expected_data)
