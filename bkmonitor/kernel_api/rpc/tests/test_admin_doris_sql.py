from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from kernel_api.rpc.functions.admin import doris_sql


@pytest.mark.parametrize(
    "sql,changes",
    [
        ("SELECT 1", False),
        ("SELECT 1 /*! INTO OUTFILE 'a' */", True),
        ('-- comment\n SELECT ";DROP TABLE x"', False),
        ("WITH a AS (SELECT 1) SELECT * FROM a", False),
        ("SHOW TABLES", False),
        ("DESC db.table", False),
        ('SELECT * FROM a INTO OUTFILE "s3://bucket/a"', True),
        ("DELETE FROM a", True),
        ("CREATE TABLE a (id INT)", True),
        ("EXPLAIN SELECT 1", True),
        ("SET query_timeout = 100", True),
    ],
)
def test_classification(sql, changes):
    assert doris_sql.classify_sql(sql)[1] == changes


@pytest.mark.parametrize("sql", ["", ";", "--comment", "SELECT 1; DROP TABLE a", "SELECT 1; SELECT 2"])
def test_multiple_or_empty_statements_rejected(sql):
    with pytest.raises(Exception):
        doris_sql.classify_sql(sql)


@pytest.fixture
def cluster():
    with patch.object(doris_sql.models.ClusterInfo, "objects") as manager:
        manager.get.return_value = SimpleNamespace(domain_name="localhost", port=9030, username="u", password="p")
        yield manager


def test_changes_require_confirmation_and_readonly_rejects(cluster):
    params = {"cluster_id": 40, "sql": "DROP TABLE db.a", "readonly": False}
    with patch.object(doris_sql.pymysql, "connect") as connect:
        result = doris_sql.execute_doris_sql(params)
        assert result["data"]["status"] == "confirmation_required"
        connect.assert_not_called()
        with pytest.raises(Exception, match="只读"):
            doris_sql.execute_doris_sql({**params, "readonly": True, "confirmed": True})
        connect.assert_not_called()


def test_streaming_query_truncates_and_preserves_duplicate_column_names(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = [("value",), ("value",)]
    cursor.fetchmany.return_value = [(1, 9007199254740993), (2, None), (3, "hidden")]
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        result = doris_sql.execute_doris_sql(
            {"bk_tenant_id": "tenant-a", "cluster_id": 40, "sql": "SELECT * FROM a", "max_rows": 2, "readonly": True}
        )["data"]
    assert result["rows"] == [[1, "9007199254740993"], [2, None]]
    assert result["columns"] == ["value", "value"]
    assert result["truncated"] is True
    connection.close.assert_called_once()
    cluster.get.assert_called_once_with(bk_tenant_id="tenant-a", cluster_id=40, cluster_type="doris")


def test_confirmed_write_executes_once_and_returns_affected_rows(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = None
    cursor.rowcount = 12
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        result = doris_sql.execute_doris_sql(
            {"cluster_id": 40, "sql": "DELETE FROM a", "confirmed": True, "readonly": False}
        )["data"]
    assert result["affected_rows"] == 12
    assert cursor.execute.call_args_list[-1].args == ("DELETE FROM a",)
    connection.close.assert_called_once()


def test_sql_error_is_reported_without_retry_and_connection_closed(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.execute.side_effect = [None, doris_sql.pymysql.ProgrammingError(1064, "syntax error")]
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        with pytest.raises(Exception, match="syntax error"):
            doris_sql.execute_doris_sql({"cluster_id": 40, "sql": "SELECT invalid", "readonly": True})
    assert cursor.execute.call_count == 2
    connection.close.assert_called_once()
