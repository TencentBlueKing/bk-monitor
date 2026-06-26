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

from metadata import models
from metadata.health_check import get_bkdata_status
from metadata.task.tasks import _refresh_data_link_status


@pytest.fixture
def create_or_delete_records(mocker):
    models.BkBaseResultTable.objects.create(
        data_link_name="bkm_test_data_link",
        bkbase_data_name="bkm_test_data_link",
        storage_type="victoria_metrics",
        monitor_table_id="1001_bkm_time_series_test.__default__",
        storage_cluster_id=11,
        status="creating",
        bkbase_table_id="2_bkm_1001_bkm_time_series_test",
        bkbase_rt_name="bkm_test_rt",
    )

    models.DataLink.objects.create(
        data_link_name="bkm_test_data_link",
        namespace="bkmonitor",
        data_link_strategy="bk_standard_v2_time_series",
        table_ids=["1001_bkm_time_series_test.__default__"],
    )

    models.DataIdConfig.objects.create(namespace="bkmonitor", name="bkm_test_data_link", bk_biz_id=1001)
    models.ResultTableConfig.objects.create(
        namespace="bkmonitor",
        status="creating",
        data_link_name="bkm_test_data_link",
        name="bkm_test_rt",
        bk_biz_id=1001,
    )
    models.VMStorageBindingConfig.objects.create(
        namespace="bkmonitor",
        name="bkm_test_rt",
        status="creating",
        data_link_name="bkm_test_data_link",
        bk_biz_id=1001,
    )
    models.DataBusConfig.objects.create(
        namespace="bkmonitor",
        name="bkm_test_rt",
        data_link_name="bkm_test_data_link",
        status="creating",
        bk_biz_id=1001,
    )
    yield
    models.DataLink.objects.filter(data_link_name="bkm_test_data_link").delete()
    models.DataIdConfig.objects.filter(name="bkm_test_data_link").delete()
    models.ResultTableConfig.objects.filter(name="bkm_test_rt").delete()
    models.VMStorageBindingConfig.objects.filter(name="bkm_test_rt").delete()
    models.DataBusConfig.objects.filter(name="bkm_test_rt").delete()
    models.BkBaseResultTable.objects.filter(bkbase_rt_name="bkm_test_rt").delete()


@pytest.mark.django_db(databases="__all__")
def test_refresh_data_link_status(create_or_delete_records):
    bkbase_rt_record = models.BkBaseResultTable.objects.get(data_link_name="bkm_test_data_link")
    data_link_name = bkbase_rt_record.data_link_name
    bkbase_rt_name = bkbase_rt_record.bkbase_rt_name
    _refresh_data_link_status(bkbase_rt_record=bkbase_rt_record)

    assert models.DataIdConfig.objects.get(name=data_link_name).status == "Failed"
    assert models.ResultTableConfig.objects.get(name=bkbase_rt_name).status == "Failed"
    assert models.VMStorageBindingConfig.objects.get(name=bkbase_rt_name).status == "Failed"
    assert models.DataBusConfig.objects.get(name=bkbase_rt_name).status == "Failed"
    assert models.BkBaseResultTable.objects.get(data_link_name=data_link_name).status == "Pending"


@pytest.fixture
def create_or_delete_records_legacy_names():
    """构造复用场景：RT / Binding / DataBus 三者各自复用 legacy 的不同 name，
    且 BkBaseResultTable.bkbase_rt_name 和 bkbase_data_name 与任何一个组件名都不完全一致。

    _refresh_data_link_status 必须按 data_link_name 遍历 kind，而不是按 bkbase_rt_name 查组件。
    """
    models.BkBaseResultTable.objects.create(
        data_link_name="bkm_reuse_data_link",
        # 故意给一个"历史脏名"，用以验证新实现不再依赖此字段查组件
        bkbase_data_name="bkm_reuse_data_link",
        storage_type="victoria_metrics",
        monitor_table_id="1001_bkm_time_series_reuse.__default__",
        storage_cluster_id=11,
        status="creating",
        bkbase_table_id="2_legacy_rt_reuse",
        # bkbase_rt_name 指向 RT 的 legacy 名；Binding/DataBus 名与之不同
        bkbase_rt_name="legacy_rt_reuse",
    )
    models.DataLink.objects.create(
        data_link_name="bkm_reuse_data_link",
        namespace="bkmonitor",
        data_link_strategy="bk_standard_v2_time_series",
        table_ids=["1001_bkm_time_series_reuse.__default__"],
        bk_data_id=70001,
    )
    models.DataIdConfig.objects.create(
        namespace="bkmonitor",
        name="bkm_reuse_data_link",
        bk_data_id=70001,
        bk_biz_id=1001,
    )
    models.ResultTableConfig.objects.create(
        namespace="bkmonitor",
        status="creating",
        data_link_name="bkm_reuse_data_link",
        name="legacy_rt_reuse",
        bk_biz_id=1001,
    )
    models.VMStorageBindingConfig.objects.create(
        namespace="bkmonitor",
        name="legacy_binding_reuse",
        status="creating",
        data_link_name="bkm_reuse_data_link",
        bk_biz_id=1001,
    )
    models.DataBusConfig.objects.create(
        namespace="bkmonitor",
        name="legacy_databus_reuse",
        data_link_name="bkm_reuse_data_link",
        status="creating",
        bk_biz_id=1001,
    )
    yield
    models.DataLink.objects.filter(data_link_name="bkm_reuse_data_link").delete()
    models.DataIdConfig.objects.filter(name="bkm_reuse_data_link").delete()
    models.ResultTableConfig.objects.filter(data_link_name="bkm_reuse_data_link").delete()
    models.VMStorageBindingConfig.objects.filter(data_link_name="bkm_reuse_data_link").delete()
    models.DataBusConfig.objects.filter(data_link_name="bkm_reuse_data_link").delete()
    models.BkBaseResultTable.objects.filter(data_link_name="bkm_reuse_data_link").delete()


@pytest.mark.django_db(databases="__all__")
def test_refresh_data_link_status_matches_by_data_link_name(create_or_delete_records_legacy_names):
    """复用后三者名字互不相同，新实现按 (data_link_name, bk_tenant_id, namespace) 过滤后全部刷新。"""
    bkbase_rt_record = models.BkBaseResultTable.objects.get(data_link_name="bkm_reuse_data_link")
    _refresh_data_link_status(bkbase_rt_record=bkbase_rt_record)

    # 三个组件都被按 data_link_name 找到并刷成 Failed（测试环境下 bkbase API 必然抛异常 -> Failed）
    assert models.ResultTableConfig.objects.get(name="legacy_rt_reuse").status == "Failed"
    assert models.VMStorageBindingConfig.objects.get(name="legacy_binding_reuse").status == "Failed"
    assert models.DataBusConfig.objects.get(name="legacy_databus_reuse").status == "Failed"
    # BkBaseResultTable 汇总结果：存在非 OK 组件 -> Pending
    assert models.BkBaseResultTable.objects.get(data_link_name="bkm_reuse_data_link").status == "Pending"


@pytest.fixture
def create_or_delete_records_data_id_mismatch():
    """构造 BkBaseResultTable.bkbase_data_name 与 DataIdConfig.name 不一致，
    但 DataLink.bk_data_id == DataIdConfig.bk_data_id 的场景，用于验证 fallback 路径。
    """
    models.BkBaseResultTable.objects.create(
        data_link_name="bkm_fallback_data_link",
        # 这个名字在 DataIdConfig 里不存在 -> 按 name 查必定 miss
        bkbase_data_name="stale_legacy_data_name",
        storage_type="victoria_metrics",
        monitor_table_id="1001_bkm_time_series_fallback.__default__",
        storage_cluster_id=11,
        status="creating",
        bkbase_table_id="2_bkm_fallback_rt",
        bkbase_rt_name="bkm_fallback_rt",
    )
    models.DataLink.objects.create(
        data_link_name="bkm_fallback_data_link",
        namespace="bkmonitor",
        data_link_strategy="bk_standard_v2_time_series",
        table_ids=["1001_bkm_time_series_fallback.__default__"],
        bk_data_id=80001,
    )
    # DataIdConfig.name 与 BkBaseResultTable.bkbase_data_name 故意不一致，
    # 但 bk_data_id 与 DataLink.bk_data_id 相等 -> 应当走 fallback 命中。
    models.DataIdConfig.objects.create(
        namespace="bkmonitor",
        name="actual_data_id_name",
        bk_data_id=80001,
        bk_biz_id=1001,
    )
    models.ResultTableConfig.objects.create(
        namespace="bkmonitor",
        status="creating",
        data_link_name="bkm_fallback_data_link",
        name="bkm_fallback_rt",
        bk_biz_id=1001,
    )
    models.VMStorageBindingConfig.objects.create(
        namespace="bkmonitor",
        name="bkm_fallback_rt",
        status="creating",
        data_link_name="bkm_fallback_data_link",
        bk_biz_id=1001,
    )
    models.DataBusConfig.objects.create(
        namespace="bkmonitor",
        name="bkm_fallback_rt",
        data_link_name="bkm_fallback_data_link",
        status="creating",
        bk_biz_id=1001,
    )
    yield
    models.DataLink.objects.filter(data_link_name="bkm_fallback_data_link").delete()
    models.DataIdConfig.objects.filter(name="actual_data_id_name").delete()
    models.ResultTableConfig.objects.filter(data_link_name="bkm_fallback_data_link").delete()
    models.VMStorageBindingConfig.objects.filter(data_link_name="bkm_fallback_data_link").delete()
    models.DataBusConfig.objects.filter(data_link_name="bkm_fallback_data_link").delete()
    models.BkBaseResultTable.objects.filter(data_link_name="bkm_fallback_data_link").delete()


@pytest.mark.django_db(databases="__all__")
def test_refresh_data_link_status_falls_back_to_bk_data_id(create_or_delete_records_data_id_mismatch):
    """按 bkbase_data_name 命不中时，必须 fallback 到按 DataLink.bk_data_id 查并刷新 DataIdConfig 状态。"""
    bkbase_rt_record = models.BkBaseResultTable.objects.get(data_link_name="bkm_fallback_data_link")
    _refresh_data_link_status(bkbase_rt_record=bkbase_rt_record)

    # fallback 命中后，DataIdConfig 按 bk_data_id 找到的记录被更新状态
    assert models.DataIdConfig.objects.get(name="actual_data_id_name").status == "Failed"


@pytest.mark.django_db(databases="__all__")
def test_refresh_graph_link_status_skips_local_binding(mocker):
    """GraphRelationBindingConfig 是本地聚合配置，不应作为 BKBase 资源查询状态。"""
    data_link_name = "bkm_graph_status_link"
    models.BkBaseResultTable.objects.create(
        data_link_name=data_link_name,
        bkbase_data_name=data_link_name,
        storage_type="victoria_metrics",
        monitor_table_id="1001_bkm_graph_status.__default__",
        storage_cluster_id=11,
        status="creating",
        bkbase_table_id="2_bkm_graph_status",
        bkbase_rt_name="graph_status_rt",
    )
    models.DataLink.objects.create(
        data_link_name=data_link_name,
        namespace="bkmonitor",
        data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES,
        table_ids=["1001_bkm_graph_status.__default__"],
        bk_data_id=90001,
    )
    models.DataIdConfig.objects.create(namespace="bkmonitor", name=data_link_name, bk_data_id=90001, bk_biz_id=1001)
    models.ResultTableConfig.objects.create(
        namespace="bkmonitor",
        status="creating",
        data_link_name=data_link_name,
        name="graph_status_rt",
        bk_biz_id=1001,
    )
    models.VMStorageBindingConfig.objects.create(
        namespace="bkmonitor",
        name="graph_status_binding",
        bkbase_result_table_name="graph_status_rt",
        status="creating",
        data_link_name=data_link_name,
        bk_biz_id=1001,
    )
    models.DataBusConfig.objects.create(
        namespace="bkmonitor",
        name="graph_status_databus",
        data_link_name=data_link_name,
        status="creating",
        bk_biz_id=1001,
    )
    graph_binding = models.GraphRelationBindingConfig.objects.create(
        namespace="bkmonitor",
        name="graph_status_binding_config",
        data_link_name=data_link_name,
        bkbase_result_table_name="graph_status_rt",
        vm_storage_binding_name="graph_status_binding",
        vm_databus_name="graph_status_databus",
        write_mode=models.GraphRelationBindingConfig.WRITE_MODE_VM,
        status="creating",
        bk_biz_id=1001,
    )
    status_mock = mocker.patch("metadata.task.tasks.get_data_link_component_status", return_value="Ok")

    _refresh_data_link_status(models.BkBaseResultTable.objects.get(data_link_name=data_link_name))

    queried_kinds = [call.kwargs["kind"] for call in status_mock.call_args_list]
    assert models.GraphRelationBindingConfig.kind not in queried_kinds
    assert models.GraphRelationBindingConfig.objects.get(pk=graph_binding.pk).status == "creating"


def _create_graph_status_link(
    *,
    create_vm_databus: bool = False,
    create_graph_result_table: bool = True,
    create_graph_binding: bool = True,
):
    data_link_name = "bkm_graph_databus_status_link"
    vm_databus_name = "graph_status_missing_vm_databus"
    graph_databus_name = "graph_status_graph_databus"
    models.BkBaseResultTable.objects.create(
        data_link_name=data_link_name,
        bkbase_data_name=data_link_name,
        storage_type="victoria_metrics",
        monitor_table_id="1001_bkm_graph_databus_status.__default__",
        storage_cluster_id=11,
        status="creating",
        bkbase_table_id="2_bkm_graph_databus_status",
        bkbase_rt_name="graph_status_vm_rt",
    )
    models.DataLink.objects.create(
        data_link_name=data_link_name,
        namespace="bkmonitor",
        data_link_strategy=models.DataLink.GRAPH_RELATION_TIME_SERIES,
        table_ids=["1001_bkm_graph_databus_status.__default__"],
        bk_data_id=90002,
    )
    models.DataIdConfig.objects.create(namespace="bkmonitor", name=data_link_name, bk_data_id=90002, bk_biz_id=1001)
    models.ResultTableConfig.objects.create(
        namespace="bkmonitor",
        status="creating",
        data_link_name=data_link_name,
        name="graph_status_vm_rt",
        bk_biz_id=1001,
    )
    if create_graph_result_table:
        models.ResultTableConfig.objects.create(
            namespace="bkmonitor",
            status="creating",
            data_link_name=data_link_name,
            name="graph_status_graph_rt",
            bk_biz_id=1001,
        )
    models.VMStorageBindingConfig.objects.create(
        namespace="bkmonitor",
        name="graph_status_vm_binding",
        bkbase_result_table_name="graph_status_vm_rt",
        status="creating",
        data_link_name=data_link_name,
        bk_biz_id=1001,
    )
    models.SurrealDBBindingConfig.objects.create(
        namespace="bkmonitor",
        name="graph_status_surreal_binding",
        bkbase_result_table_name="graph_status_graph_rt",
        surrealdb_cluster_name="surrealdb",
        status="creating",
        data_link_name=data_link_name,
        bk_biz_id=1001,
    )
    if create_vm_databus:
        models.DataBusConfig.objects.create(
            namespace="bkmonitor",
            name=vm_databus_name,
            data_link_name=data_link_name,
            status="creating",
            bk_biz_id=1001,
        )
    models.GraphDataBusConfig.objects.create(
        namespace="bkmonitor",
        name=graph_databus_name,
        data_id_name=data_link_name,
        data_link_name=data_link_name,
        status="creating",
        bk_biz_id=1001,
        bk_data_id=90002,
        sink_names=["SurrealDBBinding:graph_status_surreal_binding"],
    )
    if create_graph_binding:
        models.GraphRelationBindingConfig.objects.create(
            namespace="bkmonitor",
            name="graph_status_binding_config",
            data_link_name=data_link_name,
            bkbase_result_table_name="graph_status_vm_rt",
            graph_result_table_name="graph_status_graph_rt",
            vm_storage_binding_name="graph_status_vm_binding",
            vm_databus_name=vm_databus_name,
            surrealdb_binding_name="graph_status_surreal_binding",
            graph_databus_name=graph_databus_name,
            write_mode=models.GraphRelationBindingConfig.WRITE_MODE_VM_AND_SURREALDB,
            status="creating",
            bk_biz_id=1001,
        )
    assert models.DataBusConfig.objects.filter(name=graph_databus_name).exists()
    return data_link_name, vm_databus_name, graph_databus_name


@pytest.mark.django_db(databases="__all__")
def test_refresh_graph_link_status_does_not_count_graph_databus_as_vm(mocker):
    data_link_name, vm_databus_name, graph_databus_name = _create_graph_status_link()

    status_mock = mocker.patch("metadata.task.tasks.get_data_link_component_status", return_value="Ok")
    _refresh_data_link_status(models.BkBaseResultTable.objects.get(data_link_name=data_link_name))

    queried_databus_names = [
        call.kwargs["component_name"]
        for call in status_mock.call_args_list
        if call.kwargs["kind"] == models.DataBusConfig.kind
    ]
    assert vm_databus_name not in queried_databus_names
    assert queried_databus_names.count(graph_databus_name) == 1
    assert models.BkBaseResultTable.objects.get(data_link_name=data_link_name).status == "Pending"


@pytest.mark.django_db(databases="__all__")
def test_refresh_graph_link_status_requires_each_result_table(mocker):
    data_link_name, _, _ = _create_graph_status_link(
        create_vm_databus=True,
        create_graph_result_table=False,
    )

    status_mock = mocker.patch("metadata.task.tasks.get_data_link_component_status", return_value="Ok")
    _refresh_data_link_status(models.BkBaseResultTable.objects.get(data_link_name=data_link_name))

    queried_result_table_names = [
        call.kwargs["component_name"]
        for call in status_mock.call_args_list
        if call.kwargs["kind"] == models.ResultTableConfig.kind
    ]
    assert "graph_status_vm_rt" in queried_result_table_names
    assert "graph_status_graph_rt" not in queried_result_table_names
    assert models.BkBaseResultTable.objects.get(data_link_name=data_link_name).status == "Pending"


@pytest.mark.django_db(databases="__all__")
def test_refresh_graph_link_status_requires_graph_binding(mocker):
    data_link_name, _, _ = _create_graph_status_link(
        create_vm_databus=True,
        create_graph_binding=False,
    )

    mocker.patch("metadata.task.tasks.get_data_link_component_status", return_value="Ok")
    _refresh_data_link_status(models.BkBaseResultTable.objects.get(data_link_name=data_link_name))

    assert models.BkBaseResultTable.objects.get(data_link_name=data_link_name).status == "Pending"


@pytest.mark.django_db(databases="__all__")
def test_get_bkdata_status_does_not_count_graph_databus_as_vm(mocker):
    data_link_name, vm_databus_name, graph_databus_name = _create_graph_status_link()
    mocker.patch(
        "metadata.models.data_link.service.get_data_link_component_config",
        return_value={"status": {"phase": "OK"}},
    )

    bkdata_status = get_bkdata_status("system", data_link_name)

    assert not bkdata_status.finished
    assert f"Name:{vm_databus_name}配置不存在" in bkdata_status.message
    missing_vm_databus_status = next(
        status
        for status in bkdata_status.component_statuses
        if status.kind == models.DataBusConfig.kind and status.name == vm_databus_name
    )
    assert not missing_vm_databus_status.exists
    graph_databus_statuses = [
        status
        for status in bkdata_status.component_statuses
        if status.kind == models.DataBusConfig.kind and status.name == graph_databus_name
    ]
    assert len(graph_databus_statuses) == 1
    assert graph_databus_statuses[0].exists


@pytest.mark.django_db(databases="__all__")
def test_get_bkdata_status_requires_each_graph_result_table(mocker):
    data_link_name, _, _ = _create_graph_status_link(
        create_vm_databus=True,
        create_graph_result_table=False,
    )
    mocker.patch(
        "metadata.models.data_link.service.get_data_link_component_config",
        return_value={"status": {"phase": "OK"}},
    )

    bkdata_status = get_bkdata_status("system", data_link_name)

    assert not bkdata_status.finished
    assert "Name:graph_status_graph_rt配置不存在" in bkdata_status.message
    missing_graph_rt_status = next(
        status
        for status in bkdata_status.component_statuses
        if status.kind == models.ResultTableConfig.kind and status.name == "graph_status_graph_rt"
    )
    assert not missing_graph_rt_status.exists


@pytest.mark.django_db(databases="__all__")
def test_get_bkdata_status_requires_graph_binding(mocker):
    data_link_name, _, _ = _create_graph_status_link(
        create_vm_databus=True,
        create_graph_binding=False,
    )
    mocker.patch(
        "metadata.models.data_link.service.get_data_link_component_config",
        return_value={"status": {"phase": "OK"}},
    )

    bkdata_status = get_bkdata_status("system", data_link_name)

    assert not bkdata_status.finished
    assert models.GraphRelationBindingConfig.kind in bkdata_status.message
