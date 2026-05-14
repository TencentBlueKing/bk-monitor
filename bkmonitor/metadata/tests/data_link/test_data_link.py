"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from core.errors.api import BKAPIError
from metadata import models
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import (
    BASE_EVENT_RESULT_TABLE_FIELD_MAP,
    BASE_EVENT_RESULT_TABLE_FIELD_OPTION_MAP,
    BASE_EVENT_RESULT_TABLE_OPTION_MAP,
    BASEREPORT_RESULT_TABLE_FIELD_MAP,
    SYSTEM_PROC_DATA_LINK_CONFIGS,
)
from metadata.models.data_link import DataLink, utils
from metadata.models.data_link.component_reuse import (
    ComponentReuseError,
    ExistingComponentContext,
)
from metadata.models.data_link.constants import (
    BASEREPORT_SOURCE_SYSTEM,
    BASEREPORT_USAGES,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    ResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.models.space.constants import EtlConfigs
from metadata.models.vm.utils import (
    create_bkbase_data_link,
    create_fed_bkbase_data_link,
)
from metadata.task.tasks import (
    create_base_event_datalink_for_bkcc,
    create_basereport_datalink_for_bkcc,
    create_system_proc_datalink_for_bkcc,
)
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
    models.DataSource.objects.create(
        bk_data_id=50011,
        data_name="bk_exporter_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EtlConfigs.BK_EXPORTER.value,
        is_custom_source=False,
    )
    models.DataSource.objects.create(
        bk_data_id=50012,
        data_name="bk_standard_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=EtlConfigs.BK_STANDARD.value,
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
    multi_tenant_base_event_data_source = models.DataSource.objects.create(
        bk_data_id=80010,
        data_name="base_1_agent_event",
        bk_tenant_id="system",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_multi_tenancy_agent_event",
        is_custom_source=False,
    )
    # 系统进程数据链路相关的数据源
    multi_tenant_system_proc_perf_data_source = models.DataSource.objects.create(
        bk_data_id=90010,
        data_name="base_1_system_proc_perf",
        bk_tenant_id="test_tenant",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_multi_tenancy_system_proc_perf",
        is_custom_source=False,
        source_label="bk_monitor",
        type_label="time_series",
    )
    multi_tenant_system_proc_port_data_source = models.DataSource.objects.create(
        bk_data_id=90011,
        data_name="base_1_system_proc_port",
        bk_tenant_id="test_tenant",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_multi_tenancy_system_proc_port",
        is_custom_source=False,
        source_label="bk_monitor",
        type_label="time_series",
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
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50011.__default__", bk_biz_id=1001, is_custom_table=False
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50012.__default__", bk_biz_id=1001, is_custom_table=False
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
        bk_tenant_id="system",
    )
    models.ClusterInfo.objects.create(
        cluster_name="vm-default2",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="default.vm",
        port=9090,
        description="",
        cluster_id=100112,
        is_default_cluster=True,
        version="6.x",
        bk_tenant_id="system",
    )
    models.ClusterInfo.objects.create(
        cluster_name="vm-default",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="default.vm",
        port=9090,
        description="",
        cluster_id=100113,
        is_default_cluster=True,
        version="6.x",
        bk_tenant_id="test_tenant",
    )
    models.ClusterInfo.objects.create(
        cluster_name="es_default",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="default.es",
        port=9090,
        description="",
        cluster_id=666666,
        is_default_cluster=True,
        version="6.x",
        bk_tenant_id="system",
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    proxy_data_source.delete()
    federal_sub_data_source.delete()
    multi_tenant_base_data_source.delete()
    multi_tenant_base_event_data_source.delete()
    multi_tenant_system_proc_perf_data_source.delete()
    multi_tenant_system_proc_port_data_source.delete()
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
    # 清理系统进程数据链路测试创建的数据
    models.DataSource.objects.filter(data_name__in=["base_1_system_proc_perf", "base_1_system_proc_port"]).delete()
    models.ResultTable.objects.filter(table_id__in=["system_1_system_proc.perf", "system_1_system_proc.port"]).delete()
    models.AccessVMRecord.objects.filter(
        result_table_id__in=["system_1_system_proc.perf", "system_1_system_proc.port"]
    ).delete()
    models.DataLink.objects.filter(data_link_name__in=["base_1_system_proc_perf", "base_1_system_proc_port"]).delete()


@pytest.mark.django_db(databases="__all__")
def test_Standard_V2_Time_Series_compose_configs(create_or_delete_records):
    """
    测试单指标单表类型链路是否能正确生成资源配置
    需要测试：能否正确生成配置，是否正确创建了ResultTableConfig、VMStorageBindingConfig、DataBusConfig三个实例
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
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":2,'
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

    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        configs = data_link_ins.compose_configs(
            bk_biz_id=1001, data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
    assert json.dumps(configs) == expected_configs

    # 测试实例是否正确创建
    vm_table_id_ins = ResultTableConfig.objects.get(name=bkbase_vmrt_name)
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
                    "bizId": 2,
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
    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        configs = data_link_ins.compose_configs(
            bk_biz_id=1001, data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
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
        bk_biz_id=1001,
        data_source=sub_ds,
        table_id=sub_rt.table_id,
        bcs_cluster_id="BCS-K8S-10002",
        storage_cluster_name="vm-plat",
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
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":2,'
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

    # 模拟 ResultTableConfig 的 get_or_create 操作抛出异常
    with patch(
        "metadata.models.data_link.data_link_configs.ResultTableConfig.objects.get_or_create",
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
            data_link_ins.compose_configs(
                bk_biz_id=1001, data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat"
            )

    # 确保由于事务回滚，没有任何配置实例对象被创建
    assert DataLink.objects.filter(data_link_name=bkbase_data_name).exists()
    assert not ResultTableConfig.objects.filter(name=bkbase_vmrt_name).exists()
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

    def _create_configs(*args, **kwargs):
        """compose_configs 被 mock 后 ORM 行不会被实际创建，这里显式补上，供 sync_metadata 读实名。"""
        ResultTableConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            table_id=rt.table_id,
            defaults={"name": bkbase_vmrt_name, "bk_biz_id": 1001},
        )
        DataBusConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            defaults={
                "name": bkbase_data_name,
                "data_id_name": bkbase_data_name,
                "bk_biz_id": 1001,
                "bk_data_id": ds.bk_data_id,
                "sink_names": [],
            },
        )
        return expected_configs

    with (
        patch.object(DataLink, "compose_configs", side_effect=_create_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
        mock_compose_configs.assert_called_once()
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

    bcs_record = models.BCSClusterInfo.objects.filter(K8sMetricDataID=ds.bk_data_id).first()
    if bcs_record:
        bcs_cluster_id = bcs_record.cluster_id

    with patch.object(
        DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
    ) as mock_apply_with_retry:  # noqa
        create_bkbase_data_link(
            bk_biz_id=1001,
            data_source=ds,
            monitor_table_id=rt.table_id,
            storage_cluster_name="vm-plat",
            bcs_cluster_id=bcs_cluster_id,
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

    vm_table_id_ins = models.ResultTableConfig.objects.get(data_link_name=bkbase_data_name)
    assert vm_table_id_ins.name == bkbase_vmrt_name
    assert vm_table_id_ins.namespace == "bkmonitor"

    databus_ins = models.ResultTableConfig.objects.get(data_link_name=bkbase_data_name)
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
            bk_biz_id=1001,
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
def test_create_basereport_datalink_for_bkcc_metadata_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集数据链路创建
    Metadata部分,不包含具体V4链路配置
    """
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_basereport_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    table_id_prefix = "system_1_sys."
    multi_tenancy_base_report_rts = models.ResultTable.objects.filter(table_id__startswith=table_id_prefix)
    assert len(multi_tenancy_base_report_rts) == 11

    # 测试元信息是否符合预期
    # ResultTable & ResultTableField & DataSourceResultTable & AccessVMRecord
    for usage in BASEREPORT_USAGES:
        # 预期的结果表和VMRT命名
        table_id = f"{table_id_prefix}{usage}"
        vm_result_table_id = f"1_base_1_sys_{usage}"

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
        expected_fields = BASEREPORT_RESULT_TABLE_FIELD_MAP[usage]
        for expected_field in expected_fields:
            field = models.ResultTableField.objects.get(table_id=table_id, field_name=expected_field["field_name"])
            assert field
            assert field.field_type == expected_field["field_type"]
            assert field.bk_tenant_id == "system"


@pytest.mark.django_db(databases="__all__")
def test_create_basereport_datalink_for_bkcc_extra_source_metadata_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集额外主机维度数据链路 Metadata 部分。
    """
    settings.ENABLE_MULTI_TENANT_MODE = True
    extra_source = "bkcc"

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        create_basereport_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1, extra_source=extra_source)
        mock_apply_with_retry.assert_called_once()

    data_source = models.DataSource.objects.get(data_name="system_1_sys_base")
    table_id_prefix = f"system_1_{extra_source}."
    extra_result_tables = models.ResultTable.objects.filter(table_id__startswith=table_id_prefix)
    assert len(extra_result_tables) == 11
    assert set(extra_result_tables.values_list("data_label", flat=True)) == {f"{extra_source}_system"}

    data_link_ins = models.DataLink.objects.get(data_link_name="system_1_sys_base")
    assert len(data_link_ins.table_ids) == 22

    for usage in BASEREPORT_USAGES:
        table_id = f"{table_id_prefix}{usage}"
        result_table = models.ResultTable.objects.get(table_id=table_id)
        assert result_table.bk_biz_id == 1
        assert result_table.is_enable
        assert result_table.bk_tenant_id == "system"
        assert result_table.data_label == f"{extra_source}_system"

        vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
        assert vm_record.bk_base_data_id == data_source.bk_data_id
        assert vm_record.vm_result_table_id == f"1_base_1_{extra_source}_{usage}"
        assert vm_record.vm_cluster_id == 100112

        dsrt = models.DataSourceResultTable.objects.get(table_id=table_id)
        assert dsrt.bk_data_id == data_source.bk_data_id
        assert dsrt.bk_tenant_id == "system"

        expected_fields = BASEREPORT_RESULT_TABLE_FIELD_MAP[usage]
        for expected_field in expected_fields:
            field = models.ResultTableField.objects.get(table_id=table_id, field_name=expected_field["field_name"])
            assert field.field_type == expected_field["field_type"]
            assert field.bk_tenant_id == "system"


@pytest.mark.django_db(databases="__all__")
def test_create_basereport_datalink_for_bkcc_bkbase_v4_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集数据链路创建
    V4链路配置
    """
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_basereport_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    data_link_ins = models.DataLink.objects.get(data_link_name="system_1_sys_base")
    data_source = models.DataSource.objects.get(data_name="system_1_sys_base")
    storage_cluster_name = "vm-default"
    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        actual_configs = data_link_ins.compose_configs(
            data_source=data_source,
            storage_cluster_name=storage_cluster_name,
            bk_biz_id=1,
            source=BASEREPORT_SOURCE_SYSTEM,
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_cpu_summary",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_summary_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_cpu_summary_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_cpu_summary_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_summary_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_cpu_summary_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_cpu_detail",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_detail_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_cpu_detail_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_cpu_detail_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_cpu_detail_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_cpu_detail_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_disk",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_disk_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_disk_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_disk_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_disk_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_disk_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_env",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_env_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_env_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_env_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_env_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_env_cmdb",
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
                "name": "base_1_sys_inode",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_inode",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_inode",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_inode_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_inode_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_inode_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_inode_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_inode_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_io",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_io_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_io_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_io_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_io_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_io_cmdb",
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
                "name": "base_1_sys_load",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_load",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_load",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_load_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_load_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_load_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_load_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_load_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_mem",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_mem_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_mem_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_mem_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_mem_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_mem_cmdb",
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
                "name": "base_1_sys_net",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_net",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_net",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_net_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_net_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_net_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_net_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_net_cmdb",
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
                "name": "base_1_sys_netstat",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_netstat",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_netstat",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_netstat_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_netstat_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_netstat_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_netstat_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_netstat_cmdb",
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
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_swap",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_swap_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_sys_swap_cmdb",
                "bizId": 1,
                "dataType": "metric",
                "description": "base_1_sys_swap_cmdb",
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
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_sys_swap_cmdb",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_sys_swap_cmdb",
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
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_cpu_summary",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["cpu_summary_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_cpu_summary_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["cpu_detail"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_cpu_detail",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["cpu_detail_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_cpu_detail_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["disk"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_disk",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["disk_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_disk_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["env"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_env",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["env_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_env_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["inode"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_inode",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["inode_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_inode_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["io"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_io",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["io_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_io_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["load"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_load",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["load_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_load_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["mem"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_mem",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["mem_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_mem_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["net"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_net",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["net_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_net_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["netstat"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_netstat",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["netstat_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_netstat_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["swap"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_swap",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"any": ["swap_cmdb"], "name": "__result_table"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "base_1_sys_swap_cmdb",
                                "namespace": "bkmonitor",
                                "tenant": "system",
                            }
                        ],
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
                "sinks": [
                    {
                        "kind": "ConditionalSink",
                        "name": "system_1_sys_base",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
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


@pytest.mark.django_db(databases="__all__")
def test_create_basereport_datalink_for_bkcc_extra_source_bkbase_v4_part(create_or_delete_records, mocker):
    """
    测试多租户基础采集额外主机维度 V4 链路配置。
    """
    settings.ENABLE_MULTI_TENANT_MODE = True
    extra_source = "bkcc"

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        create_basereport_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1, extra_source=extra_source)
        mock_apply_with_retry.assert_called_once()

    data_link_ins = models.DataLink.objects.get(data_link_name="system_1_sys_base")
    data_source = models.DataSource.objects.get(data_name="system_1_sys_base")
    storage_cluster_name = "vm-default2"
    actual_configs = data_link_ins.compose_configs(
        data_source=data_source,
        storage_cluster_name=storage_cluster_name,
        bk_biz_id=1,
        source=BASEREPORT_SOURCE_SYSTEM,
        extra_source=extra_source,
    )

    basereport_sink = next(c for c in actual_configs if c["kind"] == "BasereportSink")
    assert basereport_sink["metadata"] == {
        "name": f"system_1_sys_base_{extra_source}",
        "namespace": "bkmonitor",
        "tenant": "system",
    }
    mapping_by_metric = {m["metric_type"]: m["sinks"] for m in basereport_sink["spec"]["mappings"]}
    assert set(mapping_by_metric) == set(BASEREPORT_USAGES)
    for usage in BASEREPORT_USAGES:
        assert mapping_by_metric[usage] == [
            {
                "kind": "VmStorageBinding",
                "name": f"base_1_{extra_source}_{usage}",
                "namespace": "bkmonitor",
                "tenant": "system",
            }
        ]

    extra_databus = next(
        c
        for c in actual_configs
        if c["kind"] == "Databus" and c["metadata"]["name"] == f"system_1_sys_base_{extra_source}"
    )
    assert extra_databus["spec"]["sinks"] == [
        {
            "kind": "BasereportSink",
            "name": f"system_1_sys_base_{extra_source}",
            "namespace": "bkmonitor",
            "tenant": "system",
        }
    ]
    assert extra_databus["spec"]["sources"] == [
        {"kind": "DataId", "name": "system_1_sys_base", "namespace": "bkmonitor", "tenant": "system"}
    ]
    assert extra_databus["spec"]["transforms"] == [
        {
            "extra_dims": True,
            "format": "bkmonitor_basereport_v1",
            "kind": "PreDefinedLogic",
            "name": "log_to_metric",
        }
    ]
    assert "biz_to_rt_prefix" not in extra_databus["spec"]["transforms"][0]

    extra_result_table = next(
        c
        for c in actual_configs
        if c["kind"] == "ResultTable" and c["metadata"]["name"] == f"base_1_{extra_source}_cpu_summary"
    )
    assert extra_result_table["spec"]["alias"] == f"base_1_{extra_source}_cpu_summary"


@pytest.mark.django_db(databases="__all__")
def test_create_base_event_datalink_for_bkcc_metadata_part(create_or_delete_records, mocker):
    """
    测试多租户基础事件数据链路
    Metadata部分 -- 元信息关联关系
    """
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_base_event_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    table_id = "base_system_1_event"
    result_table = models.ResultTable.objects.get(table_id=table_id)
    assert result_table.bk_biz_id == 1
    assert result_table.bk_tenant_id == "system"

    fields = BASE_EVENT_RESULT_TABLE_FIELD_MAP.get("base_event", [])
    for field in fields:
        result_table_field = models.ResultTableField.objects.get(table_id=table_id, field_name=field["field_name"])
        assert result_table_field.bk_tenant_id == "system"

    dsrt = models.DataSourceResultTable.objects.get(bk_data_id=80010)
    assert dsrt.table_id == table_id
    assert dsrt.bk_tenant_id == "system"

    es_storage = models.ESStorage.objects.get(table_id=table_id)
    assert es_storage.index_set == table_id
    assert es_storage.storage_cluster_id == 666666
    assert es_storage.bk_tenant_id == "system"

    options = BASE_EVENT_RESULT_TABLE_OPTION_MAP.get("base_event", [])
    for option in options:
        result_table_option = models.ResultTableOption.objects.get(table_id=table_id, name=option["name"])
        assert result_table_option.bk_tenant_id == "system"
        assert result_table_option.value == option["value"]

    field_options = BASE_EVENT_RESULT_TABLE_FIELD_OPTION_MAP.get("base_event", [])
    for field_option in field_options:
        result_table_field_option = models.ResultTableFieldOption.objects.get(
            table_id=table_id, name=field_option["name"], field_name=field_option["field_name"]
        )
        assert result_table_field_option.value == field_option["value"]
        assert result_table_field_option.value_type == field_option["value_type"]


@pytest.mark.django_db(databases="__all__")
def test_create_base_event_datalink_for_bkcc_bkbase_part(create_or_delete_records, mocker):
    """
    测试多租户基础事件数据链路
    BkBase部分 -- V4链路配置
    """
    settings.ENABLE_MULTI_TENANT_MODE = True

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        # 调用多租户基础采集数据链路创建方法
        create_base_event_datalink_for_bkcc(bk_tenant_id="system", bk_biz_id=1)
        mock_apply_with_retry.assert_called_once()

    data_link_ins = models.DataLink.objects.get(data_link_name="base_1_agent_event")
    data_source = models.DataSource.objects.get(data_name="base_1_agent_event", bk_tenant_id="system")

    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        actual_configs = data_link_ins.compose_configs(
            data_source=data_source, table_id="base_system_1_event", storage_cluster_name="es_default", bk_biz_id=1
        )

    expected_configs = [
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_agent_event",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "base_1_agent_event",
                "bizId": 1,
                "dataType": "log",
                "description": "base_1_agent_event",
                "fields": [
                    {
                        "field_alias": "dimensions",
                        "field_index": 0,
                        "field_name": "dimensions",
                        "field_type": "object",
                        "is_dimension": True,
                    },
                    {
                        "field_alias": "event",
                        "field_index": 1,
                        "field_name": "event",
                        "field_type": "object",
                        "is_dimension": True,
                    },
                    {
                        "field_alias": "event_name",
                        "field_index": 2,
                        "field_name": "event_name",
                        "field_type": "string",
                        "is_dimension": True,
                    },
                    {
                        "field_alias": "target",
                        "field_index": 3,
                        "field_name": "target",
                        "field_type": "string",
                        "is_dimension": True,
                    },
                    {
                        "field_alias": "数据上报时间",
                        "field_index": 4,
                        "field_name": "time",
                        "field_type": "timestamp",
                        "is_dimension": False,
                    },
                ],
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "ElasticSearchBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_agent_event",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "base_1_agent_event",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {
                    "kind": "ElasticSearch",
                    "name": "es_default",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "unique_field_list": ["event", "target", "dimensions", "event_name", "time"],
                "write_alias": {"TimeBased": {"format": "write_%Y%m%d_base_system_1_event", "timezone": 0}},
            },
        },
        {
            "kind": "Databus",
            "metadata": {
                "labels": {"bk_biz_id": "1"},
                "name": "base_1_agent_event",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "maintainers": ["admin"],
                "sinks": [
                    {
                        "kind": "ElasticSearchBinding",
                        "name": "base_1_agent_event",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
                "sources": [
                    {"kind": "DataId", "name": "base_1_agent_event", "namespace": "bkmonitor", "tenant": "system"}
                ],
                "transforms": [{"kind": "PreDefinedLogic", "name": "gse_system_event"}],
            },
        },
    ]

    assert actual_configs == expected_configs


@pytest.mark.django_db(databases="__all__")
def test_create_bkbase_data_link_for_bk_exporter(create_or_delete_records, mocker):
    """
    测试bk_exporter V4链路接入 -- Metadata部分 & Datalink V4配置部分
    """
    settings.ENABLE_PLUGIN_ACCESS_V4_DATA_LINK = True
    settings.ENABLE_MULTI_TENANT_MODE = True

    ds = models.DataSource.objects.get(bk_data_id=50011)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50011.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_bk_exporter_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50011"

    def _create_configs(*args, **kwargs):
        ResultTableConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            table_id=rt.table_id,
            defaults={"name": bkbase_vmrt_name, "bk_biz_id": 1001},
        )
        DataBusConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            defaults={
                "name": bkbase_data_name,
                "data_id_name": bkbase_data_name,
                "bk_biz_id": 1001,
                "bk_data_id": ds.bk_data_id,
                "sink_names": [],
            },
        )

    with (
        patch.object(DataLink, "compose_configs", side_effect=_create_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        data_link_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001)
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
        mock_compose_configs.assert_called_once()
        mock_apply_with_retry.assert_called_once()

    bkbase_rt_ins = BkBaseResultTable.objects.get(data_link_name=bkbase_data_name)
    assert bkbase_rt_ins.monitor_table_id == rt.table_id

    data_link_ins = models.DataLink.objects.get(data_link_name=bkbase_data_name)
    assert data_link_ins.data_link_strategy == DataLink.BK_EXPORTER_TIME_SERIES

    vm_record = models.AccessVMRecord.objects.get(result_table_id=rt.table_id)
    assert vm_record.vm_cluster_id == 100111
    assert vm_record.vm_result_table_id == f"{data_link_biz_ids.data_biz_id}_{bkbase_vmrt_name}"

    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        actual_configs = data_link_ins.compose_configs(
            bk_biz_id=1001, data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
    expected_configs = [
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50011",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "bkm_1001_bkmonitor_time_series_50011",
                "bizId": 1001,
                "dataType": "metric",
                "description": "bkm_1001_bkmonitor_time_series_50011",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50011",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "bkm_1001_bkmonitor_time_series_50011",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {
                    "kind": "VmStorage",
                    "name": "vm-plat",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
            },
        },
        {
            "kind": "Databus",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50011",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "maintainers": ["admin"],
                "sinks": [
                    {
                        "kind": "VmStorageBinding",
                        "name": "bkm_1001_bkmonitor_time_series_50011",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "bkm_bk_exporter_test",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
                "transforms": [{"format": "bkmonitor_exporter_v1", "kind": "PreDefinedLogic", "name": "log_to_metric"}],
            },
        },
    ]

    assert actual_configs == expected_configs


@pytest.mark.django_db(databases="__all__")
def test_create_bkbase_data_link_for_bk_standard(create_or_delete_records, mocker):
    """
    测试bk_standard V4链路接入 -- Metadata部分 & Datalink V4配置部分
    """
    settings.ENABLE_PLUGIN_ACCESS_V4_DATA_LINK = True
    settings.ENABLE_MULTI_TENANT_MODE = True

    ds = models.DataSource.objects.get(bk_data_id=50012)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50012.__default__")

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_bk_standard_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50012"

    def _create_configs(*args, **kwargs):
        ResultTableConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            table_id=rt.table_id,
            defaults={"name": bkbase_vmrt_name, "bk_biz_id": 1001},
        )
        DataBusConfig.objects.update_or_create(
            bk_tenant_id=ds.bk_tenant_id,
            namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
            data_link_name=bkbase_data_name,
            defaults={
                "name": bkbase_data_name,
                "data_id_name": bkbase_data_name,
                "bk_biz_id": 1001,
                "bk_data_id": ds.bk_data_id,
                "sink_names": [],
            },
        )

    with (
        patch.object(DataLink, "compose_configs", side_effect=_create_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        data_link_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001)
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
        mock_compose_configs.assert_called_once()
        mock_apply_with_retry.assert_called_once()

    bkbase_rt_ins = BkBaseResultTable.objects.get(data_link_name=bkbase_data_name)
    assert bkbase_rt_ins.monitor_table_id == rt.table_id

    data_link_ins = models.DataLink.objects.get(data_link_name=bkbase_data_name)
    assert data_link_ins.data_link_strategy == DataLink.BK_STANDARD_TIME_SERIES

    vm_record = models.AccessVMRecord.objects.get(result_table_id=rt.table_id)
    assert vm_record.vm_cluster_id == 100111
    assert vm_record.vm_result_table_id == f"{data_link_biz_ids.data_biz_id}_{bkbase_vmrt_name}"

    with patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2):
        actual_configs = data_link_ins.compose_configs(
            bk_biz_id=1001, data_source=ds, table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
    expected_configs = [
        {
            "kind": "ResultTable",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50012",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "alias": "bkm_1001_bkmonitor_time_series_50012",
                "bizId": 1001,
                "dataType": "metric",
                "description": "bkm_1001_bkmonitor_time_series_50012",
                "maintainers": ["admin"],
            },
        },
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50012",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "bkm_1001_bkmonitor_time_series_50012",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
                "maintainers": ["admin"],
                "storage": {
                    "kind": "VmStorage",
                    "name": "vm-plat",
                    "namespace": "bkmonitor",
                    "tenant": "system",
                },
            },
        },
        {
            "kind": "Databus",
            "metadata": {
                "labels": {"bk_biz_id": "1001"},
                "name": "bkm_1001_bkmonitor_time_series_50012",
                "namespace": "bkmonitor",
                "tenant": "system",
            },
            "spec": {
                "maintainers": ["admin"],
                "sinks": [
                    {
                        "kind": "VmStorageBinding",
                        "name": "bkm_1001_bkmonitor_time_series_50012",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "bkm_bk_standard_test",
                        "namespace": "bkmonitor",
                        "tenant": "system",
                    }
                ],
                "transforms": [{"format": "bkmonitor_standard", "kind": "PreDefinedLogic", "name": "log_to_metric"}],
            },
        },
    ]

    assert actual_configs == expected_configs


@pytest.mark.django_db(databases="__all__")
def test_create_system_proc_datalink_for_bkcc(create_or_delete_records, mocker):
    """
    测试多租户系统进程数据链路创建
    Metadata部分 -- 元信息关联关系
    """

    settings.ENABLE_MULTI_TENANT_MODE = True

    bk_tenant_id = "test_tenant"

    with (
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        # 调用多租户系统进程数据链路创建方法
        create_system_proc_datalink_for_bkcc(bk_tenant_id=bk_tenant_id, bk_biz_id=1)
        # 验证 apply_data_link_with_retry 被调用两次（perf 和 port 两个链路）
        assert mock_apply_with_retry.call_count == 2

    # 测试 perf 链路
    perf_table_id = f"{bk_tenant_id}_1_system_proc.perf"
    perf_data_name = "base_1_system_proc_perf"

    # 验证结果表
    result_table = models.ResultTable.objects.get(table_id=perf_table_id)
    assert result_table.bk_biz_id == 1
    assert result_table.bk_tenant_id == bk_tenant_id
    assert result_table.data_label == "system.proc"
    assert result_table.table_name_zh == perf_data_name
    assert result_table.is_custom_table is False
    assert result_table.default_storage == models.ClusterInfo.TYPE_VM

    # 验证数据源
    data_source = models.DataSource.objects.get(data_name=perf_data_name, bk_tenant_id=bk_tenant_id)
    assert data_source.source_label == "bk_monitor"
    assert data_source.type_label == "time_series"

    # 验证数据源结果表关联
    dsrt = models.DataSourceResultTable.objects.get(bk_data_id=data_source.bk_data_id, table_id=perf_table_id)
    assert dsrt.bk_tenant_id == bk_tenant_id

    # 验证 AccessVMRecord
    vm_record = models.AccessVMRecord.objects.get(result_table_id=perf_table_id)
    assert vm_record.bk_tenant_id == bk_tenant_id
    assert vm_record.bk_base_data_id == data_source.bk_data_id
    assert vm_record.bk_base_data_name == perf_data_name
    assert vm_record.vm_result_table_id == "1_base_1_system_proc_perf"

    # 验证结果表字段
    perf_fields = SYSTEM_PROC_DATA_LINK_CONFIGS["perf"]["fields"]
    for field in perf_fields:
        result_table_field = models.ResultTableField.objects.get(table_id=perf_table_id, field_name=field["field_name"])
        assert result_table_field.bk_tenant_id == bk_tenant_id
        assert result_table_field.field_type == field["field_type"]
        assert result_table_field.description == field.get("description", "")
        assert result_table_field.unit == field.get("unit", "")
        assert result_table_field.tag == field.get("tag", "")

    # 验证数据链路
    data_link_ins = models.DataLink.objects.get(data_link_name=perf_data_name)
    assert data_link_ins.bk_tenant_id == bk_tenant_id
    assert data_link_ins.data_link_strategy == DataLink.SYSTEM_PROC_PERF
    assert data_link_ins.namespace == "bkmonitor"

    # 测试 port 链路
    port_table_id = f"{bk_tenant_id}_1_system_proc.port"
    port_data_name = "base_1_system_proc_port"

    # 验证结果表
    result_table = models.ResultTable.objects.get(table_id=port_table_id)
    assert result_table.bk_biz_id == 1
    assert result_table.bk_tenant_id == bk_tenant_id
    assert result_table.data_label == "system.proc_port"
    assert result_table.table_name_zh == port_data_name
    assert result_table.is_custom_table is False
    assert result_table.default_storage == models.ClusterInfo.TYPE_VM

    # 验证数据源
    data_source = models.DataSource.objects.get(data_name=port_data_name, bk_tenant_id=bk_tenant_id)
    assert data_source.source_label == "bk_monitor"
    assert data_source.type_label == "time_series"

    # 验证数据源结果表关联
    dsrt = models.DataSourceResultTable.objects.get(bk_data_id=data_source.bk_data_id, table_id=port_table_id)
    assert dsrt.bk_tenant_id == bk_tenant_id

    # 验证 AccessVMRecord
    vm_record = models.AccessVMRecord.objects.get(result_table_id=port_table_id)
    assert vm_record.bk_tenant_id == bk_tenant_id
    assert vm_record.bk_base_data_id == data_source.bk_data_id
    assert vm_record.bk_base_data_name == port_data_name
    assert vm_record.vm_result_table_id == "1_base_1_system_proc_port"

    # 验证结果表字段
    port_fields = SYSTEM_PROC_DATA_LINK_CONFIGS["port"]["fields"]
    for field in port_fields:
        result_table_field = models.ResultTableField.objects.get(table_id=port_table_id, field_name=field["field_name"])
        assert result_table_field.bk_tenant_id == bk_tenant_id
        assert result_table_field.field_type == field["field_type"]
        assert result_table_field.description == field.get("description", "")
        assert result_table_field.unit == field.get("unit", "")
        assert result_table_field.tag == field.get("tag", "")

    # 验证数据链路
    data_link_ins = models.DataLink.objects.get(data_link_name=port_data_name)
    assert data_link_ins.bk_tenant_id == bk_tenant_id
    assert data_link_ins.data_link_strategy == DataLink.SYSTEM_PROC_PORT
    assert data_link_ins.namespace == "bkmonitor"


# ============================================================
# DataLink 组件复用机制集成测试 -- bk_plugin (bk_exporter / bk_standard)
# ============================================================


@pytest.fixture
def bk_exporter_reuse_enabled():
    """临时把 BK_EXPORTER_TIME_SERIES 纳入复用灰度，用完复原。"""
    original = set(getattr(settings, "DATA_LINK_COMPONENT_REUSE_STRATEGIES", set()))
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = original | {DataLink.BK_EXPORTER_TIME_SERIES}
    try:
        yield
    finally:
        settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = original


@pytest.fixture
def bk_exporter_leftover_policy_keep():
    """把 BK_EXPORTER_TIME_SERIES 三类组件的 leftover 策略改为 keep。"""
    original = dict(DataLink.REUSE_LEFTOVER_POLICY)
    DataLink.REUSE_LEFTOVER_POLICY = {
        **original,
        (DataLink.BK_EXPORTER_TIME_SERIES, ResultTableConfig): "keep",
        (DataLink.BK_EXPORTER_TIME_SERIES, VMStorageBindingConfig): "keep",
        (DataLink.BK_EXPORTER_TIME_SERIES, DataBusConfig): "keep",
    }
    try:
        yield
    finally:
        DataLink.REUSE_LEFTOVER_POLICY = original


def _prepare_bk_exporter_datalink(bk_biz_id: int = 1001):
    """准备 bk_exporter 场景下的 DataLink 实例以及对应 DataSource / ResultTable。"""
    ds = models.DataSource.objects.get(bk_data_id=50011)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50011.__default__")
    data_link_name = utils.compose_bkdata_data_id_name(ds.data_name, DataLink.BK_EXPORTER_TIME_SERIES)
    datalink = DataLink.objects.create(
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_strategy=DataLink.BK_EXPORTER_TIME_SERIES,
    )
    return datalink, ds, rt


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_reuse_three_legacy_components(create_or_delete_records, bk_exporter_reuse_enabled, mocker):
    """三个组件都命中 legacy 时，compose 应复用 name，不新增记录。"""
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="legacy_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    VMStorageBindingConfig.objects.create(
        name="legacy_binding",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
        vm_cluster_name="vm-plat",
        bkbase_result_table_name=bkbase_vmrt_name,
    )
    DataBusConfig.objects.create(
        name="legacy_databus",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name=datalink.data_link_name,
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    ctx = ExistingComponentContext.from_datalink(datalink)
    configs = datalink.compose_configs(
        bk_biz_id=1001,
        data_source=ds,
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        existing_context=ctx,
    )

    # 没有新增：每个 kind 在 DB 里依旧只保留 legacy 记录
    assert ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert VMStorageBindingConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert DataBusConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1

    rt_cfg = ResultTableConfig.objects.get(data_link_name=datalink.data_link_name)
    binding_cfg = VMStorageBindingConfig.objects.get(data_link_name=datalink.data_link_name)
    databus_cfg = DataBusConfig.objects.get(data_link_name=datalink.data_link_name)
    assert rt_cfg.name == "legacy_rt"
    assert binding_cfg.name == "legacy_binding"
    assert databus_cfg.name == "legacy_databus"
    # sink_names 必须联动 legacy binding name，不能回退到 bkbase_vmrt_name
    assert databus_cfg.sink_names == [f"{DataLinkKind.VMSTORAGEBINDING.value}:legacy_binding"]
    # P1 续：binding.bkbase_result_table_name 是 relation.py 用来按 name 回查 RT 的指针，
    # 复用场景下必须同步为实际引用的 RT name（"legacy_rt"），哪怕 legacy fixture 里写的
    # 是老的 bkbase_vmrt_name -- 如果不同步，本地元数据关系会指向一张不存在的 RT。
    assert binding_cfg.bkbase_result_table_name == "legacy_rt"

    # leftover 为空 -- 三条全部 claim 完毕
    assert ctx.leftover() == {}

    # 返回的 spec metadata.name 以及 databus sink name 也应联动 legacy
    assert configs[0]["metadata"]["name"] == "legacy_rt"
    assert configs[1]["metadata"]["name"] == "legacy_binding"
    assert configs[2]["metadata"]["name"] == "legacy_databus"
    assert configs[2]["spec"]["sinks"][0]["name"] == "legacy_binding"
    # P1 回归：binding.spec.data.name 必须指向真正存在的 RT（"legacy_rt"），
    # 不能回退到 binding 自己的 name（"legacy_binding"），否则 BKBase 会收到
    # 指向一张并不存在的 ResultTable 的引用。
    assert configs[1]["spec"]["data"]["name"] == "legacy_rt"

    # P1 回归：sync_metadata 必须从 configs 表读实名回填 BkBaseResultTable。
    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_name="vm-plat")
    from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
    from metadata.models.bkdata.result_table import BkBaseResultTable

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.bkbase_rt_name == "legacy_rt"
    # 业务 id 应和 compose 中 ``self.datalink_biz_ids.data_biz_id`` 走同一条路径，替代老的全局
    # ``settings.DEFAULT_BKDATA_BIZ_ID``；单租户默认部署下两者等价，多租户下前者会跟随 tenant。
    expected_biz_id = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001).data_biz_id
    assert brt.bkbase_table_id == f"{expected_biz_id}_legacy_rt"
    # bkbase_data_name 来源于实际 DataBusConfig.data_id_name，而不是 compose_bkdata_data_id_name 推测。
    assert brt.bkbase_data_name == databus_cfg.data_id_name


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_partial_reuse_only_rt(create_or_delete_records, bk_exporter_reuse_enabled, mocker):
    """只有 ResultTableConfig 有 legacy；binding / databus 走新建。"""
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="legacy_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    ctx = ExistingComponentContext.from_datalink(datalink)
    datalink.compose_configs(
        bk_biz_id=1001,
        data_source=ds,
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        existing_context=ctx,
    )

    assert ResultTableConfig.objects.get(data_link_name=datalink.data_link_name).name == "legacy_rt"
    binding_cfg = VMStorageBindingConfig.objects.get(data_link_name=datalink.data_link_name)
    databus_cfg = DataBusConfig.objects.get(data_link_name=datalink.data_link_name)
    assert binding_cfg.name == bkbase_vmrt_name
    assert databus_cfg.name == bkbase_vmrt_name
    assert ctx.leftover() == {}


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_reuse_off_uses_default_name(create_or_delete_records, mocker, settings):
    """灰度未开启时：即便 DB 里已有 legacy 记录，compose 仍然按 bkbase_vmrt_name 新建。

    使用 pytest-django 注入的 ``settings`` fixture（而不是直接改 ``django.conf.settings``
    全局对象）：用例结束时 fixture 会自动把该属性还原为测试开始前的值，避免污染后续
    用例 —— 如果忘记复原，后续依赖 ``DATA_LINK_COMPONENT_REUSE_STRATEGIES`` 的用例在
    不同执行顺序下会出现串扰式的随机失败。
    """
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="legacy_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()

    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}):
        datalink.apply_data_link(
            bk_biz_id=1001,
            data_source=ds,
            table_id=rt.table_id,
            storage_cluster_name="vm-plat",
        )

    names = set(ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name).values_list("name", flat=True))
    # 未开启灰度 -> 新建 bkbase_vmrt_name 记录；legacy 原样保留
    assert names == {"legacy_rt", bkbase_vmrt_name}


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_strict_leftover_raises_on_apply(create_or_delete_records, bk_exporter_reuse_enabled, mocker):
    """strict 策略下：claim 未命中的既有组件在 apply 收尾时抛 ComponentReuseError，
    且本次 compose 已经写入的 RT/Binding/DataBus 必须随外层事务一起回滚。
    """
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    # 造 table_id 不匹配的 ResultTableConfig -> claim 不会命中 -> leftover 非空
    ResultTableConfig.objects.create(
        name="orphan_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id="some_other_table",
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}):
        with pytest.raises(ComponentReuseError) as exc_info:
            datalink.apply_data_link(
                bk_biz_id=1001,
                data_source=ds,
                table_id=rt.table_id,
                storage_cluster_name="vm-plat",
            )

    assert ResultTableConfig in exc_info.value.violations
    assert exc_info.value.violations[ResultTableConfig][0].name == "orphan_rt"

    # 回滚回归：apply 失败时，compose 内部的 update_or_create 必须与 leftover 校验
    # 位于同一外层事务，三种组件的"本次新建副本"都不应落库。否则失败的 apply 会
    # 留下持久化脏数据，重复重试还会不断累积。
    assert not ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name, name=bkbase_vmrt_name).exists()
    assert not VMStorageBindingConfig.objects.filter(
        data_link_name=datalink.data_link_name, name=bkbase_vmrt_name
    ).exists()
    assert not DataBusConfig.objects.filter(data_link_name=datalink.data_link_name, name=bkbase_vmrt_name).exists()
    # 孤儿 RT 本来就是外层测试事务里的 arrange 数据，不受此次回滚影响。
    assert ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name, name="orphan_rt").exists()


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_keep_leftover_allows_apply(
    create_or_delete_records,
    bk_exporter_reuse_enabled,
    bk_exporter_leftover_policy_keep,
    mocker,
):
    """keep 策略下：未被 claim 的既有组件不会阻塞 apply。"""
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="orphan_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id="some_other_table",
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}) as mocked_apply:
        datalink.apply_data_link(
            bk_biz_id=1001,
            data_source=ds,
            table_id=rt.table_id,
            storage_cluster_name="vm-plat",
        )
    mocked_apply.assert_called_once()

    assert ResultTableConfig.objects.filter(name="orphan_rt", data_link_name=datalink.data_link_name).exists()
    assert ResultTableConfig.objects.filter(name=bkbase_vmrt_name, data_link_name=datalink.data_link_name).exists()


@pytest.mark.django_db(databases="__all__")
def test_bk_exporter_reuse_updates_vm_cluster_name(create_or_delete_records, bk_exporter_reuse_enabled, mocker):
    """复用既有 binding 时，vm_cluster_name 应跟随本次 apply 更新。"""
    datalink, ds, rt = _prepare_bk_exporter_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_EXPORTER_TIME_SERIES)

    VMStorageBindingConfig.objects.create(
        name="legacy_binding",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
        vm_cluster_name="vm-old",
        bkbase_result_table_name=bkbase_vmrt_name,
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    ctx = ExistingComponentContext.from_datalink(datalink)
    configs = datalink.compose_configs(
        bk_biz_id=1001,
        data_source=ds,
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        existing_context=ctx,
    )

    binding_cfg = VMStorageBindingConfig.objects.get(data_link_name=datalink.data_link_name)
    assert binding_cfg.name == "legacy_binding"
    assert binding_cfg.vm_cluster_name == "vm-plat"
    assert binding_cfg.bkbase_result_table_name == bkbase_vmrt_name
    assert ctx.leftover() == {}
    assert configs[1]["metadata"]["name"] == "legacy_binding"
    assert configs[1]["spec"]["storage"]["name"] == "vm-plat"


@pytest.mark.django_db(databases="__all__")
def test_compose_configs_falls_back_when_strategy_not_implemented(mocker, settings):
    """P2 回归：灰度开关被配成未接入复用的 strategy 时，不应把 existing_context 透传过去。

    历史问题：compose_configs 在判断灰度时只看 settings，未校验 compose 分支是否已经
    接受 ``existing_context`` 形参。任何只在 settings 里"误配"的 strategy 都会在
    ``method(existing_context=...)`` 这一步抛 ``TypeError: unexpected keyword argument``，
    把当前 apply 直接打挂。

    这里把 ``compose_standard_time_series_configs`` 替换成 MagicMock 观察调用形态，
    断言即使 ``BK_STANDARD_V2_TIME_SERIES`` 被塞进灰度 settings，switcher 也会走
    "不带 existing_context"的旧调用路径。依赖 pytest-django 的 ``settings`` fixture
    在用例退出时自动还原 ``DATA_LINK_COMPONENT_REUSE_STRATEGIES``，避免跨用例串扰。
    """
    # 选用 BK_STANDARD_V2_EVENT 作为"未接入 REUSE_ENABLED_STRATEGIES"的样例；
    # 一旦未来该 strategy 也完成复用接入，请换成仍未接入的 strategy 以保证本用例的
    # 回归语义（避免误把"接入之后"的行为断成"未接入"）。
    datalink = DataLink(
        data_link_name="dummy",
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_strategy=DataLink.BK_STANDARD_V2_EVENT,
    )

    # 故意把一个"尚未在 REUSE_ENABLED_STRATEGIES 里登记"的 strategy 开进灰度
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set(
        getattr(settings, "DATA_LINK_COMPONENT_REUSE_STRATEGIES", set())
    ) | {DataLink.BK_STANDARD_V2_EVENT}

    mocked_compose = mocker.patch.object(DataLink, "compose_custom_event_configs", return_value=[])
    # 故意传一个非 None 的 sentinel 来观察 switcher 是否透传；switcher 不应把它交给
    # compose_custom_event_configs（该 strategy 尚未登记进 REUSE_ENABLED_STRATEGIES）。
    sentinel_ctx = object()
    datalink.compose_configs(bk_biz_id=1, existing_context=sentinel_ctx)  # type: ignore[arg-type]

    mocked_compose.assert_called_once_with(bk_biz_id=1)
    # 关键断言：尽管上游传了 existing_context，switcher 发现当前 strategy 未接入
    # (不在 REUSE_ENABLED_STRATEGIES 里)，必须把它丢弃，不能透传给 compose 分支。
    assert "existing_context" not in mocked_compose.call_args.kwargs


# ============================================================
# DataLink 组件复用机制集成测试 -- bk_standard_v2_time_series
# ============================================================


@pytest.fixture
def bk_standard_v2_reuse_enabled(settings):
    """把 BK_STANDARD_V2_TIME_SERIES 纳入复用灰度；依赖 pytest-django settings fixture 自动复原。"""
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set(
        getattr(settings, "DATA_LINK_COMPONENT_REUSE_STRATEGIES", set())
    ) | {DataLink.BK_STANDARD_V2_TIME_SERIES}


def _prepare_bk_standard_v2_datalink(bk_biz_id: int = 1001):
    """准备 bk_standard_v2 场景下的 DataLink 实例以及对应 DataSource / ResultTable。

    复用 create_or_delete_records fixture 里的 bk_data_id=50010 样例数据（V2 场景）。
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")
    data_link_name = utils.compose_bkdata_data_id_name(ds.data_name, DataLink.BK_STANDARD_V2_TIME_SERIES)
    datalink = DataLink.objects.create(
        data_link_name=data_link_name,
        namespace="bkmonitor",
        bk_tenant_id="system",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
    )
    return datalink, ds, rt


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_reuse_three_legacy_components(create_or_delete_records, bk_standard_v2_reuse_enabled, mocker):
    """V2 链路三个组件都命中 legacy 时，compose 应复用 name，不新增记录。"""
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name, DataLink.BK_STANDARD_V2_TIME_SERIES)
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    VMStorageBindingConfig.objects.create(
        name="legacy_v2_binding",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
        vm_cluster_name="vm-plat",
        bkbase_result_table_name=bkbase_vmrt_name,
    )
    DataBusConfig.objects.create(
        name="legacy_v2_databus",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name=bkbase_data_name,
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    ctx = ExistingComponentContext.from_datalink(datalink)
    configs = datalink.compose_configs(
        bk_biz_id=1001,
        data_source=ds,
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        existing_context=ctx,
    )

    # 没有新增：每个 kind 在 DB 里依旧只保留 legacy 记录
    assert ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert VMStorageBindingConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert DataBusConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1

    rt_cfg = ResultTableConfig.objects.get(data_link_name=datalink.data_link_name)
    binding_cfg = VMStorageBindingConfig.objects.get(data_link_name=datalink.data_link_name)
    databus_cfg = DataBusConfig.objects.get(data_link_name=datalink.data_link_name)
    assert rt_cfg.name == "legacy_v2_rt"
    assert binding_cfg.name == "legacy_v2_binding"
    assert databus_cfg.name == "legacy_v2_databus"
    # sink_names 联动 binding 的 legacy name，而非 bkbase_vmrt_name
    assert databus_cfg.sink_names == [f"{DataLinkKind.VMSTORAGEBINDING.value}:legacy_v2_binding"]
    # binding.bkbase_result_table_name 必须同步为最终 RT name，不能残留历史的 bkbase_vmrt_name
    assert binding_cfg.bkbase_result_table_name == "legacy_v2_rt"

    # leftover 为空 -- 三条全部 claim 完毕
    assert ctx.leftover() == {}

    # payload 中 metadata.name 与 databus sink name 均联动 legacy
    assert configs[0]["metadata"]["name"] == "legacy_v2_rt"
    assert configs[1]["metadata"]["name"] == "legacy_v2_binding"
    assert configs[2]["metadata"]["name"] == "legacy_v2_databus"
    assert configs[2]["spec"]["sinks"][0]["name"] == "legacy_v2_binding"
    # P1 关键：binding.spec.data.name 必须指向真正存在的 RT（"legacy_v2_rt"），
    # 不能回退到 binding 自身的 name。
    assert configs[1]["spec"]["data"]["name"] == "legacy_v2_rt"

    # P1 回归：sync_metadata 读 ResultTableConfig / DataBusConfig 实名回填 BkBaseResultTable。
    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_name="vm-plat")
    from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
    from metadata.models.bkdata.result_table import BkBaseResultTable

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.bkbase_rt_name == "legacy_v2_rt"
    expected_biz_id = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001).data_biz_id
    assert brt.bkbase_table_id == f"{expected_biz_id}_legacy_v2_rt"
    assert brt.bkbase_data_name == databus_cfg.data_id_name


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_sync_metadata_respects_tenant_biz_id(
    create_or_delete_records, bk_standard_v2_reuse_enabled, mocker
):
    """多租户下 sync_metadata 拼 bkbase_table_id 的前缀必须跟随 tenant 的 data_biz_id，
    而不是全局 settings.DEFAULT_BKDATA_BIZ_ID。
    """
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    DataBusConfig.objects.create(
        name="legacy_v2_databus",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name="tenant_custom_data_name",
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    # 关键：patch 掉 ResultTableConfig.datalink_biz_ids 所依赖的 get_tenant_datalink_biz_id，
    # 让它返回一个非默认的 data_biz_id。sync_metadata 必须跟着这个值拼前缀。
    from bkmonitor.utils.tenant import DatalinkBizIds

    mocker.patch(
        "metadata.models.data_link.data_link_configs.get_tenant_datalink_biz_id",
        return_value=DatalinkBizIds(label_biz_id=1001, data_biz_id=9527),
    )

    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_name="vm-plat")

    from metadata.models.bkdata.result_table import BkBaseResultTable

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.bkbase_rt_name == "legacy_v2_rt"
    # 前缀跟随 tenant 粒度的 data_biz_id，而不是全局 DEFAULT_BKDATA_BIZ_ID。
    assert brt.bkbase_table_id == "9527_legacy_v2_rt"
    assert brt.bkbase_data_name == "tenant_custom_data_name"


@pytest.mark.django_db(databases="__all__")
def test_sync_metadata_records_partial_bkbase_result_table_when_databus_missing(create_or_delete_records):
    """DataBusConfig 缺失时，sync_metadata 仍应尽量回填 ResultTableConfig 中已知的实名信息。"""
    datalink, _, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="partial_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_name="vm-plat")

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.monitor_table_id == rt.table_id
    assert brt.bkbase_rt_name == "partial_rt"
    assert brt.bkbase_table_id == f"{settings.DEFAULT_BKDATA_BIZ_ID}_partial_rt"
    assert brt.bkbase_data_name is None


@pytest.mark.django_db(databases="__all__")
def test_sync_metadata_uses_filtered_latest_config_when_duplicates_exist(create_or_delete_records):
    """存在重复配置时不直接放弃，选择最近更新的一条继续回填 BkBaseResultTable。"""
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="old_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    ResultTableConfig.objects.create(
        name="latest_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    DataBusConfig.objects.create(
        name="old_databus",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name="old_data_name",
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )
    DataBusConfig.objects.create(
        name="latest_databus",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name="latest_data_name",
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )

    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_name="vm-plat")

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.bkbase_rt_name == "latest_rt"
    assert brt.bkbase_table_id == f"{settings.DEFAULT_BKDATA_BIZ_ID}_latest_rt"
    assert brt.bkbase_data_name == "latest_data_name"


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_result_table_option_enables_reuse(create_or_delete_records, settings, mocker):
    """RT option=true 时，即使 strategy 灰度关闭，单表 apply 也应进入复用逻辑。"""
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name, DataLink.BK_STANDARD_V2_TIME_SERIES)
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
    models.ResultTableOption.create_option(
        table_id=rt.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_DATA_LINK_COMPONENT_REUSE,
        value=True,
        creator="pytest",
        bk_tenant_id=datalink.bk_tenant_id,
    )

    ResultTableConfig.objects.create(
        name="legacy_v2_rt_by_option",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )
    VMStorageBindingConfig.objects.create(
        name="legacy_v2_binding_by_option",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
        vm_cluster_name="vm-plat",
        bkbase_result_table_name=bkbase_vmrt_name,
    )
    DataBusConfig.objects.create(
        name="legacy_v2_databus_by_option",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        data_id_name=bkbase_data_name,
        bk_data_id=ds.bk_data_id,
        sink_names=[],
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}) as apply_mock:
        datalink.apply_data_link(
            bk_biz_id=1001,
            data_source=ds,
            table_id=rt.table_id,
            storage_cluster_name="vm-plat",
        )

    configs = apply_mock.call_args.args[0]
    assert ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert VMStorageBindingConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert DataBusConfig.objects.filter(data_link_name=datalink.data_link_name).count() == 1
    assert configs[0]["metadata"]["name"] == "legacy_v2_rt_by_option"
    assert configs[1]["metadata"]["name"] == "legacy_v2_binding_by_option"
    assert configs[1]["spec"]["data"]["name"] == "legacy_v2_rt_by_option"
    assert configs[2]["metadata"]["name"] == "legacy_v2_databus_by_option"
    assert configs[2]["spec"]["sinks"][0]["name"] == "legacy_v2_binding_by_option"


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_reuse_off_uses_default_name(create_or_delete_records, mocker, settings):
    """V2 链路灰度未开启时：即便 DB 里已有 legacy 记录，compose 仍然按 bkbase_vmrt_name 新建。"""
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()

    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}):
        datalink.apply_data_link(
            bk_biz_id=1001,
            data_source=ds,
            table_id=rt.table_id,
            storage_cluster_name="vm-plat",
        )

    names = set(ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name).values_list("name", flat=True))
    # 未开启灰度 -> 新建 bkbase_vmrt_name 记录；legacy 原样保留
    assert names == {"legacy_v2_rt", bkbase_vmrt_name}


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_strict_leftover_raises_on_apply(create_or_delete_records, bk_standard_v2_reuse_enabled, mocker):
    """V2 链路 strict 策略下：claim 未命中的既有组件在 apply 收尾时抛 ComponentReuseError，
    且本次 compose 已经写入的 RT/Binding/DataBus 必须随外层事务一起回滚。
    """
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)

    # 造 table_id 不匹配的 ResultTableConfig -> claim 不会命中 -> leftover 非空
    ResultTableConfig.objects.create(
        name="orphan_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id="some_other_table",
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    with patch.object(DataLink, "apply_data_link_with_retry", return_value={"status": "success"}):
        with pytest.raises(ComponentReuseError) as exc_info:
            datalink.apply_data_link(
                bk_biz_id=1001,
                data_source=ds,
                table_id=rt.table_id,
                storage_cluster_name="vm-plat",
            )

    assert ResultTableConfig in exc_info.value.violations
    assert exc_info.value.violations[ResultTableConfig][0].name == "orphan_v2_rt"

    # 回滚回归：apply 失败时，compose 内部的 update_or_create 必须与 leftover 校验
    # 位于同一外层事务，本次尝试写入的三种组件（bkbase_vmrt_name）都应当被回滚。
    assert not ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name, name=bkbase_vmrt_name).exists()
    assert not VMStorageBindingConfig.objects.filter(
        data_link_name=datalink.data_link_name, name=bkbase_vmrt_name
    ).exists()
    assert not DataBusConfig.objects.filter(data_link_name=datalink.data_link_name, name=bkbase_vmrt_name).exists()
    # 孤儿 RT 本来就是外层测试事务里的 arrange 数据，不受此次回滚影响。
    assert ResultTableConfig.objects.filter(data_link_name=datalink.data_link_name, name="orphan_v2_rt").exists()


@pytest.mark.django_db(databases="__all__")
def test_bk_standard_v2_reuse_updates_vm_cluster_name(create_or_delete_records, bk_standard_v2_reuse_enabled, mocker):
    """V2 链路复用既有 binding 时，vm_cluster_name 应跟随本次 apply 更新。"""
    datalink, ds, rt = _prepare_bk_standard_v2_datalink()
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, DataLink.BK_STANDARD_V2_TIME_SERIES)

    VMStorageBindingConfig.objects.create(
        name="legacy_v2_binding",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
        vm_cluster_name="vm-old",
        bkbase_result_table_name=bkbase_vmrt_name,
    )

    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)

    ctx = ExistingComponentContext.from_datalink(datalink)
    configs = datalink.compose_configs(
        bk_biz_id=1001,
        data_source=ds,
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        existing_context=ctx,
    )

    binding_cfg = VMStorageBindingConfig.objects.get(data_link_name=datalink.data_link_name)
    assert binding_cfg.name == "legacy_v2_binding"
    assert binding_cfg.vm_cluster_name == "vm-plat"
    assert binding_cfg.bkbase_result_table_name == bkbase_vmrt_name
    assert ctx.leftover() == {}
    assert configs[1]["metadata"]["name"] == "legacy_v2_binding"
    assert configs[1]["spec"]["storage"]["name"] == "vm-plat"


@pytest.mark.django_db(databases="__all__")
def test_sync_metadata_supports_storage_cluster_id_lookup(create_or_delete_records):
    """传入 storage_cluster_id 时，sync_metadata 应反查 ClusterInfo 得到对应 storage_type。"""
    datalink, _, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    es_cluster = models.ClusterInfo.objects.get(cluster_name="es_default")
    datalink.sync_metadata(table_id=rt.table_id, storage_cluster_id=es_cluster.cluster_id)

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    assert brt.storage_cluster_id == es_cluster.cluster_id
    assert brt.storage_type == models.ClusterInfo.TYPE_ES
    assert brt.bkbase_rt_name == "legacy_v2_rt"


@pytest.mark.django_db(databases="__all__")
def test_sync_metadata_supports_cluster_name_with_storage_type(create_or_delete_records):
    """传入 storage_cluster_name + storage_type 时，按 (cluster_name, cluster_type) 命中 ClusterInfo。"""
    datalink, _, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    datalink.sync_metadata(
        table_id=rt.table_id,
        storage_cluster_name="es_default",
        storage_type=models.ClusterInfo.TYPE_ES,
    )

    brt = BkBaseResultTable.objects.get(data_link_name=datalink.data_link_name)
    es_cluster = models.ClusterInfo.objects.get(cluster_name="es_default")
    assert brt.storage_cluster_id == es_cluster.cluster_id
    assert brt.storage_type == models.ClusterInfo.TYPE_ES


@pytest.mark.django_db(databases="__all__")
def test_sync_metadata_storage_type_mismatch_skips(create_or_delete_records):
    """cluster_name 命中但 cluster_type 不匹配时，应判为 cluster 不存在并跳过回填。"""
    datalink, _, rt = _prepare_bk_standard_v2_datalink()

    ResultTableConfig.objects.create(
        name="legacy_v2_rt",
        namespace=datalink.namespace,
        bk_tenant_id=datalink.bk_tenant_id,
        data_link_name=datalink.data_link_name,
        bk_biz_id=1001,
        table_id=rt.table_id,
    )

    # vm-plat 是 VM 集群，给出错误的 storage_type=ES 时 sync_metadata 应静默返回。
    datalink.sync_metadata(
        table_id=rt.table_id,
        storage_cluster_name="vm-plat",
        storage_type=models.ClusterInfo.TYPE_ES,
    )

    assert not BkBaseResultTable.objects.filter(data_link_name=datalink.data_link_name).exists()
