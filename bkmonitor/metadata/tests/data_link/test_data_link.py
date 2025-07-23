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
from unittest.mock import patch

import pytest
from django.conf import settings
from django.db.utils import IntegrityError
from tenacity import RetryError

from core.errors.api import BKAPIError
from metadata import models
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import BASEREPORT_RESULT_TABLE_FIELD_MAP
from metadata.models.data_link import DataLink, utils
from metadata.models.data_link.constants import (
    DataLinkKind,
    DataLinkResourceStatus,
    BASEREPORT_USAGES,
    BASEREPORT_SOURCE_SYSTEM,
)
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    VMResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.vm.utils import (
    create_bkbase_data_link,
    create_fed_bkbase_data_link,
)
from metadata.task.tasks import create_basereport_datalink_for_bkcc
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    models.Space.objects.create(space_type_id="bkcc", space_id=1, space_name="bkcc_1", bk_tenant_id="system")
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    proxy_data_source = models.DataSource.objects.create(
        bk_data_id=60010,
        data_name="bcs_BCS-K8S-10001_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    federal_sub_data_source = models.DataSource.objects.create(
        bk_data_id=60011,
        data_name="bcs_BCS-K8S-10002_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    multi_tenant_base_data_source = models.DataSource.objects.create(
        bk_data_id=70010,
        data_name="system_1_sys_base",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_multi_tenancy_basereport",
        is_custom_source=False,
    )
    models.BCSClusterInfo.objects.create(
        cluster_id="BCS-K8S-10002",
        bcs_api_cluster_id="BCS-K8S-10002",
        bk_biz_id=1001,
        project_id="proxy",
        domain_name="proxy",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60011,
        K8sEventDataID=60012,
    )
    models.BCSClusterInfo.objects.create(
        cluster_id="BCS-K8S-10001",
        bcs_api_cluster_id="BCS-K8S-10002",
        bk_biz_id=1001,
        project_id="proxy",
        domain_name="proxy",
        port=1001,
        server_address_path="test",
        api_key_content="test",
        K8sMetricDataID=60010,
        K8sEventDataID=60009,
    )
    models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id="BCS-K8S-10001",
        host_cluster_id="BCS-K8S-00000",
        sub_cluster_id="BCS-K8S-10002",
        fed_namespaces=["ns1", "ns2", "ns3"],
        fed_builtin_metric_table_id="1001_bkmonitor_time_series_60010.__default__",
    )
    models.BcsFederalClusterInfo.objects.create(
        fed_cluster_id="BCS-K8S-70001",
        host_cluster_id="BCS-K8S-00000",
        sub_cluster_id="BCS-K8S-10002",
        fed_namespaces=["ns4", "ns5", "ns6"],
        fed_builtin_metric_table_id="1001_bkmonitor_time_series_70010.__default__",
    )
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    proxy_rt = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    fed_rt = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60011.__default__", bk_biz_id=1001, is_custom_table=False
    )
    fed_rt_2 = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_70010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.ClusterInfo.objects.create(
        cluster_name="vm-plat",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.vm",
        port=9090,
        description="",
        cluster_id=100111,
        is_default_cluster=False,
        version="5.x",
    )
    models.ClusterInfo.objects.create(
        cluster_name="vm-default",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="default.vm",
        port=9090,
        description="",
        cluster_id=100112,
        is_default_cluster=True,
        version="6.x",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    proxy_data_source.delete()
    federal_sub_data_source.delete()
    multi_tenant_base_data_source.delete()
    result_table.delete()
    proxy_rt.delete()
    fed_rt.delete()
    fed_rt_2.delete()
    models.ClusterInfo.objects.all().delete()
    BkBaseResultTable.objects.all().delete()
    models.BcsFederalClusterInfo.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    models.Space.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_Standard_V2_Time_Series_compose_configs(create_or_delete_records):
    """
    测试单指标单表类型链路是否能正确生成资源配置
    需要测试：能否正确生成配置，是否正确创建了VMResultTableConfig、VMStorageBindingConfig、DataBusConfig三个实例
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    # 预期的配置
    expected_configs = (
        '[{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},"spec":{'
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}},{"kind":"VmStorageBinding","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"maintainers":["admin"],"storage":{"kind":"VmStorage","name":"vm-plat",'
        '"namespace":"bkmonitor"}}},{"kind":"Databus","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"maintainers":["admin"],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"}],"sources":[{'
        '"kind":"DataId","name":"bkm_data_link_test","namespace":"bkmonitor"}],"transforms":[{'
        '"kind":"PreDefinedLogic","name":"log_to_metric","format":"bkmonitor_standard_v2"}]}}]'
    )

    # 测试配置是否正确生成
    data_link_ins, _ = DataLink.objects.get_or_create(
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
    )

    configs = data_link_ins.compose_configs(data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat")
    assert json.dumps(configs) == expected_configs

    # 测试实例是否正确创建
    vm_table_id_ins = VMResultTableConfig.objects.get(name=bkbase_vmrt_name)
    assert vm_table_id_ins.kind == DataLinkKind.RESULTTABLE.value
    assert vm_table_id_ins.name == bkbase_vmrt_name
    assert vm_table_id_ins.data_link_name == bkbase_data_name
    assert vm_table_id_ins.namespace == "bkmonitor"

    vm_storage_binding_ins = VMStorageBindingConfig.objects.get(name=bkbase_vmrt_name)
    assert vm_storage_binding_ins.kind == DataLinkKind.VMSTORAGEBINDING.value
    assert vm_storage_binding_ins.name == bkbase_vmrt_name
    assert vm_storage_binding_ins.namespace == "bkmonitor"
    assert vm_storage_binding_ins.data_link_name == bkbase_data_name
    assert vm_storage_binding_ins.vm_cluster_name == "vm-plat"

    data_bus_ins = DataBusConfig.objects.get(name=bkbase_vmrt_name)
    assert data_bus_ins.kind == DataLinkKind.DATABUS.value
    assert data_bus_ins.name == bkbase_vmrt_name
    assert data_bus_ins.data_link_name == bkbase_data_name
    assert data_bus_ins.data_id_name == bkbase_data_name
    assert data_bus_ins.namespace == "bkmonitor"


@pytest.mark.django_db(databases="__all__")
def test_compose_bcs_federal_time_series_configs(create_or_delete_records):
    """
    测试联邦代理集群能否正确生成配置
    联邦代理集群应具有ResultTable & VmStorageBinding 两类资源
    测试用例： BCS-K8S-10001为代理集群（ProxyCluster）,其K8S内建指标为60010-1001_bkmonitor_time_series_60010.__default__
    """
    ds = models.DataSource.objects.get(bk_data_id=60010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_bcs_BCS-K8S-10001_k8s_metric"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_60010"

    expected = json.dumps(
        [
            {
                "kind": "ResultTable",
                "metadata": {
                    "name": "bkm_1001_bkmonitor_time_series_60010",
                    "namespace": "bkmonitor",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "alias": "bkm_1001_bkmonitor_time_series_60010",
                    "bizId": 0,
                    "dataType": "metric",
                    "description": "bkm_1001_bkmonitor_time_series_60010",
                    "maintainers": ["admin"],
                },
            },
            {
                "kind": "VmStorageBinding",
                "metadata": {
                    "name": "bkm_1001_bkmonitor_time_series_60010",
                    "namespace": "bkmonitor",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "data": {
                        "kind": "ResultTable",
                        "name": "bkm_1001_bkmonitor_time_series_60010",
                        "namespace": "bkmonitor",
                    },
                    "maintainers": ["admin"],
                    "storage": {"kind": "VmStorage", "name": "vm-plat", "namespace": "bkmonitor"},
                },
            },
        ]
    )
    data_link_ins, _ = models.DataLink.objects.get_or_create(
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        data_link_strategy=models.DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
    )
    configs = data_link_ins.compose_configs(data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat")
    assert json.dumps(configs) == expected


@pytest.mark.django_db(databases="__all__")
def test_compose_bcs_federal_subset_time_series_configs(create_or_delete_records):
    """
    测试联邦集群子集群配置能否正确生成
    联邦集群子集群应具有:ConditionalSink & DataBus等两类资源
    测试用例：
    BCS-K8S-10001为代理集群（ProxyCluster）,其K8S内建指标为60010-1001_bkmonitor_time_series_60010.__default__
    BCS-K8S-70001为代理集群（ProxyCluster）,其K8S内建指标为70010-1001_bkmonitor_time_series_70010.__default__
    BCS-K8S-10002为联邦集群子集群（SubCluster）,其K8S内建指标为60011-1001_bkmonitor_time_series_60011.__default__
    """
    sub_ds = models.DataSource.objects.get(bk_data_id=60011)
    sub_rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60011.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(
        sub_ds.data_name, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES
    )
    assert bkbase_data_name == "fed_bkm_bcs_BCS-K8S-10002_k8s_metric"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(sub_rt.table_id, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_60011_fed"

    expected = json.dumps(
        [
            {
                "kind": "ConditionalSink",
                "metadata": {
                    "namespace": "bkmonitor",
                    "name": "bkm_1001_bkmonitor_time_series_60011_fed",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "conditions": [
                        {
                            "match_labels": [{"name": "namespace", "any": ["ns1", "ns2", "ns3"]}],
                            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
                            "sinks": [
                                {
                                    "kind": "VmStorageBinding",
                                    "name": "bkm_1001_bkmonitor_time_series_60010",
                                    "namespace": "bkmonitor",
                                }
                            ],
                        },
                        {
                            "match_labels": [{"name": "namespace", "any": ["ns4", "ns5", "ns6"]}],
                            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-70001"}],
                            "sinks": [
                                {
                                    "kind": "VmStorageBinding",
                                    "name": "bkm_1001_bkmonitor_time_series_70010",
                                    "namespace": "bkmonitor",
                                }
                            ],
                        },
                    ]
                },
            },
            {
                "kind": "Databus",
                "metadata": {
                    "name": "bkm_1001_bkmonitor_time_series_60011_fed",
                    "namespace": "bkmonitor",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "maintainers": ["admin"],
                    "sinks": [
                        {
                            "kind": "ConditionalSink",
                            "name": "bkm_1001_bkmonitor_time_series_60011_fed",
                            "namespace": "bkmonitor",
                        }
                    ],
                    "sources": [
                        {"kind": "DataId", "name": "bkm_bcs_BCS-K8S-10002_k8s_metric", "namespace": "bkmonitor"}
                    ],
                    "transforms": [
                        {"kind": "PreDefinedLogic", "name": "log_to_metric", "format": "bkmonitor_standard_v2"}
                    ],
                },
            },
        ]
    )

    data_link_ins, _ = models.DataLink.objects.get_or_create(
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        data_link_strategy=models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES,
    )
    content = data_link_ins.compose_configs(
        data_source=sub_ds, table_id=sub_rt.table_id, bcs_cluster_id="BCS-K8S-10002", storage_cluster_name="vm-plat"
    )
    assert json.dumps(content) == expected

    conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name)
    assert conditional_sink_ins.namespace == "bkmonitor"
    assert conditional_sink_ins.name == bkbase_vmrt_name

    databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name)
    assert databus_ins.namespace == "bkmonitor"
    assert databus_ins.name == bkbase_vmrt_name


@pytest.mark.django_db(databases="__all__")
def test_Standard_V2_Time_Series_apply_data_link(create_or_delete_records):
    """
    测试完整流程：单指标单表套餐apply_data_link是否如期执行
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    data_link_ins, _ = DataLink.objects.get_or_create(
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
    )

    # 模拟 compose_configs 方法，确保它返回预期的配置
    expected_configs = (
        '[{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},"spec":{'
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}},{"kind":"VmStorageBinding","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"maintainers":["admin"],"storage":{"kind":"VmStorage","name":"vm-plat",'
        '"namespace":"bkmonitor"}}},{"kind":"Databus","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"maintainers":["admin"],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"}],"sources":[{'
        '"kind":"DataId","name":"bkm_data_link_test","namespace":"bkmonitor"}],"transforms":[{'
        '"kind":"PreDefinedLogic","name":"log_to_metric","format":"bkmonitor_standard_v2"}]}}]'
    )

    with (
        patch.object(DataLink, "compose_configs", return_value=expected_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        data_link_ins.apply_data_link(data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat")

        # 验证 compose_configs 被调用并返回预期的配置
        mock_compose_configs.assert_called_once()
        actual_configs = mock_compose_configs.return_value
        assert actual_configs == expected_configs

        # 验证 apply_data_link_with_retry 被调用并返回模拟的值
        mock_apply_with_retry.assert_called_once()

    assert BkBaseResultTable.objects.filter(data_link_name=bkbase_data_name).exists()
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).monitor_table_id == rt.table_id
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).storage_type == models.ClusterInfo.TYPE_VM
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).status
        == DataLinkResourceStatus.INITIALIZING.value
    )


@pytest.mark.django_db(databases="__all__")
def test_compose_configs_transaction_failure(create_or_delete_records):
    """
    测试在 compose_configs 操作中途发生错误时，事务是否能正确回滚
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)

    # 模拟 VMResultTableConfig 的 get_or_create 操作抛出异常
    with patch(
        "metadata.models.data_link.data_link_configs.VMResultTableConfig.objects.get_or_create",
        side_effect=IntegrityError("Simulated error"),
    ):
        with pytest.raises(IntegrityError):
            # 开始事务
            data_link_ins, created = DataLink.objects.get_or_create(
                data_link_name=bkbase_data_name,
                namespace="bkmonitor",
                data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
            )

            # 调用 compose_configs 方法，该方法内部会调用 get_or_create
            data_link_ins.compose_configs(data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat")

    # 确保由于事务回滚，没有任何配置实例对象被创建
    assert DataLink.objects.filter(data_link_name=bkbase_data_name).exists()
    assert not VMResultTableConfig.objects.filter(name=bkbase_vmrt_name).exists()
    assert not VMStorageBindingConfig.objects.filter(name=bkbase_vmrt_name).exists()
    assert not DataBusConfig.objects.filter(name=bkbase_vmrt_name).exists()


@pytest.mark.django_db(databases="__all__")
def test_Standard_V2_Time_Series_apply_data_link_with_failure(create_or_delete_records):
    """
    测试完整流程：单指标单表套餐apply_data_link出现异常时，是否能够如期工作
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    data_link_ins, _ = DataLink.objects.get_or_create(
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
    )

    # 模拟请求外部API时出现了异常
    with (
        patch.object(DataLink, "compose_configs", return_value="") as mock_compose_configs,
        patch.object(DataLink, "apply_data_link_with_retry", side_effect=BKAPIError("apply_data_link_with_retry")),
    ):  # noqa
        with pytest.raises(BKAPIError):
            data_link_ins.apply_data_link(data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat")

    mock_compose_configs.assert_called_once()
    assert BkBaseResultTable.objects.filter(data_link_name=bkbase_data_name).exists()
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).monitor_table_id == rt.table_id
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).storage_type == models.ClusterInfo.TYPE_VM
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).status
        == DataLinkResourceStatus.INITIALIZING.value
    )

    # 验证重试装饰器是否正常工作，重试四次 间隔 1->2->4->8秒
    with pytest.raises(RetryError):
        data_link_ins.apply_data_link_with_retry(configs="")


@pytest.mark.django_db(databases="__all__")
def test_create_bkbase_data_link(create_or_delete_records, mocker):
    """
    测试接入计算平台数据量路是否如期工作
    """
    mocker.patch("metadata.models.vm.utils.settings.ENABLE_V2_ACCESS_BKBASE_METHOD", True)
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    expected_configs = (
        '[{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},"spec":{'
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}},{"kind":"VmStorageBinding","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"maintainers":["admin"],"storage":{"kind":"VmStorage","name":"vm-plat",'
        '"namespace":"bkmonitor"}}},{"kind":"Databus","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor","labels":{"bk_biz_id":"1001"}},'
        '"spec":{"maintainers":["admin"],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"}],"sources":[{'
        '"kind":"DataId","name":"bkm_data_link_test","namespace":"bkmonitor"}],"transforms":[{'
        '"kind":"PreDefinedLogic","name":"log_to_metric","format":"bkmonitor_standard_v2"}]}}]'
    )

    with (
        patch.object(DataLink, "compose_configs", return_value=expected_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        create_bkbase_data_link(data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat")
        # 验证 compose_configs 被调用并返回预期的配置
        mock_compose_configs.assert_called_once()
        actual_configs = mock_compose_configs.return_value

        assert actual_configs == expected_configs

        # 验证 apply_data_link_with_retry 被调用并返回模拟的值
        mock_apply_with_retry.assert_called_once()

    assert BkBaseResultTable.objects.filter(data_link_name=bkbase_data_name).exists()
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).monitor_table_id == rt.table_id
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).storage_type == models.ClusterInfo.TYPE_VM
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).status
        == DataLinkResourceStatus.INITIALIZING.value
    )
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_rt_name == bkbase_vmrt_name
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_table_id
        == f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}"
    )

    # 测试 旧版 VM记录是否存在
    assert models.AccessVMRecord.objects.filter(result_table_id=rt.table_id).exists()
    vm_record = models.AccessVMRecord.objects.get(result_table_id=rt.table_id)
    assert vm_record.vm_cluster_id == 100111
    assert vm_record.bk_base_data_name == bkbase_data_name
    assert vm_record.vm_result_table_id == f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}"


@pytest.mark.django_db(databases="__all__")
def test_create_bkbase_federal_proxy_data_link(create_or_delete_records, mocker):
    """
    测试接入计算平台数据量路是否如期工作(联邦代理集群场景）
    """
    ds = models.DataSource.objects.get(bk_data_id=60010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_bcs_BCS-K8S-10001_k8s_metric"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_60010"

    expected_configs = json.dumps(
        [
            {
                "kind": "ResultTable",
                "metadata": {
                    "name": "bkm_1001_bkmonitor_time_series_60010",
                    "namespace": "bkmonitor",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "alias": "bkm_1001_bkmonitor_time_series_60010",
                    "bizId": 0,
                    "dataType": "metric",
                    "description": "bkm_1001_bkmonitor_time_series_60010",
                    "maintainers": ["admin"],
                },
            },
            {
                "kind": "VmStorageBinding",
                "metadata": {
                    "name": "bkm_1001_bkmonitor_time_series_60010",
                    "namespace": "bkmonitor",
                    "labels": {"bk_biz_id": "1001"},
                },
                "spec": {
                    "data": {
                        "kind": "ResultTable",
                        "name": "bkm_1001_bkmonitor_time_series_60010",
                        "namespace": "bkmonitor",
                    },
                    "maintainers": ["admin"],
                    "storage": {"kind": "VmStorage", "name": "vm-plat", "namespace": "bkmonitor"},
                },
            },
        ]
    )
    assert expected_configs == expected_configs

    bcs_cluster_id = None

    bcs_record = models.BCSClusterInfo.objects.filter(K8sMetricDataID=ds.bk_data_id)
    if bcs_record:
        bcs_cluster_id = bcs_record.first().cluster_id

    with patch.object(
        DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
    ) as mock_apply_with_retry:  # noqa
        create_bkbase_data_link(
            data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat", bcs_cluster_id=bcs_cluster_id
        )
        # 验证 apply_data_link_with_retry 被调用并返回模拟的值
        mock_apply_with_retry.assert_called_once()

    assert BkBaseResultTable.objects.filter(data_link_name=bkbase_data_name).exists()
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).monitor_table_id == rt.table_id
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).storage_type == models.ClusterInfo.TYPE_VM
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).status
        == DataLinkResourceStatus.INITIALIZING.value
    )
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_rt_name == bkbase_vmrt_name
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_table_id
        == f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}"
    )

    vm_table_id_ins = models.VMResultTableConfig.objects.get(data_link_name=bkbase_data_name)
    assert vm_table_id_ins.name == bkbase_vmrt_name
    assert vm_table_id_ins.namespace == "bkmonitor"

    databus_ins = models.VMResultTableConfig.objects.get(data_link_name=bkbase_data_name)
    assert databus_ins.name == bkbase_vmrt_name
    assert databus_ins.namespace == "bkmonitor"

    # 测试 旧版 VM记录是否存在
    assert models.AccessVMRecord.objects.filter(result_table_id=rt.table_id).exists()
    vm_record = models.AccessVMRecord.objects.get(result_table_id=rt.table_id)
    assert vm_record.vm_cluster_id == 100111
    assert vm_record.bk_base_data_name == bkbase_data_name
    assert vm_record.vm_result_table_id == f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}"


@pytest.mark.django_db(databases="__all__")
def test_create_sub_federal_data_link(create_or_delete_records, mocker):
    sub_ds = models.DataSource.objects.get(bk_data_id=60011)
    sub_rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_60011.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(sub_ds.data_name, DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_data_name == "fed_bkm_bcs_BCS-K8S-10002_k8s_metric"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(sub_rt.table_id, DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_60011_fed"

    # with patch.object(DataLink, 'compose_configs', return_value=expected) as mock_compose_configs, patch.object(
    #         DataLink, 'apply_data_link_with_retry', return_value={'status': 'success'}
    # ) as mock_apply_with_retry:  # noqa
    with patch.object(
        DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
    ) as mock_apply_with_retry:  # noqa
        create_fed_bkbase_data_link(
            data_source=sub_ds,
            monitor_table_id=sub_rt.table_id,
            storage_cluster_name="vm-plat",
            bcs_cluster_id="BCS-K8S-10002",
        )
        # 验证 apply_data_link_with_retry 被调用并返回模拟的值
        mock_apply_with_retry.assert_called_once()

    assert BkBaseResultTable.objects.filter(data_link_name=bkbase_data_name).exists()
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).monitor_table_id == sub_rt.table_id
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).storage_type == models.ClusterInfo.TYPE_VM
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).status
        == DataLinkResourceStatus.INITIALIZING.value
    )
    assert BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_rt_name == bkbase_vmrt_name
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).bkbase_table_id
        == f"{settings.DEFAULT_BKDATA_BIZ_ID}_{bkbase_vmrt_name}"
    )

    conditional_sink_ins = models.ConditionalSinkConfig.objects.get(data_link_name=bkbase_data_name)
    assert conditional_sink_ins.namespace == "bkmonitor"
    assert conditional_sink_ins.name == bkbase_vmrt_name

    databus_ins = models.DataBusConfig.objects.get(data_link_name=bkbase_data_name)
    assert databus_ins.namespace == "bkmonitor"
    assert databus_ins.name == bkbase_vmrt_name


@pytest.mark.django_db(databases="__all__")
def test_component_id(create_or_delete_records, mocker):
    """
    测试component_id是否正确组装
    """
    mocker.patch("metadata.models.vm.utils.settings.ENABLE_V2_ACCESS_BKBASE_METHOD", True)
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    BkBaseResultTable.objects.create(
        data_link_name=bkbase_data_name,
        monitor_table_id=rt.table_id,
        bkbase_rt_name=bkbase_vmrt_name,
    )

    DataBusConfig.objects.create(data_link_name=bkbase_data_name, namespace="bkmonitor", name=bkbase_vmrt_name)

    # 测试component_id
    assert (
        BkBaseResultTable.objects.get(data_link_name=bkbase_data_name).component_id
        == "bkmonitor-bkm_1001_bkmonitor_time_series_50010"
    )


@pytest.mark.django_db(databases="__all__")
def test_create_basereport_datalink_for_bkcc_metadata_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集数据链路创建
    Metadata部分,不包含具体V4链路配置
    """
    mocker.patch("metadata.models.vm.utils.settings.ENABLE_V2_ACCESS_BKBASE_METHOD", True)
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_basereport_datalink_for_bkcc(bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    table_id_prefix = "system_1_sys."
    multi_tenancy_base_report_rts = models.ResultTable.objects.filter(table_id__startswith=table_id_prefix)
    assert len(multi_tenancy_base_report_rts) == 11

    # 测试元信息是否符合预期
    # ResultTable & ResultTableField & DataSourceResultTable & AccessVMRecord
    for usage in BASEREPORT_USAGES:
        # 预期的结果表和VMRT命名
        table_id = f"{table_id_prefix}{usage}"
        vm_result_table_id = f"base_1_sys_{usage}"

        # ResultTable
        result_table = models.ResultTable.objects.get(table_id=table_id)
        assert result_table.bk_biz_id == 1
        assert result_table.is_enable
        assert result_table.bk_tenant_id == "system"

        # AccessVMRecord
        vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
        assert vm_record
        assert vm_record.bk_base_data_id == 70010
        assert vm_record.vm_result_table_id == vm_result_table_id
        assert vm_record.vm_cluster_id == 100112

        # DataSourceResultTable
        dsrt = models.DataSourceResultTable.objects.get(table_id=table_id)
        assert dsrt.bk_data_id == 70010
        assert dsrt.bk_tenant_id == "system"
        # ResultTableField
        expected_fields = BASEREPORT_RESULT_TABLE_FIELD_MAP.get(usage)
        for expected_field in expected_fields:
            field = models.ResultTableField.objects.get(table_id=table_id, field_name=expected_field["field_name"])
            assert field
            assert field.field_type == expected_field["field_type"]
            assert field.bk_tenant_id == "system"


@pytest.mark.django_db(databases="__all__")
def test_create_basereport_datalink_for_bkcc_bkbase_v4_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集数据链路创建
    V4链路配置
    """
    mocker.patch("metadata.models.vm.utils.settings.ENABLE_V2_ACCESS_BKBASE_METHOD", True)
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_basereport_datalink_for_bkcc(bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    data_link_ins = models.DataLink.objects.get(data_link_name="system_1_sys_base")
    data_source = models.DataSource.objects.get(data_name="system_1_sys_base")
    storage_cluster_name = "vm-default"
    actual_configs = data_link_ins.compose_configs(
        data_source=data_source, storage_cluster_name=storage_cluster_name, bk_biz_id=1, source=BASEREPORT_SOURCE_SYSTEM
    )
    expected_config = [
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_summary",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_cpu_summary",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_cpu_summary",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_summary",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_cpu_summary",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_detail",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_cpu_detail",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_cpu_detail",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_detail",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_cpu_detail",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_disk",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_disk",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_disk",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_disk",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_disk",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_env",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_env",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_env",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_env",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {"kind": "ResultTable", "name": "base_1_sys_env", "namespace": "bkmonitor", "tenant": "system"},
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_inode",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_inode",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_inode",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_inode",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_inode",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_io",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_io",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_io",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_io",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {"kind": "ResultTable", "name": "base_1_sys_io", "namespace": "bkmonitor", "tenant": "system"},
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_load",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_load",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_load",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_load",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_load",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_mem",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_mem",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_mem",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_mem",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {"kind": "ResultTable", "name": "base_1_sys_mem", "namespace": "bkmonitor", "tenant": "system"},
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_net",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_net",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_net",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_net",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {"kind": "ResultTable", "name": "base_1_sys_net", "namespace": "bkmonitor", "tenant": "system"},
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_netstat",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_netstat",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_netstat",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_netstat",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_netstat",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_swap",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_swap",
                "bizId": 0,
                "dataType": "metric",
                "description": "base_1_sys_swap",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_swap",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_swap",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {"kind": "VmStorage", "name": "vm-default", "namespace": "bkmonitor", "tenant": "system"},
            },
        },
        {
            "kind": "ConditionalSink",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "system_1_sys_base",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "conditions": [
                    {
                        "match_labels": [{"any": ["cpu_summary"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "cpu_summary"}],
                        "sinks": [
                            {"kind": "VmStorageBinding", "name": "base_1_sys_cpu_summary", "namespace": "bkmonitor"}
                        ],
                    },
                    {
                        "match_labels": [{"any": ["cpu_detail"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "cpu_detail"}],
                        "sinks": [
                            {"kind": "VmStorageBinding", "name": "base_1_sys_cpu_detail", "namespace": "bkmonitor"}
                        ],
                    },
                    {
                        "match_labels": [{"any": ["disk"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "disk"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_disk", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["env"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "env"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_env", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["inode"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "inode"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_inode", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["io"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "io"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_io", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["load"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "load"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_load", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["mem"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "mem"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_mem", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["net"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "net"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_net", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["netstat"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "netstat"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_netstat", "namespace": "bkmonitor"}],
                    },
                    {
                        "match_labels": [{"any": ["swap"], "name": "__result_table"}],
                        "relabels": [{"name": "__result_table", "value": "swap"}],
                        "sinks": [{"kind": "VmStorageBinding", "name": "base_1_sys_swap", "namespace": "bkmonitor"}],
                    },
                ]
            },
        },
        {
            "kind": "Databus",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "system_1_sys_base",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "maintainers": ["admin"],
                "sinks": [{"kind": "ConditionalSink", "name": "system_1_sys_base", "namespace": "bkmonitor"}],
                "sources": [
                    {"kind": "DataId", "name": "system_1_sys_base", "namespace": "bkmonitor", "tenant": "system"}
                ],
                "transforms": [
                    {"format": "bkmonitor_basereport_v1", "kind": "PreDefinedLogic", "name": "log_to_metric"}
                ],
            },
        },
    ]
    assert actual_configs == expected_config
