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


@pytest.fixture
def create_or_delete_records():
    """
    测试用例
    联邦代理集群--BCS-K8S-10001--60001 & 60002
    联邦子集群--BCS-K8S-10002--70001 & 70002
    """
    models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id='BCS-K8S-10001',
        host_cluster_id='BCS-K8S-00000',
        sub_cluster_id='BCS-K8S-10002',
        fed_namespaces=['ns1', 'ns2', 'ns3'],
        fed_builtin_metric_table_id='1001_bkmonitor_time_series_60010.__default__',
    )
    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-10001',
        bcs_api_cluster_id='BCS-K8S-10001',
        bk_biz_id=1001,
        project_id="proxy",
        domain_name="proxy",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60001,
        K8sEventDataID=60002,
    )

    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-10001',
        bcs_api_cluster_id='BCS-K8S-10001',
        bk_biz_id=1001,
        project_id="sub",
        domain_name="sub",
        port=1001,
        server_address_path="test1",
        api_key_content="test1",
        K8sMetricDataID=70001,
        K8sEventDataID=70002,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=60001,
        table_id='1001_bkmonitor_time_series_60001.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=60002,
        table_id='1001_bkmonitor_time_series_60002.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=70001,
        table_id='1001_bkmonitor_time_series_70001.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=70002,
        table_id='1001_bkmonitor_time_series_70002.__default__',
    )
    yield
    models.BCSClusterInfo.objects.all().delete()
    models.BcsFederalClusterInfo.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_sync_federation_clusters(create_or_delete_records):
    """
    测试同步联邦拓扑信息
    TODO：暂时留空，后续需要重构联邦拓扑任务
    """
    pass
