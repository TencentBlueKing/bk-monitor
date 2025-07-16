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
from django.conf import settings

from metadata import models
from metadata.models.data_link import utils
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
    DataIdConfig,
    VMResultTableConfig,
    VMStorageBindingConfig,
)
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    data_source = models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="data_link_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    data_source.delete()
    result_table.delete()


@pytest.mark.django_db(databases="__all__")
def test_compose_data_id_config(create_or_delete_records):
    """
    测试DataIdConfig能否正确生成
    """

    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False
    ds = models.DataSource.objects.get(bk_data_id=50010)
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    expected_config = (
        '{"kind":"DataId","metadata":{"name":"bkm_data_link_test","namespace":"bkmonitor","labels":{'
        '"bk_biz_id":"111"}},"spec":{"alias":"bkm_data_link_test","bizId":0,'
        '"description":"bkm_data_link_test","maintainers":["admin"]}}'
    )

    data_id_config_ins, _ = DataIdConfig.objects.get_or_create(
        name=bkbase_data_name, namespace="bkmonitor", bk_biz_id=111
    )
    content = data_id_config_ins.compose_config()
    assert json.dumps(content) == expected_config

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True
    expected_config = (
        '{"kind":"DataId","metadata":{"name":"bkm_data_link_test","namespace":"bkmonitor",'
        '"tenant":"system","labels":{"bk_biz_id":"111"}},"spec":{"alias":"bkm_data_link_test",'
        '"bizId":0,"description":"bkm_data_link_test","maintainers":["admin"]}}'
    )

    content = data_id_config_ins.compose_config()
    assert json.dumps(content) == expected_config


@pytest.mark.django_db(databases="__all__")
def test_compose_vm_result_table_config(create_or_delete_records):
    """
    测试VMResultTableConfig能否正确生成
    """
    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False

    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    expect_config = (
        '{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"111"}},"spec":{'
        '"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}}'
    )

    vm_table_id_ins, _ = VMResultTableConfig.objects.get_or_create(
        name=bkbase_vmrt_name, data_link_name=bkbase_data_name, namespace="bkmonitor", bk_biz_id=111
    )
    content = vm_table_id_ins.compose_config()
    assert json.dumps(content) == expect_config

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True
    expect_config = (
        '{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","tenant":"system","labels":{"bk_biz_id":"111"}},'
        '"spec":{"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,"dataType":"metric",'
        '"description":"bkm_1001_bkmonitor_time_series_50010","maintainers":["admin"]}}'
    )

    content = vm_table_id_ins.compose_config()
    assert json.dumps(content) == expect_config


@pytest.mark.django_db(databases="__all__")
def test_compose_vm_storage_binding_config(create_or_delete_records):
    """
    测试VMStorageBindingConfig能否正确生成
    """
    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    vm_storage_ins, _ = VMStorageBindingConfig.objects.get_or_create(
        name=bkbase_vmrt_name,
        vm_cluster_name="vm-plat",
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        bk_biz_id=111,
    )

    expect_config = (
        '{"kind":"VmStorageBinding","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"111"}},"spec":{"data":{"kind":"ResultTable",'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},"maintainers":['
        '"admin"],"storage":{"kind":"VmStorage","name":"vm-plat","namespace":"bkmonitor"}}}'
    )

    content = vm_storage_ins.compose_config()
    assert json.dumps(content) == expect_config

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True

    expect_config = (
        '{"kind":"VmStorageBinding","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"tenant":"system","namespace":"bkmonitor","labels":{"bk_biz_id":"111"}},"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","tenant":"system",'
        '"namespace":"bkmonitor"},"maintainers":["admin"],"storage":{"kind":"VmStorage",'
        '"name":"vm-plat","tenant":"system","namespace":"bkmonitor"}}}'
    )

    content = vm_storage_ins.compose_config()
    assert json.dumps(content) == expect_config


@pytest.mark.django_db(databases="__all__")
def test_compose_data_bus_config(create_or_delete_records):
    """
    测试DataBusConfig能否正确生成
    """
    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    sinks = [
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "name": bkbase_vmrt_name,
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
    ]

    expect_config = (
        '{"kind":"Databus","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"111"}},"spec":{"maintainers":["admin"],"sinks":[{'
        '"kind":"VmStorageBinding","name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor"}],"sources":[{"kind":"DataId","name":"bkm_data_link_test",'
        '"namespace":"bkmonitor"}],"transforms":[{"kind":"PreDefinedLogic","name":"log_to_metric",'
        '"format":"bkmonitor_standard_v2"}]}}'
    )

    data_bus_ins, _ = DataBusConfig.objects.get_or_create(
        name=bkbase_vmrt_name,
        data_id_name=bkbase_data_name,
        data_link_name=bkbase_data_name,
        namespace="bkmonitor",
        bk_biz_id=111,
    )

    content = data_bus_ins.compose_config(sinks)
    assert json.dumps(content) == expect_config

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True

    # 生成sink的时候,需要加上tenant
    sinks = [
        {
            "kind": DataLinkKind.VMSTORAGEBINDING.value,
            "name": bkbase_vmrt_name,
            "tenant": "system",
            "namespace": settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
        }
    ]

    expect_config = (
        '{"kind":"Databus","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010","tenant":"system",'
        '"namespace":"bkmonitor","labels":{"bk_biz_id":"111"}},"spec":{"maintainers":["admin"],'
        '"sinks":[{"kind":"VmStorageBinding","name":"bkm_1001_bkmonitor_time_series_50010",'
        '"tenant":"system","namespace":"bkmonitor"}],"sources":[{"kind":"DataId",'
        '"name":"bkm_data_link_test","tenant":"system","namespace":"bkmonitor"}],"transforms":[{'
        '"kind":"PreDefinedLogic","name":"log_to_metric","format":"bkmonitor_standard_v2"}]}}'
    )

    content = data_bus_ins.compose_config(sinks)
    assert json.dumps(content) == expect_config


@pytest.mark.django_db(databases="__all__")
def test_compose_single_conditional_sink_config(create_or_delete_records):
    """
    测试单集群ConditionalSinkConfig能否正确生成
    """
    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_data_name == "fed_bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010_fed"
    conditions = [
        {
            "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
            "sinks": [
                {"kind": "VmStorageBinding", "name": "bkm_1001_bkmonitor_time_series_50001", "namespace": "bkmonitor"}
            ],
        },
    ]

    expected = json.dumps(
        {
            "kind": "ConditionalSink",
            "metadata": {
                "namespace": "bkmonitor",
                "name": "bkm_1001_bkmonitor_time_series_50010_fed",
                "labels": {"bk_biz_id": "111"},
            },
            "spec": {
                "conditions": [
                    {
                        "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
                        "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "bkm_1001_bkmonitor_time_series_50001",
                                "namespace": "bkmonitor",
                            }
                        ],
                    },
                ]
            },
        }
    )

    vm_conditional_ins, _ = models.ConditionalSinkConfig.objects.get_or_create(
        name=bkbase_vmrt_name, data_link_name=bkbase_data_name, namespace="bkmonitor", bk_biz_id=111
    )
    content = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
    assert json.dumps(content) == expected

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True

    expected = (
        '{"kind":"ConditionalSink","metadata":{"namespace":"bkmonitor",'
        '"name":"bkm_1001_bkmonitor_time_series_50010_fed","tenant":"system","labels":{"bk_biz_id":"111"}},'
        '"spec":{"conditions":[{"match_labels":[{"name":"namespace","any":["testns1","testns2","testns3"]}],'
        '"relabels":[{"name":"bcs_cluster_id","value":"BCS-K8S-10001"}],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50001","tenant":"system","namespace":"bkmonitor"}]}]}}'
    )

    conditions = [
        {
            "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
            "sinks": [
                {
                    "kind": "VmStorageBinding",
                    "name": "bkm_1001_bkmonitor_time_series_50001",
                    "tenant": "system",
                    "namespace": "bkmonitor",
                }
            ],
        },
    ]

    content = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
    assert json.dumps(content) == expected


@pytest.mark.django_db(databases="__all__")
def test_compose_multi_conditional_sink_config(create_or_delete_records):
    """
    测试多集群ConditionalSinkConfig能否正确生成
    """
    # 单租户模式
    settings.ENABLE_MULTI_TENANT_MODE = False
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_data_name == "fed_bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id, models.DataLink.BCS_FEDERAL_SUBSET_TIME_SERIES)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010_fed"

    conditions = [
        {
            "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
            "sinks": [
                {"kind": "VmStorageBinding", "name": "bkm_1001_bkmonitor_time_series_50001", "namespace": "bkmonitor"}
            ],
        },
        {
            "match_labels": [{"name": "namespace", "any": ["testns4", "testns5", "testns6"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10002"}],
            "sinks": [
                {"kind": "VmStorageBinding", "name": "bkm_1001_bkmonitor_time_series_50002", "namespace": "bkmonitor"}
            ],
        },
    ]

    expected = json.dumps(
        {
            "kind": "ConditionalSink",
            "metadata": {
                "namespace": "bkmonitor",
                "name": "bkm_1001_bkmonitor_time_series_50010_fed",
                "labels": {"bk_biz_id": "111"},
            },
            "spec": {
                "conditions": [
                    {
                        "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
                        "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "bkm_1001_bkmonitor_time_series_50001",
                                "namespace": "bkmonitor",
                            }
                        ],
                    },
                    {
                        "match_labels": [{"name": "namespace", "any": ["testns4", "testns5", "testns6"]}],
                        "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10002"}],
                        "sinks": [
                            {
                                "kind": "VmStorageBinding",
                                "name": "bkm_1001_bkmonitor_time_series_50002",
                                "namespace": "bkmonitor",
                            }
                        ],
                    },
                ]
            },
        }
    )

    vm_conditional_ins, _ = models.ConditionalSinkConfig.objects.get_or_create(
        name=bkbase_vmrt_name, data_link_name=bkbase_data_name, namespace="bkmonitor", bk_biz_id=111
    )
    content = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
    assert json.dumps(content) == expected

    # 多租户模式
    settings.ENABLE_MULTI_TENANT_MODE = True

    expected = (
        '{"kind":"ConditionalSink","metadata":{"namespace":"bkmonitor",'
        '"name":"bkm_1001_bkmonitor_time_series_50010_fed","tenant":"system","labels":{"bk_biz_id":"111"}},'
        '"spec":{"conditions":[{"match_labels":[{"name":"namespace","any":["testns1","testns2","testns3"]}],'
        '"relabels":[{"name":"bcs_cluster_id","value":"BCS-K8S-10001"}],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50001","tenant":"system","namespace":"bkmonitor"}]},'
        '{"match_labels":[{"name":"namespace","any":["testns4","testns5","testns6"]}],"relabels":[{'
        '"name":"bcs_cluster_id","value":"BCS-K8S-10002"}],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50002","tenant":"system","namespace":"bkmonitor"}]}]}}'
    )

    conditions = [
        {
            "match_labels": [{"name": "namespace", "any": ["testns1", "testns2", "testns3"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10001"}],
            "sinks": [
                {
                    "kind": "VmStorageBinding",
                    "name": "bkm_1001_bkmonitor_time_series_50001",
                    "tenant": "system",
                    "namespace": "bkmonitor",
                }
            ],
        },
        {
            "match_labels": [{"name": "namespace", "any": ["testns4", "testns5", "testns6"]}],
            "relabels": [{"name": "bcs_cluster_id", "value": "BCS-K8S-10002"}],
            "sinks": [
                {
                    "kind": "VmStorageBinding",
                    "name": "bkm_1001_bkmonitor_time_series_50002",
                    "tenant": "system",
                    "namespace": "bkmonitor",
                }
            ],
        },
    ]

    content = vm_conditional_ins.compose_conditional_sink_config(conditions=conditions)
    assert json.dumps(content) == expected
