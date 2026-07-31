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
