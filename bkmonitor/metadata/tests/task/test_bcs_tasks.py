"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import nullcontext
from unittest.mock import patch

import pytest
from django.core.management import call_command

from metadata import models
from metadata.models.data_link.utils import compose_bkdata_data_id_name
from metadata.service.federation_data_link import (
    FederationNamespaceConflictError,
    FederationReconcileError,
    FederationReconcilePlan,
    FederationTopologyEmptySnapshotError,
    reconcile_federation_data_links,
)
from metadata.task.bcs import (
    discover_bcs_clusters,
    sync_and_schedule_federation_clusters,
    sync_federation_clusters,
)
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker, settings):
    """
    测试用例
    联邦代理集群--BCS-K8S-10001--60010
    联邦代理集群--BCS-K8S-70001 -- 70010
    联邦子集群--BCS-K8S-10002--60011
    联邦子集群--BCS-K8S-10003--60012
    """
    settings.ENABLE_MULTI_TENANT_MODE = False
    mocker.patch("metadata.task.bcs.service_lock", side_effect=lambda *args, **kwargs: nullcontext())
    mocker.patch(
        "metadata.service.federation_data_link.service_lock", side_effect=lambda *args, **kwargs: nullcontext()
    )
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
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
    for registered_data_source in models.DataSource.objects.filter(bk_data_id__in=[60010, 60011, 60012, 70010]):
        models.DataIdConfig.objects.create(
            name=compose_bkdata_data_id_name(registered_data_source.data_name),
            namespace="bkmonitor",
            bk_tenant_id=registered_data_source.bk_tenant_id,
            bk_biz_id=1001,
            bk_data_id=registered_data_source.bk_data_id,
        )

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
    models.ResultTable.objects.bulk_create(
        [
            models.ResultTable(
                table_id=f"1001_bkmonitor_time_series_{data_id}.__default__",
                table_name_zh="federation metric",
                bk_biz_id=1001,
                is_custom_table=False,
            )
            for data_id in (60011, 60012, 70010)
        ]
    )

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
    with (
        patch.object(models.DataLink, "get_existing_component_config", return_value=None),
        patch.object(models.DataLink, "apply_data_link_with_retry", return_value={"status": "success"}),
    ):
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
        plan = sync_federation_clusters(fed_clusters=bcs_api_fed_returns)
        reconcile_federation_data_links(bk_tenant_id="system", plan=plan)
        bkbase_data_name_10002_fed = models.DataLink.objects.get(
            bk_data_id=60011, data_link_strategy=models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES
        ).pk
        bkbase_vmrt_name_10002_fed = models.ConditionalSinkConfig.objects.get(
            data_link_name=bkbase_data_name_10002_fed
        ).name
        bkbase_data_name_10003_fed = models.DataLink.objects.get(
            bk_data_id=60012, data_link_strategy=models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES
        ).pk
        bkbase_vmrt_name_10003_fed = models.ConditionalSinkConfig.objects.get(
            data_link_name=bkbase_data_name_10003_fed
        ).name

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

        plan = sync_federation_clusters(fed_clusters=bcs_api_fed_returns_2)
        reconcile_federation_data_links(bk_tenant_id="system", plan=plan)

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


@pytest.mark.django_db(databases="__all__")
def test_sync_federation_clusters_rejects_suspicious_empty_snapshot(create_or_delete_records):
    pair = {
        "fed_cluster_id": "BCS-K8S-10001",
        "host_cluster_id": "BCS-K8S-11111",
        "sub_cluster_id": "BCS-K8S-10002",
        "fed_namespaces": ["default"],
    }
    models.BcsFederalClusterInfo.objects.create(bk_tenant_id="system", **pair)
    models.BcsFederalClusterInfo.objects.create(bk_tenant_id="tenant-b", **pair)

    with pytest.raises(FederationTopologyEmptySnapshotError, match="empty snapshot"):
        sync_federation_clusters(fed_clusters={}, bk_tenant_id="system")

    assert not models.BcsFederalClusterInfo.objects.get(
        bk_tenant_id="system",
        fed_cluster_id=pair["fed_cluster_id"],
        sub_cluster_id=pair["sub_cluster_id"],
    ).is_deleted
    assert not models.BcsFederalClusterInfo.objects.get(
        bk_tenant_id="tenant-b",
        fed_cluster_id=pair["fed_cluster_id"],
        sub_cluster_id=pair["sub_cluster_id"],
    ).is_deleted


@pytest.mark.django_db(databases="__all__")
def test_sync_and_schedule_federation_clusters_skips_suspicious_empty_snapshot(
    create_or_delete_records,
    mocker,
    caplog,
):
    record = models.BcsFederalClusterInfo.objects.create(
        bk_tenant_id="system",
        fed_cluster_id="BCS-K8S-10001",
        host_cluster_id="BCS-K8S-11111",
        sub_cluster_id="BCS-K8S-10002",
        fed_namespaces=["default"],
    )
    schedule = mocker.patch("metadata.task.bcs.schedule_federation_reconcile")

    synced = sync_and_schedule_federation_clusters(
        fed_clusters={},
        bk_tenant_id="system",
        source="test_periodic_task",
    )

    record.refresh_from_db()
    assert synced is False
    assert not record.is_deleted
    schedule.assert_not_called()
    assert "skip suspicious empty federation topology" in caplog.text


@pytest.mark.django_db(databases="__all__")
def test_sync_federation_clusters_allows_explicitly_confirmed_empty_topology(create_or_delete_records):
    pair = {
        "fed_cluster_id": "BCS-K8S-10001",
        "host_cluster_id": "BCS-K8S-11111",
        "sub_cluster_id": "BCS-K8S-10002",
        "fed_namespaces": ["default"],
    }
    models.BcsFederalClusterInfo.objects.create(bk_tenant_id="system", **pair)
    models.BcsFederalClusterInfo.objects.create(bk_tenant_id="tenant-b", **pair)

    plan = sync_federation_clusters(
        fed_clusters={},
        bk_tenant_id="system",
        allow_empty_topology=True,
    )

    assert plan.removed_proxy_cluster_ids == ["BCS-K8S-10001"]
    assert plan.removed_sub_cluster_ids == ["BCS-K8S-10002"]
    assert models.BcsFederalClusterInfo.objects.get(
        bk_tenant_id="system",
        fed_cluster_id=pair["fed_cluster_id"],
        sub_cluster_id=pair["sub_cluster_id"],
    ).is_deleted
    assert not models.BcsFederalClusterInfo.objects.get(
        bk_tenant_id="tenant-b",
        fed_cluster_id=pair["fed_cluster_id"],
        sub_cluster_id=pair["sub_cluster_id"],
    ).is_deleted


@pytest.mark.django_db(databases="__all__")
def test_sync_federation_clusters_rejects_overlapping_namespaces_before_update(create_or_delete_records):
    existing = models.BcsFederalClusterInfo.objects.create(
        bk_tenant_id="system",
        fed_cluster_id="BCS-K8S-10001",
        host_cluster_id="BCS-K8S-11111",
        sub_cluster_id="BCS-K8S-10002",
        fed_namespaces=["stable"],
    )
    invalid_topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["shared"]},
        },
        "BCS-K8S-70001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["shared"]},
        },
    }

    with pytest.raises(FederationNamespaceConflictError, match="shared"):
        sync_federation_clusters(fed_clusters=invalid_topology, bk_tenant_id="system")

    existing.refresh_from_db()
    assert existing.fed_namespaces == ["stable"]
    assert not existing.is_deleted


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("namespaces", [["ns1", "ns2"], ["ns2", "ns1", "ns1"], None])
def test_federation_unchanged_topology_does_not_apply(create_or_delete_records, mocker, namespaces):
    topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["ns1", "ns2"]},
        }
    }
    # 两个周期入口共用此函数；提交回调在此立即执行以验证投递次数。
    mocker.patch("metadata.task.bcs.transaction.on_commit", side_effect=lambda callback, **kwargs: callback())
    delay = mocker.patch("metadata.task.bcs.reconcile_federation_data_links_task.delay")
    apply = mocker.patch.object(models.DataLink, "apply_data_link_with_retry")
    assert sync_and_schedule_federation_clusters(topology, "system", "discover_bcs_clusters")
    delay.assert_called_once()
    models.BcsFederalClusterInfo.objects.update(reconcile_status="success")
    topology["BCS-K8S-10001"]["sub_clusters"]["BCS-K8S-10002"] = namespaces
    assert sync_and_schedule_federation_clusters(topology, "system", "refresh_bcs_monitor_info")
    delay.assert_called_once()
    plan = sync_federation_clusters(topology)
    assert plan == FederationReconcilePlan()
    reconcile_federation_data_links("system", plan)
    apply.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize(
    "change", ["add", "remove", "namespaces_add", "namespaces_remove", "namespaces_empty", "host", "metric", "event"]
)
def test_federation_topology_changes_trigger_reconcile(create_or_delete_records, change):
    topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["ns1", "ns2"]},
        }
    }
    assert sync_federation_clusters(topology) != FederationReconcilePlan()
    proxy = topology["BCS-K8S-10001"]
    if change == "add":
        proxy["sub_clusters"]["BCS-K8S-10003"] = ["ns3"]
    elif change == "remove":
        proxy["sub_clusters"] = {}
    elif change.startswith("namespaces_"):
        proxy["sub_clusters"]["BCS-K8S-10002"] = {
            "namespaces_add": ["ns1", "ns2", "ns3"],
            "namespaces_remove": ["ns1"],
            "namespaces_empty": [],
        }[change]
    elif change == "host":
        proxy["host_cluster_id"] = "BCS-K8S-22222"
    else:
        data_id = 60010 if change == "metric" else 80001
        models.DataSourceResultTable.objects.filter(bk_data_id=data_id).update(table_id="changed.__default__")
    plan = sync_federation_clusters(topology)
    assert plan != FederationReconcilePlan()
    if change == "remove":
        assert plan.removed_proxy_cluster_ids == ["BCS-K8S-10001"]
        assert plan.removed_sub_cluster_ids == ["BCS-K8S-10002"]
        proxy["sub_clusters"] = {"BCS-K8S-10002": ["ns1", "ns2"]}
        restored = sync_federation_clusters(topology)
        assert restored.active_sub_cluster_ids == ["BCS-K8S-10002"]
    else:
        assert plan.active_proxy_cluster_ids == ["BCS-K8S-10001"]
        assert "BCS-K8S-10002" in plan.active_sub_cluster_ids
    models.BcsFederalClusterInfo.objects.update(reconcile_status="success")
    assert sync_federation_clusters(topology) == FederationReconcilePlan()


@pytest.mark.django_db(databases="__all__")
def test_federation_reconcile_uses_current_topology_and_preserves_dependency_failure(create_or_delete_records, mocker):
    topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["ns1"]},
        }
    }
    sync_federation_clusters(topology)
    service = "metadata.service.federation_data_link"
    proxy = mocker.patch(f"{service}.ensure_federal_proxy_data_link")
    subset = mocker.patch(f"{service}.ensure_federal_subset_data_link")
    delete = mocker.patch(f"{service}.delete_federal_subset_data_link")
    stale_plan = FederationReconcilePlan(
        active_proxy_cluster_ids=["old-proxy"],
        active_sub_cluster_ids=["old-sub"],
        removed_sub_cluster_ids=["BCS-K8S-10002"],
    )
    reconcile_federation_data_links("system", stale_plan)
    proxy.assert_called_once_with(bk_tenant_id="system", fed_cluster_id="BCS-K8S-10001")
    subset.assert_called_once_with(bk_tenant_id="system", sub_cluster_id="BCS-K8S-10002")
    delete.assert_not_called()
    models.BcsFederalClusterInfo.objects.update(reconcile_status="pending")
    proxy.side_effect = RuntimeError("offline")
    subset.reset_mock()
    with pytest.raises(FederationReconcileError, match="failed_dependencies"):
        reconcile_federation_data_links("system", stale_plan)
    subset.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_manual_federation_reconcile_still_builds_full_plan(create_or_delete_records, mocker):
    topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "BCS-K8S-11111",
            "sub_clusters": {"BCS-K8S-10002": ["ns1"]},
        }
    }
    expected = sync_federation_clusters(topology)
    models.BcsFederalClusterInfo.objects.update(reconcile_status="success")
    assert sync_federation_clusters(topology) == FederationReconcilePlan()
    reconcile = mocker.patch(
        "metadata.management.commands.reconcile_federation_data_links.reconcile_federation_data_links"
    )
    call_command("reconcile_federation_data_links", "--tenant-id", "system", "--dry-run")
    reconcile.assert_not_called()
    call_command("reconcile_federation_data_links", "--tenant-id", "system")
    reconcile.assert_called_once_with(bk_tenant_id="system", plan=expected, force=True)


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("change", ["create", "namespace", "delete"])
def test_federation_publish_failure_is_retried(create_or_delete_records, mocker, change):
    topology = {"BCS-K8S-10001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["ns1"]}}}
    if change != "create":
        sync_federation_clusters(topology)
        models.BcsFederalClusterInfo.objects.update(reconcile_status="success")
        topology["BCS-K8S-10001"]["sub_clusters"] = {"BCS-K8S-10002": ["ns2"]} if change == "namespace" else {}
    mocker.patch("metadata.task.bcs.transaction.on_commit", side_effect=lambda callback, **kwargs: callback())
    delay = mocker.patch(
        "metadata.task.bcs.reconcile_federation_data_links_task.delay", side_effect=RuntimeError("broker")
    )
    with pytest.raises(RuntimeError, match="broker"):
        sync_and_schedule_federation_clusters(topology, "system", "test")
    assert set(models.BcsFederalClusterInfo.objects.values_list("reconcile_status", "reconcile_failures")) == {
        ("pending", 0)
    }
    delay.side_effect = None
    sync_and_schedule_federation_clusters(topology, "system", "test")
    assert delay.call_count == 2


@pytest.mark.django_db(databases="__all__")
def test_federation_failure_limit_and_partial_success(create_or_delete_records, mocker, settings):
    settings.BCS_FEDERATION_RECONCILE_MAX_FAILURES = 5
    topology = {
        "BCS-K8S-10001": {
            "host_cluster_id": "host",
            "sub_clusters": {
                "BCS-K8S-10002": ["a"],
                "BCS-K8S-10003": ["b"],
            },
        }
    }
    plan = sync_federation_clusters(topology)
    proxy = mocker.patch("metadata.service.federation_data_link.ensure_federal_proxy_data_link")

    def apply_subset(*, bk_tenant_id, sub_cluster_id):
        if sub_cluster_id == "BCS-K8S-10002":
            raise RuntimeError("offline")

    subset = mocker.patch(
        "metadata.service.federation_data_link.ensure_federal_subset_data_link", side_effect=apply_subset
    )
    for count in range(1, 6):
        with pytest.raises(FederationReconcileError):
            reconcile_federation_data_links("system", plan)
        failed = models.BcsFederalClusterInfo.objects.get(sub_cluster_id="BCS-K8S-10002")
        assert (failed.reconcile_status, failed.reconcile_failures) == ("failed", count)
    assert proxy.call_count == 5
    assert sum(call.kwargs["sub_cluster_id"] == "BCS-K8S-10003" for call in subset.call_args_list) == 1
    assert sync_federation_clusters(topology) == FederationReconcilePlan()
    reconcile_federation_data_links("system", plan)  # 已排队消息也受次数上限约束
    assert proxy.call_count == 5
    topology["BCS-K8S-10001"]["sub_clusters"]["BCS-K8S-10002"] = ["new"]
    new_plan = sync_federation_clusters(topology)
    assert new_plan.active_sub_cluster_ids == ["BCS-K8S-10002"]
    failed.refresh_from_db()
    assert (failed.reconcile_status, failed.reconcile_failures) == ("pending", 0)
    subset.side_effect = None
    reconcile_federation_data_links("system", new_plan)
    failed.refresh_from_db()
    assert (failed.reconcile_status, failed.reconcile_failures) == ("success", 0)


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("cluster_id", ["BCS-K8S-10001", "BCS-K8S-10002"])
def test_federation_business_migration_resets_state(create_or_delete_records, mocker, cluster_id):
    from metadata.task.bcs import migrate_bcs_cluster_business

    topology = {"BCS-K8S-10001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["a"]}}}
    sync_federation_clusters(topology)
    models.BcsFederalClusterInfo.objects.update(reconcile_status="failed", reconcile_failures=5)
    mocker.patch("metadata.task.bcs.change_cluster_router")
    cluster = models.BCSClusterInfo.objects.get(cluster_id=cluster_id)
    migrate_bcs_cluster_business(cluster, 1234, cluster_id == "BCS-K8S-10001")
    cluster.refresh_from_db()
    assert cluster.bk_biz_id == 1234
    plan = sync_federation_clusters(topology)
    assert plan.active_sub_cluster_ids == ["BCS-K8S-10002"]
    assert set(models.BcsFederalClusterInfo.objects.values_list("reconcile_status", "reconcile_failures")) == {
        ("pending", 0)
    }


@pytest.mark.django_db(databases="__all__")
def test_federation_deleted_relationship_retries_restore(create_or_delete_records, mocker):
    topology = {"BCS-K8S-10001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["a"]}}}
    sync_federation_clusters(topology)
    models.BcsFederalClusterInfo.objects.update(reconcile_status="success")
    topology["BCS-K8S-10001"]["sub_clusters"] = {}
    plan = sync_federation_clusters(topology)
    delete = mocker.patch("metadata.service.federation_data_link.delete_federal_subset_data_link")
    restore = mocker.patch(
        "metadata.service.federation_data_link.restore_standard_vm_data_link", side_effect=RuntimeError("offline")
    )
    with pytest.raises(FederationReconcileError):
        reconcile_federation_data_links("system", plan)
    record = models.BcsFederalClusterInfo.objects.get(sub_cluster_id="BCS-K8S-10002")
    assert (record.is_deleted, record.reconcile_status, record.reconcile_failures) == (True, "failed", 1)
    assert sync_federation_clusters(topology) == plan
    restore.side_effect = None
    reconcile_federation_data_links("system", plan)
    record.refresh_from_db()
    assert (record.reconcile_status, record.reconcile_failures) == ("success", 0)
    assert delete.call_count == 2
    assert sync_federation_clusters(topology) == FederationReconcilePlan()


@pytest.mark.django_db(databases="__all__")
def test_federation_multi_proxy_failure_counts_once(create_or_delete_records, mocker):
    topology = {
        "BCS-K8S-10001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["a"]}},
        "BCS-K8S-70001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["b"]}},
    }
    plan = sync_federation_clusters(topology)
    mocker.patch(
        "metadata.service.federation_data_link.ensure_federal_proxy_data_link", side_effect=RuntimeError("offline")
    )
    subset = mocker.patch("metadata.service.federation_data_link.ensure_federal_subset_data_link")
    with pytest.raises(FederationReconcileError):
        reconcile_federation_data_links("system", plan)
    subset.assert_not_called()
    assert list(models.BcsFederalClusterInfo.objects.values_list("reconcile_status", "reconcile_failures")) == [
        ("failed", 1),
        ("failed", 1),
    ]


@pytest.mark.django_db(databases="__all__")
def test_federation_task_stops_retry_at_limit(create_or_delete_records, mocker):
    from metadata.task.bcs import reconcile_federation_data_links_task

    models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id="BCS-K8S-10001",
        sub_cluster_id="BCS-K8S-10002",
        host_cluster_id="host",
        fed_namespaces=["a"],
        reconcile_status="failed",
        reconcile_failures=4,
    )
    mocker.patch(
        "metadata.service.federation_data_link.ensure_federal_proxy_data_link", side_effect=RuntimeError("offline")
    )
    retry = mocker.patch.object(reconcile_federation_data_links_task, "retry")
    reconcile_federation_data_links_task.run("system", ["BCS-K8S-10001"], ["BCS-K8S-10002"], [], [])
    retry.assert_not_called()
    assert models.BcsFederalClusterInfo.objects.get(sub_cluster_id="BCS-K8S-10002").reconcile_failures == 5


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("cluster_id", ["BCS-K8S-10001", "BCS-K8S-10002"])
def test_business_migration_resets_deleted_federation_relations(create_or_delete_records, mocker, cluster_id):
    from metadata.task.bcs import migrate_bcs_cluster_business

    relation = models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id="BCS-K8S-10001",
        sub_cluster_id="BCS-K8S-10002",
        host_cluster_id="host",
        is_deleted=True,
        reconcile_status="failed",
        reconcile_failures=5,
    )
    mocker.patch("metadata.task.bcs.change_cluster_router")
    cluster = models.BCSClusterInfo.objects.get(cluster_id=cluster_id)
    migrate_bcs_cluster_business(cluster, 1234, cluster_id == "BCS-K8S-10001")
    relation.refresh_from_db()
    assert (relation.is_deleted, relation.reconcile_status, relation.reconcile_failures) == (True, "pending", 0)


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("failure", ["init_raises", "init_false", "reset"])
def test_business_migration_rolls_back_router_and_cluster(create_or_delete_records, mocker, failure):
    from metadata.task.bcs import migrate_bcs_cluster_business

    cluster = models.BCSClusterInfo.objects.get(cluster_id="BCS-K8S-10001")
    original_biz = cluster.bk_biz_id
    relation = models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id=cluster.cluster_id,
        sub_cluster_id="BCS-K8S-10002",
        host_cluster_id="host",
        reconcile_status="failed",
        reconcile_failures=5,
    )
    source_before = list(models.DataSource.objects.order_by("pk").values_list("pk", "space_uid"))
    spaces_before = list(models.SpaceDataSource.objects.order_by("pk").values_list("pk", "space_id", "bk_data_id"))
    init = mocker.patch.object(cluster, "init_resource", return_value=failure != "init_false")
    if failure == "init_raises":
        init.side_effect = RuntimeError("init failed")
    elif failure == "reset":
        mocker.patch("metadata.task.bcs.reset_federation_reconcile", side_effect=RuntimeError("reset failed"))
    with pytest.raises(RuntimeError):
        migrate_bcs_cluster_business(cluster, 1234, True)
    cluster.refresh_from_db()
    relation.refresh_from_db()
    assert cluster.bk_biz_id == original_biz
    assert (relation.reconcile_status, relation.reconcile_failures) == ("failed", 5)
    assert list(models.DataSource.objects.order_by("pk").values_list("pk", "space_uid")) == source_before
    assert (
        list(models.SpaceDataSource.objects.order_by("pk").values_list("pk", "space_id", "bk_data_id")) == spaces_before
    )


@pytest.mark.django_db(databases="__all__")
def test_federation_cleanup_failure_is_retried(create_or_delete_records, mocker):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from metadata.service.federation_data_link import FederationMetricContext

    topology = {"BCS-K8S-10001": {"host_cluster_id": "host", "sub_clusters": {"BCS-K8S-10002": ["a"]}}}
    plan = sync_federation_clusters(topology)
    context = FederationMetricContext(
        cluster=models.BCSClusterInfo.objects.get(cluster_id="BCS-K8S-10001"),
        data_source=models.DataSource.objects.get(bk_data_id=60010),
        table_id="1001_bkmonitor_time_series_60010.__default__",
        storage_cluster_name="vm",
    )
    mocker.patch("metadata.service.federation_data_link._get_metric_context", return_value=context)
    mocker.patch("metadata.service.federation_data_link._report_reconcile_metric")
    component = Mock(kind="Databus", name="old-databus")
    component.delete_config.side_effect = RuntimeError("cleanup timeout")
    link = SimpleNamespace(data_link_name="proxy", _is_remote_component_not_found=lambda error: False)

    def apply(**kwargs):
        models.DataLink._cleanup_absent_components(
            link,
            [component],
            raise_on_error=kwargs["raise_on_cleanup_error"],
        )

    mocker.patch("metadata.service.federation_data_link.create_bkbase_data_link", side_effect=apply)
    subset = mocker.patch("metadata.service.federation_data_link.ensure_federal_subset_data_link")
    with pytest.raises(FederationReconcileError):
        reconcile_federation_data_links("system", plan)
    record = models.BcsFederalClusterInfo.objects.get(sub_cluster_id="BCS-K8S-10002")
    assert (record.reconcile_status, record.reconcile_failures) == ("failed", 1)
    component.delete.assert_not_called()
    subset.assert_not_called()
    assert sync_federation_clusters(topology) == plan
    component.delete_config.side_effect = None
    reconcile_federation_data_links("system", plan)
    record.refresh_from_db()
    assert (record.reconcile_status, record.reconcile_failures) == ("success", 0)
    assert component.delete_config.call_count == 2
    assert sync_federation_clusters(topology) == FederationReconcilePlan()
