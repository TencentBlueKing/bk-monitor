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
