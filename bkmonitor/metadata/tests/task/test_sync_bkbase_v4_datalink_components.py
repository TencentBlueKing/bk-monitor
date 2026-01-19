"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

import pytest

from core.drf_resource import api
from metadata import models
from metadata.models.data_link import utils as data_link_utils
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_MONITOR, DataLinkKind
from metadata.task.bkbase import sync_bkbase_v4_datalink_components


@pytest.mark.django_db(databases="__all__")
def test_sync_bkbase_v4_datalink_components_basic(monkeypatch):
    bk_tenant_id = "system"
    bk_biz_id = 2
    data_name = "test_metric_data"
    bk_data_id = 50010
    table_id = "1001_bkmonitor_time_series_50010.__default__"
    data_id_name = data_link_utils.compose_bkdata_data_id_name(data_name)
    rt_name = "bkm_test_rt"

    models.DataSource.objects.create(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=bk_data_id,
        data_name=data_name,
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        created_from="bkdata",
    )
    models.DataSourceResultTable.objects.create(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id, table_id=table_id)
    cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=bk_tenant_id,
        cluster_name="vm_cluster",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.example.com",
        port=80,
        description="vm cluster",
        is_default_cluster=True,
    )

    def mock_list_data_link(bk_tenant_id: str, namespace: str, kind: str) -> list[dict[str, Any]]:
        if namespace != BKBASE_NAMESPACE_BK_MONITOR:
            return []
        if kind == DataLinkKind.get_choice_value(DataLinkKind.DATAID.value):
            return [
                {
                    "metadata": {
                        "name": data_id_name,
                        "namespace": namespace,
                        "labels": {"bk_biz_id": str(bk_biz_id)},
                    },
                    "status": {"phase": "Ok"},
                }
            ]
        if kind == DataLinkKind.get_choice_value(DataLinkKind.RESULTTABLE.value):
            return [
                {
                    "metadata": {
                        "name": rt_name,
                        "namespace": namespace,
                        "labels": {"bk_biz_id": str(bk_biz_id)},
                    },
                    "spec": {"dataType": "metric"},
                    "status": {"phase": "Ok"},
                }
            ]
        if kind == DataLinkKind.get_choice_value(DataLinkKind.VMSTORAGEBINDING.value):
            return [
                {
                    "metadata": {
                        "name": rt_name,
                        "namespace": namespace,
                        "labels": {"bk_biz_id": str(bk_biz_id)},
                    },
                    "spec": {"storage": {"name": "vm_cluster"}},
                    "status": {"phase": "Ok"},
                }
            ]
        if kind == DataLinkKind.get_choice_value(DataLinkKind.DATABUS.value):
            return [
                {
                    "metadata": {
                        "name": rt_name,
                        "namespace": namespace,
                        "labels": {"bk_biz_id": str(bk_biz_id)},
                    },
                    "spec": {
                        "sources": [{"kind": "DataId", "name": data_id_name, "namespace": namespace}],
                    },
                    "status": {"phase": "Ok"},
                }
            ]
        return []

    monkeypatch.setattr(api.bk_login, "list_tenant", lambda: [{"id": bk_tenant_id, "name": "Blueking"}])
    monkeypatch.setattr(api.bkdata, "list_data_link", mock_list_data_link)

    sync_bkbase_v4_datalink_components()

    data_id_config = models.DataIdConfig.objects.get(name=data_id_name)
    assert data_id_config.status == "Ok"

    databus = models.DataBusConfig.objects.get(name=rt_name)
    assert databus.data_id_name == data_id_name
    assert databus.data_link_name == data_id_name
    assert databus.bk_data_id == bk_data_id

    datalink = models.DataLink.objects.get(data_link_name=data_id_name)
    assert datalink.bk_data_id == bk_data_id
    assert datalink.table_ids == [table_id]

    bkbase_rt = models.BkBaseResultTable.objects.get(data_link_name=data_id_name)
    assert bkbase_rt.monitor_table_id == table_id
    assert bkbase_rt.bkbase_rt_name == rt_name
    assert bkbase_rt.bkbase_data_name == data_id_name
    assert bkbase_rt.storage_type == models.ClusterInfo.TYPE_VM
    assert bkbase_rt.storage_cluster_id == cluster.cluster_id
