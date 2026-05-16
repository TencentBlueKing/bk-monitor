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

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.data_link import DataLink
from metadata.task.datalink import apply_event_group_datalink, apply_log_datalink

pytestmark = pytest.mark.django_db(databases="__all__")


# 日志链路 LogV4DataLinkOption 同时声明 ES 和 Doris 存储时的最小有效配置。
LOG_V4_DATALINK_OPTION_VALUE = {
    "clean_rules": [
        {
            "input_id": "data",
            "output_id": "data",
            "operator": {"type": "assign", "key_index": "data", "output_type": "string"},
        }
    ],
    "es_storage_config": {"unique_field_list": ["log"], "json_field_list": []},
    "doris_storage_config": {"storage_keys": ["log"]},
}


@pytest.fixture
def log_v4_datalink_records(mocker):
    """搭建日志 V4 链路所需的最小 records：RT、DS、option 配置以及 ES/Doris 存储/集群。

    关键约束：``register_to_bkbase`` 走 BKDATA created_from 直接跳过，不需要外部 mock；
    剩余 BKBase 远程写入由 ``DataLink.apply_data_link`` 的 patch 兜住。
    """
    bk_tenant_id = "system"
    table_id = "space_4281349_bklog.ai_flowtest8__default__json"
    bk_biz_id = -4281349

    models.Space.objects.create(
        space_type_id="bkcc",
        space_id="4281349",
        space_name="space_4281349",
        bk_tenant_id=bk_tenant_id,
    )
    rt = models.ResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_DORIS,
        creator="system",
        bk_biz_id=bk_biz_id,
    )
    ds = models.DataSource.objects.create(
        bk_data_id=510010,
        bk_tenant_id=bk_tenant_id,
        data_name="bklog_apply_log_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_log_text",
        is_custom_source=False,
        # 让 register_to_bkbase 直接跳过：created_from == BKDATA 时不会发起远程注册。
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=ds.bk_data_id,
        table_id=table_id,
        creator="system",
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=models.ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
        value="true",
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        value=json.dumps(LOG_V4_DATALINK_OPTION_VALUE),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    es_cluster = models.ClusterInfo.objects.create(
        cluster_name="bklog_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.test",
        port=9200,
        description="",
        is_default_cluster=False,
        version="7.x",
        bk_tenant_id=bk_tenant_id,
    )
    doris_cluster = models.ClusterInfo.objects.create(
        cluster_name="bklog_doris",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.test",
        port=9030,
        description="",
        is_default_cluster=False,
        version="2.x",
        bk_tenant_id=bk_tenant_id,
    )
    models.ESStorage.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        storage_cluster_id=es_cluster.cluster_id,
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        storage_cluster_id=doris_cluster.cluster_id,
    )
    yield {
        "bk_tenant_id": bk_tenant_id,
        "table_id": table_id,
        "rt": rt,
        "ds": ds,
        "es_cluster": es_cluster,
        "doris_cluster": doris_cluster,
    }
    models.ResultTableOption.objects.filter(table_id=table_id).delete()
    models.DataSourceResultTable.objects.filter(table_id=table_id).delete()
    models.ResultTable.objects.filter(table_id=table_id).delete()
    models.ESStorage.objects.filter(table_id=table_id).delete()
    models.DorisStorage.objects.filter(table_id=table_id).delete()
    models.ESStorageBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id).delete()
    models.DorisStorageBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id).delete()
    models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, namespace="bklog").delete()
    models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id).delete()
    models.DataSource.objects.filter(bk_data_id=ds.bk_data_id).delete()
    models.ClusterInfo.objects.filter(cluster_id__in=[es_cluster.cluster_id, doris_cluster.cluster_id]).delete()
    models.Space.objects.filter(space_id="4281349").delete()


def test_apply_log_datalink_uses_default_storage_doris(log_v4_datalink_records):
    """default_storage=Doris 且 ES/Doris 都存在时，sync_metadata 应使用 Doris 集群 id。"""
    ctx = log_v4_datalink_records

    with (
        patch.object(DataLink, "apply_data_link", return_value=None),
        patch.object(DataLink, "sync_metadata") as mocked_sync,
    ):
        apply_log_datalink(bk_tenant_id=ctx["bk_tenant_id"], table_id=ctx["table_id"])

    mocked_sync.assert_called_once()
    call_kwargs = mocked_sync.call_args.kwargs
    assert call_kwargs["table_id"] == ctx["table_id"]
    assert call_kwargs["storage_cluster_id"] == ctx["doris_cluster"].cluster_id


def test_apply_log_datalink_uses_default_storage_es(log_v4_datalink_records):
    """default_storage=ES 且 ES/Doris 都存在时，sync_metadata 应使用 ES 集群 id。"""
    ctx = log_v4_datalink_records
    rt = ctx["rt"]
    rt.default_storage = models.ClusterInfo.TYPE_ES
    rt.save(update_fields=["default_storage"])

    with (
        patch.object(DataLink, "apply_data_link", return_value=None),
        patch.object(DataLink, "sync_metadata") as mocked_sync,
    ):
        apply_log_datalink(bk_tenant_id=ctx["bk_tenant_id"], table_id=ctx["table_id"])

    mocked_sync.assert_called_once()
    assert mocked_sync.call_args.kwargs["storage_cluster_id"] == ctx["es_cluster"].cluster_id


def test_apply_log_datalink_falls_back_when_default_storage_missing(log_v4_datalink_records):
    """default_storage 指向的存储缺失时，回退到任一存在的 storage。"""
    ctx = log_v4_datalink_records
    # default_storage=ES，但删除 ESStorage，仅留 Doris -> 应回退到 Doris。
    rt = ctx["rt"]
    rt.default_storage = models.ClusterInfo.TYPE_ES
    rt.save(update_fields=["default_storage"])

    log_option = models.ResultTableOption.objects.get(
        table_id=ctx["table_id"], name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    )
    payload = json.loads(log_option.value)
    payload.pop("es_storage_config", None)
    log_option.value = json.dumps(payload)
    log_option.save()

    with (
        patch.object(DataLink, "apply_data_link", return_value=None),
        patch.object(DataLink, "sync_metadata") as mocked_sync,
    ):
        apply_log_datalink(bk_tenant_id=ctx["bk_tenant_id"], table_id=ctx["table_id"])

    assert mocked_sync.call_args.kwargs["storage_cluster_id"] == ctx["doris_cluster"].cluster_id


@pytest.fixture
def event_group_v4_records():
    """事件组 V4 链路最小 records：RT、DS、option 配置以及 ES 集群/存储。"""
    bk_tenant_id = "system"
    table_id = "1001_bkmonitor_event_test.__default__"
    bk_biz_id = 1001

    rt = models.ResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_ES,
        creator="system",
        bk_biz_id=bk_biz_id,
    )
    ds = models.DataSource.objects.create(
        bk_data_id=510020,
        bk_tenant_id=bk_tenant_id,
        data_name="bkmonitor_event_test",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_standard_v2_event",
        is_custom_source=False,
        created_from=DataIdCreatedFromSystem.BKDATA.value,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=ds.bk_data_id,
        table_id=table_id,
        creator="system",
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=models.ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
        value="true",
        value_type=models.ResultTableOption.TYPE_BOOL,
        creator="system",
    )
    es_cluster = models.ClusterInfo.objects.create(
        cluster_name="event_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="event.es.test",
        port=9200,
        description="",
        is_default_cluster=False,
        version="7.x",
        bk_tenant_id=bk_tenant_id,
    )
    models.ESStorage.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        storage_cluster_id=es_cluster.cluster_id,
    )
    yield {
        "bk_tenant_id": bk_tenant_id,
        "table_id": table_id,
        "rt": rt,
        "ds": ds,
        "es_cluster": es_cluster,
    }
    models.ResultTableOption.objects.filter(table_id=table_id).delete()
    models.DataSourceResultTable.objects.filter(table_id=table_id).delete()
    models.ResultTable.objects.filter(table_id=table_id).delete()
    models.ESStorage.objects.filter(table_id=table_id).delete()
    models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, namespace="bklog").delete()
    models.BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id).delete()
    models.DataSource.objects.filter(bk_data_id=ds.bk_data_id).delete()
    models.ClusterInfo.objects.filter(cluster_id=es_cluster.cluster_id).delete()


def test_apply_event_group_datalink_invokes_sync_metadata(event_group_v4_records):
    """事件组 V4 链路应在 apply 后调用 sync_metadata，并传入 ES storage 的 cluster_id。"""
    ctx = event_group_v4_records

    with (
        patch.object(DataLink, "apply_data_link", return_value=None),
        patch.object(DataLink, "sync_metadata") as mocked_sync,
    ):
        apply_event_group_datalink(bk_tenant_id=ctx["bk_tenant_id"], table_id=ctx["table_id"])

    mocked_sync.assert_called_once()
    assert mocked_sync.call_args.kwargs["storage_cluster_id"] == ctx["es_cluster"].cluster_id
    assert mocked_sync.call_args.kwargs["table_id"] == ctx["table_id"]
