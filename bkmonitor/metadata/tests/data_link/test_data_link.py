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
from unittest.mock import patch

import pytest
from django.db.utils import IntegrityError
from tenacity import RetryError

from core.errors.api import BKAPIError
from metadata import models
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.data_link import DataLink, utils
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import (
    DataBusConfig,
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


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_Standard_V2_Time_Series_compose_configs(create_or_delete_records):
    """
    测试单指标单表类型链路是否能正确生成资源配置
    需要测试：能否正确生成配置，是否正确创建了VMResultTableConfig、VMStorageBindingConfig、DataBusConfig三个实例
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id='1001_bkmonitor_time_series_50010.__default__')

    # 测试参数是否正确组装
    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    assert bkbase_data_name == "bkm_data_link_test"

    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)
    assert bkbase_vmrt_name == "bkm_1001_bkmonitor_time_series_50010"

    # 预期的配置
    expected_configs = (
        '[{"kind":"ResultTable","metadata":{"name":"bkm_1001_bkmonitor_time_series_50010",'
        '"namespace":"bkmonitor"},"spec":{"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}},{"kind":"VmStorageBinding","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"maintainers":["admin"],"storage":{"kind":"VmStorage","name":"vm-plat",'
        '"namespace":"bkmonitor"}}},{"kind":"Databus","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
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

    configs = data_link_ins.compose_configs(data_source=ds, table_id=rt.table_id, vm_cluster_name='vm-plat')
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
    assert vm_storage_binding_ins.vm_cluster_name == 'vm-plat'

    data_bus_ins = DataBusConfig.objects.get(name=bkbase_vmrt_name)
    assert data_bus_ins.kind == DataLinkKind.DATABUS.value
    assert data_bus_ins.name == bkbase_vmrt_name
    assert data_bus_ins.data_link_name == bkbase_data_name
    assert data_bus_ins.data_id_name == bkbase_data_name
    assert data_bus_ins.namespace == "bkmonitor"


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_compose_configs_transaction_failure(create_or_delete_records):
    """
    测试在 compose_configs 操作中途发生错误时，事务是否能正确回滚
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id='1001_bkmonitor_time_series_50010.__default__')

    bkbase_data_name = utils.compose_bkdata_data_id_name(ds.data_name)
    bkbase_vmrt_name = utils.compose_bkdata_table_id(rt.table_id)

    # 模拟 VMResultTableConfig 的 get_or_create 操作抛出异常
    with patch(
        'metadata.models.data_link.data_link_configs.VMResultTableConfig.objects.get_or_create',
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
            data_link_ins.compose_configs(data_source=ds, table_id=rt.table_id, vm_cluster_name='vm-plat')

    # 确保由于事务回滚，没有任何配置实例对象被创建
    assert DataLink.objects.filter(data_link_name=bkbase_data_name).exists()
    assert not VMResultTableConfig.objects.filter(name=bkbase_vmrt_name).exists()
    assert not VMStorageBindingConfig.objects.filter(name=bkbase_vmrt_name).exists()
    assert not DataBusConfig.objects.filter(name=bkbase_vmrt_name).exists()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_Standard_V2_Time_Series_apply_data_link(create_or_delete_records):
    """
    测试完整流程：单指标单表套餐apply_data_link是否如期执行
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id='1001_bkmonitor_time_series_50010.__default__')

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
        '"namespace":"bkmonitor"},"spec":{"alias":"bkm_1001_bkmonitor_time_series_50010","bizId":0,'
        '"dataType":"metric","description":"bkm_1001_bkmonitor_time_series_50010","maintainers":['
        '"admin"]}},{"kind":"VmStorageBinding","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},"spec":{"data":{'
        '"kind":"ResultTable","name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"maintainers":["admin"],"storage":{"kind":"VmStorage","name":"vm-plat",'
        '"namespace":"bkmonitor"}}},{"kind":"Databus","metadata":{'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"},'
        '"spec":{"maintainers":["admin"],"sinks":[{"kind":"VmStorageBinding",'
        '"name":"bkm_1001_bkmonitor_time_series_50010","namespace":"bkmonitor"}],"sources":[{'
        '"kind":"DataId","name":"bkm_data_link_test","namespace":"bkmonitor"}],"transforms":[{'
        '"kind":"PreDefinedLogic","name":"log_to_metric","format":"bkmonitor_standard_v2"}]}}]'
    )

    with patch.object(DataLink, 'compose_configs', return_value=expected_configs) as mock_compose_configs, patch.object(
        DataLink, 'apply_data_link_with_retry', return_value={'status': 'success'}
    ) as mock_apply_with_retry:  # noqa
        data_link_ins.apply_data_link(data_source=ds, table_id=rt.table_id, vm_cluster_name='vm-plat')

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


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_Standard_V2_Time_Series_apply_data_link_with_failure(create_or_delete_records):
    """
    测试完整流程：单指标单表套餐apply_data_link出现异常时，是否能够如期工作
    """
    ds = models.DataSource.objects.get(bk_data_id=50010)
    rt = models.ResultTable.objects.get(table_id='1001_bkmonitor_time_series_50010.__default__')

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
    with patch.object(DataLink, 'compose_configs', return_value="") as mock_compose_configs, patch.object(
        DataLink, 'apply_data_link_with_retry', side_effect=BKAPIError('apply_data_link_with_retry')
    ) as mock_apply_with_retry:  # noqa
        with pytest.raises(BKAPIError):
            data_link_ins.apply_data_link(data_source=ds, table_id=rt.table_id, vm_cluster_name='vm-plat')

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
