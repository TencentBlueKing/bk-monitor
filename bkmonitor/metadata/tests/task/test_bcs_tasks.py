"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import patch

import pytest

from metadata import models
from metadata.task.bcs import discover_bcs_clusters, sync_federation_clusters
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
    # 批量创建 BCSClusterInfo 数据
    bcs_cluster_info_data = [
        models.BCSClusterInfo(
            cluster_id="BCS-K8S-10001",
            bcs_api_cluster_id="BCS-K8S-10001",
            bk_biz_id=1001,
            project_id="proxy1",
            domain_name="proxy1",
            port=1001,
            server_address_path="test",
            api_key_content="test",
            K8sMetricDataID=60010,
            CustomMetricDataID=60019,
            K8sEventDataID=80001,
        ),
        models.BCSClusterInfo(
            cluster_id="BCS-K8S-70001",
            bcs_api_cluster_id="BCS-K8S-70001",
            bk_biz_id=1001,
            project_id="proxy2",
            domain_name="proxy2",
            port=1001,
            server_address_path="test1",
            api_key_content="test1",
            K8sMetricDataID=70010,
            K8sEventDataID=80002,
        ),
        models.BCSClusterInfo(
            cluster_id="BCS-K8S-10002",
            bcs_api_cluster_id="BCS-K8S-10002",
            bk_biz_id=1001,
            project_id="sub1",
            domain_name="sub11",
            port=1001,
            server_address_path="test",
            api_key_content="test",
            K8sMetricDataID=60011,
            K8sEventDataID=80003,
        ),
        models.BCSClusterInfo(
            cluster_id="BCS-K8S-10003",
            bcs_api_cluster_id="BCS-K8S-10003",
            bk_biz_id=1001,
            project_id="sub1",
            domain_name="sub11",
            port=1001,
            server_address_path="test",
            api_key_content="test",
            K8sMetricDataID=60012,
            K8sEventDataID=80004,
        ),
    ]
    models.BCSClusterInfo.objects.bulk_create(bcs_cluster_info_data)

    # 批量创建 DataSourceResultTable 数据
    data_source_result_table_data = [
        models.DataSourceResultTable(bk_data_id=60010, table_id="1001_bkmonitor_time_series_60010.__default__"),
        models.DataSourceResultTable(bk_data_id=60011, table_id="1001_bkmonitor_time_series_60011.__default__"),
        models.DataSourceResultTable(bk_data_id=60012, table_id="1001_bkmonitor_time_series_60012.__default__"),
        models.DataSourceResultTable(bk_data_id=70010, table_id="1001_bkmonitor_time_series_70010.__default__"),
        models.DataSourceResultTable(bk_data_id=80001, table_id="1001_bkmonitor_time_series_80001.__default__"),
        models.DataSourceResultTable(bk_data_id=80002, table_id="1001_bkmonitor_time_series_80002.__default__"),
        models.DataSourceResultTable(bk_data_id=80003, table_id="1001_bkmonitor_time_series_80003.__default__"),
        models.DataSourceResultTable(bk_data_id=80004, table_id="1001_bkmonitor_time_series_80004.__default__"),
    ]
    models.DataSourceResultTable.objects.bulk_create(data_source_result_table_data)

    # 批量创建 DataSource 数据
    data_source_data = [
        models.DataSource(
            bk_data_id=60010,
            data_name="bcs_BCS-K8S-10001_k8s_metric",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=60019,
            data_name="bcs_BCS-K8S-10001_custom_metric",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=80001,
            data_name="bcs_BCS-K8S-10001_k8s_event",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=60011,
            data_name="bcs_BCS-K8S-10002_k8s_metric",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=60012,
            data_name="bcs_BCS-K8S-10003_k8s_metric",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
        models.DataSource(
            bk_data_id=70010,
            data_name="bcs_BCS-K8S-70001_k8s_metric",
            mq_cluster_id=1,
            mq_config_id=1,
            etl_config="test",
            is_custom_source=False,
        ),
    ]
    models.DataSource.objects.bulk_create(data_source_data)

    # 批量创建 ResultTable 数据
    result_table_data = [
        models.ResultTable(
            table_id="1001_bkmonitor_time_series_60010.__default__",
            table_name_zh="bcs_BCS-K8S-10001_k8s_metric",
            bk_biz_id=1001,
            is_custom_table=False,
        ),
        models.ResultTable(
            table_id="1001_bkmonitor_time_series_60019.__default__",
            table_name_zh="bcs_BCS-K8S-10001_custom_metric",
            bk_biz_id=1001,
            is_custom_table=False,
        ),
        models.ResultTable(
            table_id="1001_bkmonitor_time_series_80001.__default__",
            table_name_zh="bcs_BCS-K8S-10001_k8s_event",
            bk_biz_id=1001,
            is_custom_table=False,
        ),
    ]
    models.ResultTable.objects.bulk_create(result_table_data)

    # 批量创建 EventGroup 数据
    event_group_data = [
        models.EventGroup(bk_data_id=80001, bk_biz_id=1001),
    ]
    models.EventGroup.objects.bulk_create(event_group_data)

    # 批量创建 SpaceDataSource 数据
    space_data_source_data = [
        models.SpaceDataSource(space_type_id="bkcc", space_id=1001, bk_data_id=60010),
        models.SpaceDataSource(space_type_id="bkcc", space_id=1001, bk_data_id=60019),
        models.SpaceDataSource(space_type_id="bkcc", space_id=1001, bk_data_id=80001),
    ]
    models.SpaceDataSource.objects.bulk_create(space_data_source_data)

    # 批量创建 ClusterInfo 数据
    cluster_info_data = [
        models.ClusterInfo(
            cluster_name="vm-plat",
            cluster_type=models.ClusterInfo.TYPE_VM,
            domain_name="test.domain.vm",
            port=9090,
            description="",
            cluster_id=100111,
            is_default_cluster=True,
            version="5.x",
        ),
    ]
    models.ClusterInfo.objects.bulk_create(cluster_info_data)

    # 清理操作
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.BCSClusterInfo.objects.all().delete()
    models.BcsFederalClusterInfo.objects.all().delete()
    models.DataSourceResultTable.objects.all().delete()
    models.DataSource.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.EventGroup.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_discover_bcs_clusters_and_change_bk_biz_id(create_or_delete_records, mocker):
    """
    测试集群发现周期任务以及当集群业务发生迁移时，对应元数据是否能够被正常处理
    """
    api_resp = [
        {
            "bk_biz_id": "1002",
            "cluster_id": "BCS-K8S-10001",
            "bcs_cluster_id": "BCS-K8S-10001",
            "status": "RUNNING",
            "project_id": "testprojectid123",
        },
    ]
    mocker.patch("core.drf_resource.api.kubernetes.fetch_k8s_cluster_list", return_value=api_resp)
    mocker.patch("django.conf.settings.BCS_API_GATEWAY_TOKEN", "test")

    # 模拟执行集群发现周期任务
    discover_bcs_clusters()

    # 结果表
    assert models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60010.__default__").bk_biz_id == 1002
    assert models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60019.__default__").bk_biz_id == 1002
    assert models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_80001.__default__").bk_biz_id == 1002

    # 数据源
    assert models.DataSource.objects.get(bk_data_id=60010).space_uid == "bkcc__1002"
    assert models.DataSource.objects.get(bk_data_id=60019).space_uid == "bkcc__1002"
    assert models.DataSource.objects.get(bk_data_id=80001).space_uid == "bkcc__1002"

    # 空间-数据源授权关系
    assert (
        models.SpaceDataSource.objects.filter(
            bk_data_id__in=[60010, 60019, 80001], space_type_id="bkcc", space_id=1001
        ).count()
        == 0
    )
    assert (
        models.SpaceDataSource.objects.filter(
            bk_data_id__in=[60010, 60019, 80001], space_type_id="bkcc", space_id=1002
        ).count()
        == 3
    )

    # 容器事件
    assert models.EventGroup.objects.get(bk_data_id=80001).bk_biz_id == 1002


@pytest.mark.django_db(databases="__all__")
def test_sync_federation_clusters(create_or_delete_records):
    """
    测试同步联邦拓扑信息
    """
    bkbase_data_name_10002_fed = "fed_bkm_bcs_BCS-K8S-10002_k8s_metric"
    bkbase_vmrt_name_10002_fed = "bkm_1001_bkmonitor_time_series_60011_fed"
    bkbase_data_name_10003_fed = "fed_bkm_bcs_BCS-K8S-10003_k8s_metric"
    bkbase_vmrt_name_10003_fed = "bkm_1001_bkmonitor_time_series_60012_fed"
    with patch.object(
        models.DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
    ) as mock_apply_with_retry:  # noqa
        bcs_api_fed_returns = {
            "BCS-K8S-10001": {
                "host_cluster_id": "BCS-K8S-11111",  # host_cluster无需关注
                "sub_clusters": {
                    "BCS-K8S-10002": ["ns1", "ns2", "ns3"],
                },
            },
            "BCS-K8S-70001": {
                "host_cluster_id": "BCS-K8S-11111",  # host_cluster无需关注
                "sub_clusters": {
                    "BCS-K8S-10002": ["ns4", "ns5", "ns6"],
                    "BCS-K8S-10003": ["nss1", "nss2"],
                },
            },
        }
        sync_federation_clusters(fed_clusters=bcs_api_fed_returns)

        fed_record_10002_part1 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id="BCS-K8S-10002", fed_cluster_id="BCS-K8S-10001", is_deleted=False
        )
        assert fed_record_10002_part1.fed_cluster_id == "BCS-K8S-10001"
        assert fed_record_10002_part1.host_cluster_id == "BCS-K8S-11111"
        assert set(fed_record_10002_part1.fed_namespaces) == {"ns1", "ns2", "ns3"}
        assert fed_record_10002_part1.fed_builtin_metric_table_id == "1001_bkmonitor_time_series_60010.__default__"

        fed_record_10002_part2 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id="BCS-K8S-10002", fed_cluster_id="BCS-K8S-70001", is_deleted=False
        )
        assert fed_record_10002_part2.fed_cluster_id == "BCS-K8S-70001"
        assert fed_record_10002_part2.host_cluster_id == "BCS-K8S-11111"
        assert set(fed_record_10002_part2.fed_namespaces) == {"ns4", "ns5", "ns6"}
        assert fed_record_10002_part2.fed_builtin_metric_table_id == "1001_bkmonitor_time_series_70010.__default__"

        fed_record_10003 = models.BcsFederalClusterInfo.objects.get(sub_cluster_id="BCS-K8S-10003", is_deleted=False)
        assert fed_record_10003.fed_cluster_id == "BCS-K8S-70001"
        assert fed_record_10003.host_cluster_id == "BCS-K8S-11111"
        assert set(fed_record_10003.fed_namespaces) == {"nss1", "nss2"}
        assert fed_record_10003.fed_builtin_metric_table_id == "1001_bkmonitor_time_series_70010.__default__"

        # 这里由于是异步触发，所以测试时需要去到sync_federation_clusters中将bulk_create_fed_data_link改为同步执行以便测试
        bkbase_rt_10002_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert bkbase_rt_10002_fed.monitor_table_id == "1001_bkmonitor_time_series_60011.__default__"
        assert bkbase_rt_10002_fed.bkbase_rt_name == bkbase_vmrt_name_10002_fed

        conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert conditional_sink_ins.namespace == "bkmonitor"
        assert conditional_sink_ins.name == bkbase_vmrt_name_10002_fed

        databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert databus_ins.namespace == "bkmonitor"
        assert databus_ins.name == bkbase_vmrt_name_10002_fed

        # 10003 子集群对应的链路

        bkbase_rt_10003_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert bkbase_rt_10003_fed.monitor_table_id == "1001_bkmonitor_time_series_60012.__default__"
        assert bkbase_rt_10003_fed.bkbase_rt_name == bkbase_vmrt_name_10003_fed

        conditional_sink_ins_10003 = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert conditional_sink_ins_10003.namespace == "bkmonitor"
        assert conditional_sink_ins_10003.name == bkbase_vmrt_name_10003_fed

        databus_ins_10003 = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10003_fed)
        assert databus_ins_10003.namespace == "bkmonitor"
        assert databus_ins_10003.name == bkbase_vmrt_name_10003_fed

        # 发生变更操作
        # BCS-K8S-10002不再属于BCS-K8S-70001，所有namespace都被BCS-K8S-10001管理
        bcs_api_fed_returns_2 = {
            "BCS-K8S-10001": {
                "host_cluster_id": "BCS-K8S-11111",  # host_cluster无需关注
                "sub_clusters": {
                    "BCS-K8S-10002": ["ns1", "ns2", "ns3", "ns4", "ns5", "ns6"],
                },
            },
            "BCS-K8S-70001": {
                "host_cluster_id": "BCS-K8S-11111",  # host_cluster无需关注
                "sub_clusters": {
                    "BCS-K8S-10003": ["nss1", "nss2"],
                },
            },
        }

        sync_federation_clusters(fed_clusters=bcs_api_fed_returns_2)

        fed_record_10002_after_part1 = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id="BCS-K8S-10002", fed_cluster_id="BCS-K8S-10001", is_deleted=False
        )
        assert fed_record_10002_after_part1.fed_cluster_id == "BCS-K8S-10001"
        assert fed_record_10002_after_part1.host_cluster_id == "BCS-K8S-11111"
        assert set(fed_record_10002_after_part1.fed_namespaces) == {"ns1", "ns2", "ns3", "ns4", "ns5", "ns6"}
        assert (
            fed_record_10002_after_part1.fed_builtin_metric_table_id == "1001_bkmonitor_time_series_60010.__default__"
        )

        fed_record_10002_after_part2 = models.BcsFederalClusterInfo.objects.filter(
            sub_cluster_id="BCS-K8S-10002", fed_cluster_id="BCS-K8S-70001"
        )
        assert fed_record_10002_after_part2.first().is_deleted

        fed_record_10003_after = models.BcsFederalClusterInfo.objects.get(
            sub_cluster_id="BCS-K8S-10003", is_deleted=False
        )
        assert fed_record_10003_after.fed_cluster_id == "BCS-K8S-70001"
        assert fed_record_10003_after.host_cluster_id == "BCS-K8S-11111"
        assert set(fed_record_10003_after.fed_namespaces) == {"nss1", "nss2"}
        assert fed_record_10003_after.fed_builtin_metric_table_id == "1001_bkmonitor_time_series_70010.__default__"

        bkbase_rt_10002_fed = models.BkBaseResultTable.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert bkbase_rt_10002_fed.monitor_table_id == "1001_bkmonitor_time_series_60011.__default__"
        assert bkbase_rt_10002_fed.bkbase_rt_name == bkbase_vmrt_name_10002_fed

        conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert conditional_sink_ins.namespace == "bkmonitor"
        assert conditional_sink_ins.name == bkbase_vmrt_name_10002_fed

        databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name_10002_fed)
        assert databus_ins.namespace == "bkmonitor"
        assert databus_ins.name == bkbase_vmrt_name_10002_fed
