"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from rest_framework.exceptions import ValidationError

from metadata import models
from metadata.resources.vm import NotifyDataLinkVmChange, QueryMetaInfoByVmrt, QueryVmRtBySpace, ModifyClusterByVmrts
from metadata.tests.common_utils import consul_client

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture
def create_or_delete_records(mocker):
    models.ClusterInfo.objects.create(
        domain_name="test1.vm.db",
        cluster_name="test1",
        cluster_id=12345,
        cluster_type=models.ClusterInfo.TYPE_VM,
        port=1111,
        is_default_cluster=False,
        bk_tenant_id="system",
    )
    models.ClusterInfo.objects.create(
        domain_name="test2.vm.db",
        cluster_name="test2",
        cluster_type=models.ClusterInfo.TYPE_VM,
        cluster_id=12346,
        port=1111,
        is_default_cluster=False,
        bk_tenant_id="system",
    )
    models.AccessVMRecord.objects.create(
        vm_result_table_id="1001_test_vm",
        vm_cluster_id=11111111,
        bk_base_data_id=11111123,
        result_table_id="1001_bkmonitor_time_series_60010.__default__",
        bk_tenant_id="system",
    )
    models.DataSource.objects.create(
        bk_data_id=60010,
        data_name="bcs_BCS-K8S-10001_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="system",
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60010.__default__", bk_biz_id=12345, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60010.__default__", bk_data_id=60010
    )
    models.AccessVMRecord.objects.create(
        vm_result_table_id="1001_test_vm_2",
        vm_cluster_id=11111111,
        bk_base_data_id=11111123,
        result_table_id="1001_bkmonitor_time_series_60011.__default__",
        bk_tenant_id="system",
    )
    models.DataSource.objects.create(
        bk_data_id=60011,
        data_name="bcs_BCS-K8S-10002_k8s_metric",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        bk_tenant_id="system",
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60011.__default__", bk_biz_id=12345, is_custom_table=False
    )
    models.DataSourceResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_60011.__default__", bk_data_id=60011
    )
    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.AccessVMRecord.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=60010).delete()
    models.DataSource.objects.filter(bk_data_id=60010).delete()
    models.ResultTable.objects.filter(table_id="1001_bkmonitor_time_series_60010.__default__").delete()
    models.DataSourceResultTable.objects.filter(bk_data_id=60011).delete()
    models.DataSource.objects.filter(bk_data_id=60011).delete()
    models.ResultTable.objects.filter(table_id="1001_bkmonitor_time_series_60011.__default__").delete()


@pytest.mark.django_db(databases="__all__")
def test_notify_data_link_vm_change(create_or_delete_records):
    NotifyDataLinkVmChange().request(cluster_name="test1", vmrt="1001_test_vm")
    record = models.AccessVMRecord.objects.get(vm_result_table_id="1001_test_vm")
    assert record.vm_cluster_id == 12345

    with pytest.raises(ValidationError):
        NotifyDataLinkVmChange().request(cluster_name="test1", vmrt="1002_test_vm")


@pytest.mark.django_db(databases="__all__")
def test_query_vm_rt_without_plugin():
    params = {"space_type": "bkcc", "space_id": "0"}
    with pytest.raises(ValidationError):
        resp = QueryVmRtBySpace().request(params)
        # 如果 request 没有抛出 ValidationError，assert 失败
        assert resp


@pytest.mark.django_db(databases="__all__")
def test_query_meta_info_by_vmrt(create_or_delete_records):
    data = QueryMetaInfoByVmrt().request(vmrt="1001_test_vm")
    assert data["bk_data_id"] == 60010
    assert data["bk_biz_id"] == 12345
    assert data["monitor_table_id"] == "1001_bkmonitor_time_series_60010.__default__"
    assert data["data_name"] == "bcs_BCS-K8S-10001_k8s_metric"
    assert data["vm_result_table_id"] == "1001_test_vm"


@pytest.mark.django_db(databases="__all__")
def test_modify_cluster_by_vmrts(create_or_delete_records):
    params = {"vmrts": ["1001_test_vm", "1001_test_vm_2"], "cluster_name": "test2"}
    ModifyClusterByVmrts().request(params)

    record = models.AccessVMRecord.objects.get(vm_result_table_id="1001_test_vm")
    assert record.vm_cluster_id == 12346
    record = models.AccessVMRecord.objects.get(vm_result_table_id="1001_test_vm_2")
    assert record.vm_cluster_id == 12346
