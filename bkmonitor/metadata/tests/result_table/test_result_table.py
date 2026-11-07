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

from constants.common import DEFAULT_TENANT_ID
from metadata import models


@pytest.fixture
def create_or_update_records():
    result_table = models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__", bk_biz_id=1001, is_custom_table=False
    )
    yield result_table
    result_table.delete()


@pytest.mark.django_db(databases="__all__")
def test_notify_bkdata_log_data_id_changed(create_or_update_records):
    """
    测试是否能够如期传递参数并通知计算平台，数据源发生改变
    """
    rt = models.ResultTable.objects.get(table_id="1001_bkmonitor_time_series_50010.__default__")

    # 使用 patch 来模拟 API 调用
    with patch("core.drf_resource.api.bkdata.notify_log_data_id_changed") as mock_notify:
        rt.notify_bkdata_log_data_id_changed(data_id=50010)

        # 验证 API 请求是否按照预期调用
        mock_notify.assert_called_once_with(data_id=50010)

        # 获取调用参数
        args, kwargs = mock_notify.call_args

        # 检查参数是否正确
        assert kwargs["data_id"] == 50010


@pytest.mark.django_db(databases="__all__")
def test_manage_query_alias_settings():
    """
    测试ESFieldQueryAliasOption的动态管理
    """

    # 测试点1: 别名配置新增
    query_alias_settings = [
        {"field_name": "__ext.io_kubernetes_pod", "query_alias": "k8s_pod"},
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns"},
    ]
    table_id = "2_bklog.job_dev"
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )

    alias_1 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_pod", bk_tenant_id=DEFAULT_TENANT_ID
    )
    alias_2 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_namespace", bk_tenant_id=DEFAULT_TENANT_ID
    )

    assert alias_1.query_alias == "k8s_pod"
    assert alias_2.query_alias == "k8s_ns"

    # 测试点2: 别名配置修改&软删除
    query_alias_settings = [
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns"},
        {"field_name": "__ext.io_kubernetes_context", "query_alias": "k8s_context"},
    ]
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )

    alias_1 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_pod", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_1.is_deleted is True
    alias_2 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_namespace", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_2.query_alias == "k8s_ns"
    alias_3 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_context", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_3.query_alias == "k8s_context"

    # 测试点3: 别名配置修改&软删除回复
    query_alias_settings = [
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns"},
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns1"},
        {"field_name": "__ext.io_kubernetes_pod", "query_alias": "k8s_pod"},
    ]
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )

    alias_ns1 = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, query_alias="k8s_ns1", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_2.field_path == "__ext.io_kubernetes_namespace"

    alias_ns = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, query_alias="k8s_ns", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_ns.is_deleted is False
    assert alias_ns1.query_alias == "k8s_ns1"

    alias_pod = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_pod", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_pod.query_alias == "k8s_pod"
    assert alias_pod.is_deleted is False

    alias_context = models.ESFieldQueryAliasOption.objects.get(
        table_id=table_id, field_path="__ext.io_kubernetes_context", bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert alias_context.query_alias == "k8s_context"


@pytest.mark.django_db(databases="__all__")
def test_generate_query_alias_settings():
    """
    测试能否正确生成采集项的别名配置
    """

    # 测试点1: 别名配置新增->组装
    table_id = "2_bklog.job_dev"
    query_alias_settings = [
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns"},
        {"field_name": "__ext.io_kubernetes_context", "query_alias": "k8s_context"},
    ]
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )
    expected = {
        "k8s_ns": {"type": "alias", "path": "__ext.io_kubernetes_namespace"},
        "k8s_context": {"type": "alias", "path": "__ext.io_kubernetes_context"},
    }
    actual_config = models.ESFieldQueryAliasOption.generate_query_alias_settings(
        table_id, bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert json.dumps(actual_config) == json.dumps(expected)

    # 测试点2: 软删除的配置不会出现
    query_alias_settings = [
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns"},
        {"field_name": "__ext.io_kubernetes_namespace", "query_alias": "k8s_ns1"},
        {"field_name": "__ext.io_kubernetes_pod", "query_alias": "k8s_pod"},
    ]
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )
    expected = {
        "k8s_ns": {"type": "alias", "path": "__ext.io_kubernetes_namespace"},
        "k8s_ns1": {"type": "alias", "path": "__ext.io_kubernetes_namespace"},
        "k8s_pod": {"type": "alias", "path": "__ext.io_kubernetes_pod"},
    }
    actual_config = models.ESFieldQueryAliasOption.generate_query_alias_settings(
        table_id, bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert json.dumps(actual_config) == json.dumps(expected)

    query_alias_settings = []
    models.ESFieldQueryAliasOption.manage_query_alias_settings(
        query_alias_settings=query_alias_settings,
        table_id=table_id,
        operator="admin",
        bk_tenant_id=DEFAULT_TENANT_ID,
    )
    expected = {}
    actual_config = models.ESFieldQueryAliasOption.generate_query_alias_settings(
        table_id, bk_tenant_id=DEFAULT_TENANT_ID
    )
    assert json.dumps(actual_config) == json.dumps(expected)


@pytest.mark.django_db(databases="__all__")
def test_modify_passes_previous_log_option_and_field_types_to_doris_sync(mocker):
    """modify 在重建字段之前快照旧 option 与旧字段类型，用于 Doris 换表判定。"""
    table_id = "1001_bklog.modify_doris_rotate"
    models.ClusterInfo.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        cluster_id=3100,
        cluster_name="doris_modify_rotate",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.rotate",
        port=9030,
        description="",
        is_default_cluster=False,
        version="2.1",
    )
    result_table = models.ResultTable.objects.create(
        table_id=table_id,
        bk_tenant_id=DEFAULT_TENANT_ID,
        bk_biz_id=1001,
        table_name_zh=table_id,
        is_custom_table=True,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        default_storage=models.ClusterInfo.TYPE_DORIS,
        creator="system",
        last_modify_user="system",
        is_enable=True,
    )
    data_source = models.DataSource.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        bk_data_id=81903,
        data_name="modify_doris_rotate_log",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_log_text",
        is_custom_source=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        bk_data_id=data_source.bk_data_id,
        table_id=table_id,
        creator="system",
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id=table_id,
        storage_cluster_id=3100,
        source_type="log",
    )
    models.ResultTableField.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id=table_id,
        field_name="log",
        field_type=models.ResultTableField.FIELD_TYPE_STRING,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )
    old_option = {
        "clean_rules": [
            {
                "input_id": "log",
                "output_id": "log",
                "operator": {"type": "assign", "key_index": "log", "output_type": "string"},
            }
        ],
        "doris_storage_config": {"storage_keys": ["log"], "tokenizers": {"log": "./=:"}},
    }
    models.ResultTableOption.objects.create(
        bk_tenant_id=DEFAULT_TENANT_ID,
        table_id=table_id,
        name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        value=json.dumps(old_option),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="system",
    )
    new_option = json.loads(json.dumps(old_option))
    new_option["doris_storage_config"]["tokenizers"] = {"log": "./=:,|"}

    sync_mock = mocker.patch.object(models.DorisStorage, "sync_log_physical_table", autospec=True)
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})

    result_table.modify(
        operator="system",
        option={models.ResultTableOption.OPTION_V4_LOG_DATA_LINK: new_option},
    )

    assert sync_mock.call_count == 1
    call_kwargs = sync_mock.call_args.kwargs
    assert call_kwargs["table_id"] == table_id
    assert call_kwargs["bk_biz_id"] == 1001
    assert json.loads(call_kwargs["previous_option_value"]) == old_option
    assert call_kwargs["previous_field_types"] == {"log": models.ResultTableField.FIELD_TYPE_STRING}

    models.ResultTableOption.objects.filter(table_id=table_id).delete()
    models.DataSourceResultTable.objects.filter(table_id=table_id).delete()
    models.DataSource.objects.filter(bk_data_id=81903).delete()
    models.ResultTableField.objects.filter(table_id=table_id).delete()
    models.StorageClusterRecord.objects.filter(table_id=table_id).delete()
    models.DorisStorage.objects.filter(table_id=table_id).delete()
    models.ResultTable.objects.filter(table_id=table_id).delete()
    models.ClusterInfo.objects.filter(cluster_id=3100).delete()
