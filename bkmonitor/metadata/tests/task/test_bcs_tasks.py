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

from unittest.mock import patch

import pytest

from metadata import models
from metadata.task.bcs import sync_federation_clusters
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    """
    测试用例
    联邦代理集群--BCS-K8S-10001--60010
    联邦代理集群--BCS-K8S-70001 -- 70010
    联邦子集群--BCS-K8S-10002--60011
    联邦子集群--BCS-K8S-10003--60012
    """
    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-10001',
        bcs_api_cluster_id='BCS-K8S-10001',
        bk_biz_id=1001,
        project_id="proxy1",
        domain_name="proxy1",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60010,
        K8sEventDataID=80001,
    )

    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-70001',
        bcs_api_cluster_id='BCS-K8S-70001',
        bk_biz_id=1001,
        project_id="proxy2",
        domain_name="proxy2",
        port=1001,
        server_address_path="test1",
        api_key_content="test1",
        K8sMetricDataID=70010,
        K8sEventDataID=80002,
    )

    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-10002',
        bcs_api_cluster_id='BCS-K8S-10002',
        bk_biz_id=1001,
        project_id="sub1",
        domain_name="sub11",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60011,
        K8sEventDataID=80003,
    )
    models.BCSClusterInfo.objects.create(
        cluster_id='BCS-K8S-10003',
        bcs_api_cluster_id='BCS-K8S-10003',
        bk_biz_id=1001,
        project_id="sub1",
        domain_name="sub11",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60012,
        K8sEventDataID=80004,
    )

    models.DataSourceResultTable.objects.create(
        bk_data_id=60010,
        table_id='1001_bkmonitor_time_series_60010.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=60011,
        table_id='1001_bkmonitor_time_series_60011.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=60012,
        table_id='1001_bkmonitor_time_series_60012.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=70010,
        table_id='1001_bkmonitor_time_series_70010.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=80001,
        table_id='1001_bkmonitor_time_series_80001.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=80002,
        table_id='1001_bkmonitor_time_series_80002.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=80003,
        table_id='1001_bkmonitor_time_series_80003.__default__',
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=80004,
        table_id='1001_bkmonitor_time_series_80004.__default__',
    )
    models.DataSource.objects.create(
        bk_data_id=60010,
        data_name="bcs_BCS-K8S-10001_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSource.objects.create(
        bk_data_id=60011,
        data_name="bcs_BCS-K8S-10002_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSource.objects.create(
        bk_data_id=60012,
        data_name="bcs_BCS-K8S-10003_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.DataSource.objects.create(
        bk_data_id=70010,
        data_name="bcs_BCS-K8S-70001_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
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
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.BCSClusterInfo.objects.all().delete()
    models.BcsFederalClusterInfo.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()
    models.DataSource.objects.all().delete()
    models.ClusterInfo.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_sync_federation_clusters(create_or_delete_records):
    """
    测试同步联邦拓扑信息
    """
    bkbase_data_name_10002_fed = 'fed_bkm_bcs_BCS-K8S-10002_k8s_metric'
    bkbase_vmrt_name_10002_fed = 'bkm_1001_bkmonitor_time_series_60011_fed'
    bkbase_data_name_10003_fed = 'fed_bkm_bcs_BCS-K8S-10003_k8s_metric'
    bkbase_vmrt_name_10003_fed = 'bkm_1001_bkmonitor_time_series_60012_fed'
    with patch.object(
        models.DataLink, 'apply_data_link_with_retry', return_value={'status': 'success'}
    ) as mock_apply_with_retry:  # noqa
        bcs_api_fed_returns = {
            'BCS-K8S-10001': {
                'host_cluster_id': 'BCS-K8S-11111',  # host_cluster无需关注
                'sub_clusters': {
                    'BCS-K8S-10002': ['ns1', 'ns2', 'ns3'],
                },
            },
            'BCS-K8S-70001': {
                'host_cluster_id': 'BCS-K8S-11111',  # host_cluster无需关注
                'sub_clusters': {
                    'BCS-K8S-10002': ['ns4', 'ns5', 'ns6'],
                    'BCS-K8S-10003': ['nss1', 'nss2'],
                },
            },
        }
        sync_federation_clusters(fed_clusters=bcs_api_fed_returns)

        fed_record_10002_part1 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id='BCS-K8S-10002', fed_cluster_id='BCS-K8S-10001', is_deleted=False
        )
        assert fed_record_10002_part1.fed_cluster_id == 'BCS-K8S-10001'
        assert fed_record_10002_part1.host_cluster_id == 'BCS-K8S-11111'
        assert set(fed_record_10002_part1.fed_namespaces) == {'ns1', 'ns2', 'ns3'}
        assert fed_record_10002_part1.fed_builtin_metric_table_id == '1001_bkmonitor_time_series_60010.__default__'

        fed_record_10002_part2 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id='BCS-K8S-10002', fed_cluster_id='BCS-K8S-70001', is_deleted=False
        )
        assert fed_record_10002_part2.fed_cluster_id == 'BCS-K8S-70001'
        assert fed_record_10002_part2.host_cluster_id == 'BCS-K8S-11111'
        assert set(fed_record_10002_part2.fed_namespaces) == {'ns4', 'ns5', 'ns6'}
        assert fed_record_10002_part2.fed_builtin_metric_table_id == '1001_bkmonitor_time_series_70010.__default__'

        fed_record_10003 = models.BcsFederalClusterInfo.objects.get(sub_cluster_id='BCS-K8S-10003', is_deleted=False)
        assert fed_record_10003.fed_cluster_id == 'BCS-K8S-70001'
        assert fed_record_10003.host_cluster_id == 'BCS-K8S-11111'
        assert set(fed_record_10003.fed_namespaces) == {'nss1', 'nss2'}
        assert fed_record_10003.fed_builtin_metric_table_id == '1001_bkmonitor_time_series_70010.__default__'

        bkbase_rt_10002_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert bkbase_rt_10002_fed.monitor_table_id == '1001_bkmonitor_time_series_60011.__default__'
        assert bkbase_rt_10002_fed.bkbase_rt_name == bkbase_vmrt_name_10002_fed

        conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert conditional_sink_ins.namespace == 'bkmonitor'
        assert conditional_sink_ins.name == bkbase_vmrt_name_10002_fed

        databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert databus_ins.namespace == 'bkmonitor'
        assert databus_ins.name == bkbase_vmrt_name_10002_fed

        # 10003 子集群对应的链路

        bkbase_rt_10003_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert bkbase_rt_10003_fed.monitor_table_id == '1001_bkmonitor_time_series_60012.__default__'
        assert bkbase_rt_10003_fed.bkbase_rt_name == bkbase_vmrt_name_10003_fed

        conditional_sink_ins_10003 = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert conditional_sink_ins_10003.namespace == 'bkmonitor'
        assert conditional_sink_ins_10003.name == bkbase_vmrt_name_10003_fed

        databus_ins_10003 = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert databus_ins_10003.namespace == 'bkmonitor'
        assert databus_ins_10003.name == bkbase_vmrt_name_10003_fed

        # 发生变更操作
        # BCS-K8S-10002不再属于BCS-K8S-70001，所有namespace都被BCS-K8S-10001管理
        bcs_api_fed_returns_2 = {
            'BCS-K8S-10001': {
                'host_cluster_id': 'BCS-K8S-11111',  # host_cluster无需关注
                'sub_clusters': {
                    'BCS-K8S-10002': ['ns1', 'ns2', 'ns3', 'ns4', 'ns5', 'ns6'],
                },
            },
            'BCS-K8S-70001': {
                'host_cluster_id': 'BCS-K8S-11111',  # host_cluster无需关注
                'sub_clusters': {
                    'BCS-K8S-10003': ['nss1', 'nss2'],
                },
            },
        }

        sync_federation_clusters(fed_clusters=bcs_api_fed_returns_2)

        fed_record_10002_after_part1 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id='BCS-K8S-10002', fed_cluster_id='BCS-K8S-10001', is_deleted=False
        )
        assert fed_record_10002_after_part1.fed_cluster_id == 'BCS-K8S-10001'
        assert fed_record_10002_after_part1.host_cluster_id == 'BCS-K8S-11111'
        assert set(fed_record_10002_after_part1.fed_namespaces) == {'ns1', 'ns2', 'ns3', 'ns4', 'ns5', 'ns6'}
        assert (
            fed_record_10002_after_part1.fed_builtin_metric_table_id == '1001_bkmonitor_time_series_60010'
            '.__default__'
        )

        fed_record_10002_after_part2 = models.BcsFederalClusterInfo.objects.filter(
            sub_cluster_id='BCS-K8S-10002', fed_cluster_id='BCS-K8S-70001'
        )
        assert fed_record_10002_after_part2.first().is_deleted

        fed_record_10003_after = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id='BCS-K8S-10003', is_deleted=False
        )
        assert fed_record_10003_after.fed_cluster_id == 'BCS-K8S-70001'
        assert fed_record_10003_after.host_cluster_id == 'BCS-K8S-11111'
        assert set(fed_record_10003_after.fed_namespaces) == {'nss1', 'nss2'}
        assert fed_record_10003_after.fed_builtin_metric_table_id == '1001_bkmonitor_time_series_70010.__default__'

        bkbase_rt_10002_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert bkbase_rt_10002_fed.monitor_table_id == '1001_bkmonitor_time_series_60011.__default__'
        assert bkbase_rt_10002_fed.bkbase_rt_name == bkbase_vmrt_name_10002_fed

        conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert conditional_sink_ins.namespace == 'bkmonitor'
        assert conditional_sink_ins.name == bkbase_vmrt_name_10002_fed

        databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert databus_ins.namespace == 'bkmonitor'
        assert databus_ins.name == bkbase_vmrt_name_10002_fed
