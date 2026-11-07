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
from unittest.mock import PropertyMock

import pytest

from metadata import models
from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig
from metadata.models import storage as storage_models


@pytest.fixture
def doris_storage():
    models.ClusterInfo.objects.update_or_create(
        bk_tenant_id="system",
        cluster_id=1001,
        defaults={
            "cluster_name": "doris_bklog",
            "cluster_type": models.ClusterInfo.TYPE_DORIS,
            "domain_name": "doris.service.consul",
            "port": 9030,
            "description": "",
            "is_default_cluster": False,
            "username": "doris_user",
            "password": "doris_password",
            "version": "2.1",
        },
    )
    DorisStorageBindingConfig.objects.update_or_create(
        bk_tenant_id="system",
        table_id="2_bklog.test",
        defaults={
            "name": "bklog_2_test",
            "namespace": "bklog",
            "data_link_name": "bklog_2_test",
            "bk_biz_id": 2,
            "status": "Ok",
            "bkbase_result_table_name": "bklog_2_test",
            "doris_cluster_name": "doris_bklog",
        },
    )
    doris_storage_obj, _ = models.DorisStorage.objects.update_or_create(
        bk_tenant_id="system",
        table_id="2_bklog.test",
        defaults={
            "bkbase_table_id": "bklog_2_test",
            "source_type": "bkdata",
            "index_set": "bklog_2_test",
            "table_type": models.DorisStorage.PRIMARY_TABLE_TYPE,
            "field_config_mapping": json.dumps({"search_an": ["log"]}),
            "expire_days": 30,
            "storage_cluster_id": 1001,
        },
    )
    return doris_storage_obj


@pytest.fixture
def virtual_doris_storage(doris_storage):
    virtual_storage_obj, _ = models.DorisStorage.objects.update_or_create(
        bk_tenant_id="system",
        table_id="2_bklog.virtual",
        defaults={
            "bkbase_table_id": "",
            "origin_table_id": doris_storage.table_id,
            "source_type": "bkdata",
            "index_set": "bklog_2_virtual",
            "table_type": models.DorisStorage.PRIMARY_TABLE_TYPE,
            "field_config_mapping": json.dumps({}),
            "expire_days": 30,
            "storage_cluster_id": 1001,
        },
    )
    return virtual_storage_obj


def build_doris_binding(*, annotations=None, storage_config=None):
    storage_config = storage_config or {
        "db": "mapleleaf_2",
        "table": "bklog_2_test_2",
        "storage_keys": ["dtEventTimeStamp", "serverIp"],
        "expires": "30d",
    }
    return {
        "kind": "DorisBinding",
        "metadata": {
            "tenant": "default",
            "namespace": "bklog",
            "name": "bklog_2_test",
            "annotations": annotations or {},
        },
        "spec": {
            "data": {
                "kind": "ResultTable",
                "tenant": "default",
                "namespace": "bklog",
                "name": "bklog_2_test",
            },
            "storage": {
                "kind": "Doris",
                "tenant": "default",
                "namespace": "bklog",
                "name": "doris_bklog",
            },
            "storage_config": storage_config,
        },
        "status": {"phase": "Ok", "message": ""},
    }


@pytest.mark.django_db(databases="__all__")
def test_create_table_rolls_back_and_reraises_when_cluster_record_creation_fails(mocker):
    table_id = "2_bklog.doris_create_failure"
    cluster = models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=1101,
        cluster_name="doris_create_failure",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.service.consul",
        port=9030,
        description="",
        is_default_cluster=False,
        version="2.1",
    )
    mocker.patch.object(
        storage_models.StorageClusterRecord.objects,
        "update_or_create",
        side_effect=RuntimeError("create storage cluster record failed"),
    )

    with pytest.raises(RuntimeError, match="create storage cluster record failed"):
        models.DorisStorage.create_table(
            table_id=table_id,
            bk_tenant_id="system",
            storage_cluster_id=cluster.cluster_id,
            field_config_mapping={},
        )

    assert not models.DorisStorage.objects.filter(table_id=table_id, bk_tenant_id="system").exists()
    assert not models.StorageClusterRecord.objects.filter(table_id=table_id, bk_tenant_id="system").exists()


@pytest.mark.django_db(databases="__all__")
def test_get_doris_connection_config_from_storage_cluster(doris_storage):
    connection_config = doris_storage.get_doris_connection_config()

    assert connection_config == {
        "host": "doris.service.consul",
        "port": 9030,
        "username": "doris_user",
        "password": "doris_password",
        "cluster_id": 1001,
        "cluster_name": "doris_bklog",
        "version": "2.1",
    }


@pytest.mark.django_db(databases="__all__")
def test_get_by_table_id_returns_origin_doris_storage_for_virtual_table(virtual_doris_storage):
    storage = models.DorisStorage.get_by_table_id("system", virtual_doris_storage.table_id)

    assert storage.table_id == "2_bklog.test"
    assert storage.origin_table_id in (None, "")


@pytest.mark.django_db(databases="__all__")
def test_get_physical_table_name_prefers_annotation(doris_storage, mocker):
    doris_binding = build_doris_binding(
        annotations={
            "PhysicalTableName": "mapleleaf_2.bklog_2_test_2",
            "index0": "ResultTable/bklog/bklog_2_test",
        }
    )
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )

    physical_table = doris_storage.get_physical_table_name()

    assert physical_table == {
        "physical_table_name": "mapleleaf_2.bklog_2_test_2",
        "database": "mapleleaf_2",
        "table": "bklog_2_test_2",
        "source": "metadata.annotations.PhysicalTableName",
    }


@pytest.mark.django_db(databases="__all__")
def test_get_physical_table_name_fallbacks_to_storage_config(doris_storage, mocker):
    doris_binding = build_doris_binding(storage_config={"db": "mapleleaf_2", "table": "bklog_2_test_2"})
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )

    physical_table = doris_storage.get_physical_table_name()

    assert physical_table == {
        "physical_table_name": "mapleleaf_2.bklog_2_test_2",
        "database": "mapleleaf_2",
        "table": "bklog_2_test_2",
        "source": "spec.storage_config.db_table",
    }


class FakeDorisCursor:
    def __init__(self, fetchall_results=None):
        self.execute_calls = []
        self.fetchall_results = fetchall_results or [
            [{"TABLE_NAME": "bklog_2_test_2", "TABLE_ROWS": 10}],
            [{"COLUMN_NAME": "dtEventTimeStamp", "DATA_TYPE": "datetime"}],
            [{"PARTITION_NAME": "p20260511"}],
            [{"Table": "bklog_2_test_2", "Create Table": "CREATE TABLE ..."}],
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def execute(self, sql, params=None):
        self.execute_calls.append((sql, params))

    def fetchall(self):
        return self.fetchall_results.pop(0)


class FakeDorisConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


@pytest.mark.django_db(databases="__all__")
def test_query_physical_storage_metadata_queries_doris_raw_metadata(doris_storage, mocker):
    doris_binding = build_doris_binding(
        annotations={
            "PhysicalTableName": "mapleleaf_2.bklog_2_test_2",
            "index0": "ResultTable/bklog/bklog_2_test",
        }
    )
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor()
    fake_connection = FakeDorisConnection(fake_cursor)
    mock_connect = mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    result = doris_storage.query_physical_storage_metadata()

    mock_connect.assert_called_once_with(
        host="doris.service.consul",
        port=9030,
        user="doris_user",
        password="doris_password",
        database="mapleleaf_2",
        charset="utf8mb4",
        cursorclass=storage_models.pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
    )
    assert fake_connection.closed is True
    assert len(fake_cursor.execute_calls) == 4
    assert fake_cursor.execute_calls[0][1] == ("mapleleaf_2", "bklog_2_test_2")
    assert fake_cursor.execute_calls[-1][0] == "SHOW CREATE TABLE `mapleleaf_2`.`bklog_2_test_2`"

    assert result["doris_storage"]["field_config_mapping"] == {"search_an": ["log"]}
    assert result["storage_cluster"] == {
        "cluster_id": 1001,
        "cluster_name": "doris_bklog",
        "domain_name": "doris.service.consul",
        "port": 9030,
        "version": "2.1",
    }
    assert "password" not in result["storage_cluster"]
    assert result["doris_binding"]["physical_table_name"] == "mapleleaf_2.bklog_2_test_2"
    assert result["physical_metadata"]["tables"] == [{"TABLE_NAME": "bklog_2_test_2", "TABLE_ROWS": 10}]
    assert result["errors"] == []


@pytest.mark.django_db(databases="__all__")
def test_query_physical_storage_metadata_can_skip_show_create_table(doris_storage, mocker):
    doris_binding = build_doris_binding(
        annotations={"PhysicalTableName": "mapleleaf_2.bklog_2_test_2"},
    )
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor()
    fake_connection = FakeDorisConnection(fake_cursor)
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    result = doris_storage.query_physical_storage_metadata(include_create_table=False)

    assert len(fake_cursor.execute_calls) == 3
    assert all("SHOW CREATE TABLE" not in sql for sql, _params in fake_cursor.execute_calls)
    assert "show_create_table" not in result["physical_metadata"]


@pytest.mark.django_db(databases="__all__")
def test_query_physical_storage_metadata_escapes_identifiers(doris_storage, mocker):
    doris_binding = build_doris_binding(storage_config={"db": "maple`leaf", "table": "bklog`table"})
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor()
    fake_connection = FakeDorisConnection(fake_cursor)
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    doris_storage.query_physical_storage_metadata()

    assert fake_cursor.execute_calls[-1][0] == "SHOW CREATE TABLE `maple``leaf`.`bklog``table`"


@pytest.mark.django_db(databases="__all__")
def test_query_latest_physical_storage_records_queries_latest_rows(doris_storage, mocker):
    doris_binding = build_doris_binding(
        annotations={
            "PhysicalTableName": "mapleleaf_2.bklog_2_test_2",
            "index0": "ResultTable/bklog/bklog_2_test",
        }
    )
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor(
        fetchall_results=[
            [
                {"dtEventTimeStamp": "2026-05-11 10:00:00", "log": "latest"},
                {"dtEventTimeStamp": "2026-05-11 09:59:00", "log": "previous"},
            ]
        ]
    )
    fake_connection = FakeDorisConnection(fake_cursor)
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    result = doris_storage.query_latest_physical_storage_records(limit=2)

    assert result["limit"] == 2
    assert result["order_field"] == "dtEventTimeStamp"
    assert result["records"] == [
        {"dtEventTimeStamp": "2026-05-11 10:00:00", "log": "latest"},
        {"dtEventTimeStamp": "2026-05-11 09:59:00", "log": "previous"},
    ]
    assert fake_connection.closed is True
    assert fake_cursor.execute_calls == [
        (
            "SELECT * FROM `mapleleaf_2`.`bklog_2_test_2` ORDER BY `dtEventTimeStamp` DESC LIMIT %s",
            (2,),
        )
    ]
    assert result["errors"] == []


@pytest.mark.django_db(databases="__all__")
def test_query_latest_physical_storage_records_uses_origin_storage_for_virtual_table(virtual_doris_storage, mocker):
    doris_binding = build_doris_binding(
        annotations={
            "PhysicalTableName": "mapleleaf_2.bklog_2_test_2",
            "index0": "ResultTable/bklog/bklog_2_test",
        }
    )
    mock_component_config = mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor(fetchall_results=[[{"dtEventTimeStamp": "2026-05-11 10:00:00", "log": "latest"}]])
    fake_connection = FakeDorisConnection(fake_cursor)
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    result = virtual_doris_storage.query_latest_physical_storage_records()

    assert result["request_table_id"] == "2_bklog.virtual"
    assert result["doris_storage"]["table_id"] == "2_bklog.test"
    assert result["physical_table"]["physical_table_name"] == "mapleleaf_2.bklog_2_test_2"
    assert result["records"] == [{"dtEventTimeStamp": "2026-05-11 10:00:00", "log": "latest"}]
    assert mock_component_config.call_count == 1
    assert fake_cursor.execute_calls == [
        (
            "SELECT * FROM `mapleleaf_2`.`bklog_2_test_2` ORDER BY `dtEventTimeStamp` DESC LIMIT %s",
            (1,),
        )
    ]


@pytest.mark.django_db(databases="__all__")
def test_query_latest_physical_storage_records_caps_limit_and_escapes_order_field(doris_storage, mocker):
    doris_binding = build_doris_binding(storage_config={"db": "maple`leaf", "table": "bklog`table"})
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    fake_cursor = FakeDorisCursor(fetchall_results=[[{"log": "latest"}]])
    fake_connection = FakeDorisConnection(fake_cursor)
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=fake_connection)

    result = doris_storage.query_latest_physical_storage_records(limit=1000, order_field="time`field")

    assert result["limit"] == 100
    assert fake_cursor.execute_calls == [
        ("SELECT * FROM `maple``leaf`.`bklog``table` ORDER BY `time``field` DESC LIMIT %s", (100,))
    ]


@pytest.mark.django_db(databases="__all__")
def test_query_latest_physical_storage_records_returns_error_when_order_field_empty(doris_storage, mocker):
    doris_binding = build_doris_binding(storage_config={"db": "mapleleaf_2", "table": "bklog_2_test_2"})
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        return_value=doris_binding,
    )
    mock_connect = mocker.patch("metadata.models.storage.pymysql.connect")

    result = doris_storage.query_latest_physical_storage_records(order_field="")

    assert result["records"] == []
    assert result["errors"][0]["code"] == "DORIS_LATEST_RECORDS_QUERY_FAILED"
    mock_connect.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_query_physical_storage_metadata_keeps_base_info_when_binding_query_fails(doris_storage, mocker):
    mocker.patch(
        "metadata.models.data_link.data_link_configs.DorisStorageBindingConfig.component_config",
        new_callable=PropertyMock,
        side_effect=ValueError("remote metadata unavailable"),
    )
    mock_connect = mocker.patch("metadata.models.storage.pymysql.connect")

    result = doris_storage.query_physical_storage_metadata()

    assert result["doris_storage"]["table_id"] == "2_bklog.test"
    assert result["storage_cluster"]["cluster_id"] == 1001
    assert result["physical_metadata"] == {}
    assert result["errors"][0]["code"] == "DORIS_BINDING_METADATA_QUERY_FAILED"
    mock_connect.assert_not_called()


# ------------------------- 日志 Doris 物理表替换（一期） ------------------------- #

LOG_DORIS_TABLE_ID = "2_bklog.rotate_test"
LOG_DORIS_OPTION_VALUE = {
    "clean_rules": [
        {
            "input_id": "log",
            "output_id": "log",
            "operator": {"type": "assign", "key_index": "log", "output_type": "string"},
        }
    ],
    "doris_storage_config": {
        "storage_keys": ["dtEventTimeStamp"],
        "json_fields": ["json_body"],
        "field_config_group": {"search_zh": ["log"]},
        "tokenizers": {"log": "./=:"},
    },
}


def _get_datalink_data_biz_id(bk_biz_id: int) -> int:
    from bkmonitor.utils.tenant import get_tenant_datalink_biz_id

    return get_tenant_datalink_biz_id(bk_tenant_id="system", bk_biz_id=bk_biz_id).data_biz_id


@pytest.fixture
def log_doris_records():
    """搭建日志 Doris 换表所需的最小记录：RT、DorisStorage、option、字段。"""
    bk_tenant_id = "system"
    bk_biz_id = 2
    cluster, _ = models.ClusterInfo.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        cluster_id=2101,
        defaults={
            "cluster_name": "doris_rotate",
            "cluster_type": models.ClusterInfo.TYPE_DORIS,
            "domain_name": "doris.rotate",
            "port": 9030,
            "description": "",
            "is_default_cluster": False,
            "version": "2.1",
        },
    )
    models.ResultTable.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=LOG_DORIS_TABLE_ID,
        defaults={
            "table_name_zh": LOG_DORIS_TABLE_ID,
            "is_custom_table": True,
            "default_storage": models.ClusterInfo.TYPE_DORIS,
            "creator": "system",
            "last_modify_user": "system",
            "bk_biz_id": bk_biz_id,
            "is_enable": True,
        },
    )
    # 只有关联了数据源的结果表才拥有写入链路。
    data_source, _ = models.DataSource.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=81921,
        defaults={
            "data_name": "log_doris_rotate",
            "mq_cluster_id": 1,
            "mq_config_id": 1,
            "etl_config": "bk_log_text",
            "is_custom_source": False,
        },
    )
    models.DataSourceResultTable.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        bk_data_id=data_source.bk_data_id,
        table_id=LOG_DORIS_TABLE_ID,
        defaults={"creator": "system"},
    )
    storage, _ = models.DorisStorage.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=LOG_DORIS_TABLE_ID,
        defaults={
            "storage_cluster_id": cluster.cluster_id,
            "source_type": "log",
            "table_type": models.DorisStorage.PRIMARY_TABLE_TYPE,
            "expire_days": 30,
        },
    )
    models.ResultTableOption.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=LOG_DORIS_TABLE_ID,
        name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        defaults={
            "value": json.dumps(LOG_DORIS_OPTION_VALUE),
            "value_type": models.ResultTableOption.TYPE_STRING,
            "creator": "system",
        },
    )
    models.ResultTableField.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=LOG_DORIS_TABLE_ID,
        field_name="log",
        defaults={
            "field_type": models.ResultTableField.FIELD_TYPE_STRING,
            "tag": models.ResultTableField.FIELD_TAG_METRIC,
            "is_config_by_user": True,
            "creator": "system",
            "last_modify_user": "system",
        },
    )
    yield {"bk_tenant_id": bk_tenant_id, "bk_biz_id": bk_biz_id, "storage": storage}

    models.ResultTableOption.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.DataSourceResultTable.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.DataSource.objects.filter(bk_data_id=81921).delete()
    models.ResultTableField.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.DorisStorage.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.ResultTable.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()
    models.ClusterInfo.objects.filter(cluster_id=2101).delete()


def _sync_log_physical_table(ctx, **kwargs):
    return models.DorisStorage.sync_log_physical_table(
        bk_tenant_id=ctx["bk_tenant_id"],
        table_id=LOG_DORIS_TABLE_ID,
        bk_biz_id=ctx["bk_biz_id"],
        **kwargs,
    )


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_creates_first_version(log_doris_records):
    """首次接入：产出 _v1 表名，bkbase_table_id 为 {data_biz_id}_{rt_name}。"""
    ctx = log_doris_records
    old_option = dict(LOG_DORIS_OPTION_VALUE)

    rt_name = _sync_log_physical_table(ctx, previous_option_value=old_option)

    data_biz_id = _get_datalink_data_biz_id(ctx["bk_biz_id"])
    assert rt_name.endswith("_v1")
    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.physical_tables == {"main": f"mapleleaf_{data_biz_id}.{rt_name}"}
    assert storage.bkbase_table_id == f"{data_biz_id}_{rt_name}"

    segment = models.StorageClusterRecord.objects.get(table_id=LOG_DORIS_TABLE_ID, is_current=True)
    assert segment.physical_tables == {"main": f"mapleleaf_{data_biz_id}.{rt_name}"}
    assert segment.bkbase_table_id == f"{data_biz_id}_{rt_name}"


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_is_idempotent(log_doris_records):
    """同一份配置重复调用不会重复换表。"""
    ctx = log_doris_records
    first = _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))
    second = _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))

    assert first == second
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 1


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_rotates_on_tokenizer_change(log_doris_records):
    """建表配置变化：版本 +1，并新开一条存储分段，旧分段保留并关闭。"""
    ctx = log_doris_records
    first_name = _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))

    new_option = json.loads(json.dumps(LOG_DORIS_OPTION_VALUE))
    new_option["doris_storage_config"]["tokenizers"] = {"log": "./=:,|"}
    second_name = _sync_log_physical_table(
        ctx,
        option_value=new_option,
        previous_option_value=dict(LOG_DORIS_OPTION_VALUE),
    )

    data_biz_id = _get_datalink_data_biz_id(ctx["bk_biz_id"])
    assert second_name.endswith("_v2")
    assert second_name != first_name

    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.physical_tables == {"main": f"mapleleaf_{data_biz_id}.{second_name}"}
    assert storage.bkbase_table_id == f"{data_biz_id}_{second_name}"

    segments = list(
        models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).order_by("enable_time", "id")
    )
    assert len(segments) == 2
    assert segments[0].is_current is False
    assert segments[0].disable_time is not None
    assert segments[1].is_current is True
    assert segments[1].bkbase_table_id == f"{data_biz_id}_{second_name}"


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_rotates_on_field_type_change(log_doris_records):
    """同名字段类型变化触发换表。"""
    ctx = log_doris_records
    _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))

    models.ResultTableField.objects.filter(table_id=LOG_DORIS_TABLE_ID, field_name="log").update(field_type="text")
    rt_name = _sync_log_physical_table(
        ctx,
        previous_option_value=dict(LOG_DORIS_OPTION_VALUE),
        previous_field_types={"log": models.ResultTableField.FIELD_TYPE_STRING},
    )

    assert rt_name.endswith("_v2")


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_ignores_field_add_or_remove(log_doris_records):
    """字段新增 / 删除不触发换表，非建表配置变化同样不换表。"""
    ctx = log_doris_records
    first_name = _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))

    models.ResultTableField.objects.create(
        bk_tenant_id=ctx["bk_tenant_id"],
        table_id=LOG_DORIS_TABLE_ID,
        field_name="path",
        field_type=models.ResultTableField.FIELD_TYPE_STRING,
        tag=models.ResultTableField.FIELD_TAG_DIMENSION,
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )
    new_option = json.loads(json.dumps(LOG_DORIS_OPTION_VALUE))
    new_option["doris_storage_config"]["flush_timeout"] = 30

    second_name = _sync_log_physical_table(
        ctx,
        option_value=new_option,
        previous_option_value=dict(LOG_DORIS_OPTION_VALUE),
        previous_field_types={"log": models.ResultTableField.FIELD_TYPE_STRING},
    )

    assert second_name == first_name
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 1


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_adopts_existing_table(log_doris_records):
    """已有表（历史链路）不换名、不加后缀，只补齐物理表与结果表记录。"""
    ctx = log_doris_records
    binding_name = "bklog_legacy_link"
    models.DorisStorageBindingConfig.objects.update_or_create(
        bk_tenant_id=ctx["bk_tenant_id"],
        table_id=LOG_DORIS_TABLE_ID,
        defaults={
            "name": binding_name,
            "namespace": "bklog",
            "data_link_name": "bklog_legacy_link",
            "bk_biz_id": ctx["bk_biz_id"],
            "status": "Ok",
            "bkbase_result_table_name": binding_name,
            "doris_cluster_name": "doris_rotate",
        },
    )

    rt_name = _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE))

    data_biz_id = _get_datalink_data_biz_id(ctx["bk_biz_id"])
    assert rt_name == binding_name
    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.physical_tables == {"main": f"mapleleaf_{data_biz_id}.{binding_name}_{data_biz_id}"}
    assert storage.bkbase_table_id == f"{data_biz_id}_{binding_name}"


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_skips_when_doris_is_not_default(log_doris_records):
    """Doris 不是默认存储时（双写场景）不写分段。"""
    ctx = log_doris_records
    models.ResultTable.objects.filter(table_id=LOG_DORIS_TABLE_ID).update(default_storage="elasticsearch")

    assert _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE)) is None
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 0


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_skips_virtual_storage(log_doris_records):
    """路由表 / 虚拟表：物理表与结果表归属实体表，不在这里产出。"""
    ctx = log_doris_records
    models.DorisStorage.objects.filter(table_id=LOG_DORIS_TABLE_ID).update(origin_table_id="2_bklog.entity")

    assert _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE)) is None
    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.bkbase_table_id in (None, "")
    assert storage.physical_tables == {}
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 0


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_skips_third_party_storage(log_doris_records):
    """第三方虚拟表（不需要创建后续链路）：不覆盖已有的 bkbase_table_id 与物理表。"""
    ctx = log_doris_records
    models.DorisStorage.objects.filter(table_id=LOG_DORIS_TABLE_ID).update(
        source_type="es",
        bkbase_table_id="2_third_party_rt",
        physical_tables={"main": "mapleleaf_2.third_party_table"},
    )

    assert _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE)) is None
    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.bkbase_table_id == "2_third_party_rt"
    assert storage.physical_tables == {"main": "mapleleaf_2.third_party_table"}
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 0


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_skips_table_without_datasource(log_doris_records):
    """没有数据源关联的查询路由表不创建后续链路，不产出物理表与结果表名。"""
    ctx = log_doris_records
    models.DataSourceResultTable.objects.filter(table_id=LOG_DORIS_TABLE_ID).delete()

    assert _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE)) is None
    storage = models.DorisStorage.objects.get(table_id=LOG_DORIS_TABLE_ID)
    assert storage.bkbase_table_id in (None, "")
    assert storage.physical_tables == {}
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 0


@pytest.mark.django_db(databases="__all__")
def test_sync_log_physical_table_skips_virtual_table_option(log_doris_records):
    """显式标记为虚拟结果表的表只参与查询，同样不产出物理表。"""
    ctx = log_doris_records
    models.ResultTableOption.objects.update_or_create(
        bk_tenant_id=ctx["bk_tenant_id"],
        table_id=LOG_DORIS_TABLE_ID,
        name=models.ResultTableOption.OPTION_IS_VIRTUAL_TABLE,
        defaults={
            "value": "true",
            "value_type": models.ResultTableOption.TYPE_BOOL,
            "creator": "system",
        },
    )

    assert _sync_log_physical_table(ctx, previous_option_value=dict(LOG_DORIS_OPTION_VALUE)) is None
    assert models.StorageClusterRecord.objects.filter(table_id=LOG_DORIS_TABLE_ID).count() == 0
