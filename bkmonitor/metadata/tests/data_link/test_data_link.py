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

    with (
        patch.object(DataLink, "compose_configs", return_value=expected_configs) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
    ):  # noqa
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
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
def test_component_id(create_or_delete_records, mocker):
    """
    测试component_id是否正确组装
    """
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

    DataBusConfig.objects.create(
        bk_tenant_id="system",
        bk_biz_id=1001,
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        name=bkbase_vmrt_name,
    )

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

    with (
        patch.object(DataLink, "compose_configs", return_value=None) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        data_link_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001)
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
        # 验证 compose_configs 被调用并返回预期的配置
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

    with (
        patch.object(DataLink, "compose_configs", return_value=None) as mock_compose_configs,
        patch.object(
            DataLink, "apply_data_link_with_retry", return_value={"status": "success"}
        ) as mock_apply_with_retry,
        patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2),
    ):  # noqa
        data_link_biz_ids = get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=1001)
        create_bkbase_data_link(
            bk_biz_id=1001, data_source=ds, monitor_table_id=rt.table_id, storage_cluster_name="vm-plat"
        )
        # 验证 compose_configs 被调用并返回预期的配置
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
