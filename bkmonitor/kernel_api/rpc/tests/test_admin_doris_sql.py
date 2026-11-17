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


@pytest.mark.parametrize("sql", ["", ";", "--comment"])
def test_empty_statements_rejected(sql):
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


@pytest.mark.parametrize(
    "sql,changes",
    [
        ("SELECT 1; SELECT 2;", False),
        ("SET time_zone = 'Asia/Shanghai'; WITH a AS (SELECT 1) SELECT * FROM a;", True),
        ("DELETE FROM a; SELECT 1", True),
        ("SELECT ';'; -- trailing comment", False),
    ],
)
def test_script_classification(sql, changes):
    assert doris_sql.classify_sql(sql) == ("SELECT", changes)


def test_script_confirmation_covers_all_statements(cluster):
    params = {"cluster_id": 40, "sql": "DELETE FROM a; SELECT 1", "readonly": False}
    with patch.object(doris_sql.pymysql, "connect") as connect:
        assert doris_sql.execute_doris_sql(params)["data"]["status"] == "confirmation_required"
        with pytest.raises(Exception, match="只读"):
            doris_sql.execute_doris_sql({**params, "readonly": True, "confirmed": True})
        connect.assert_not_called()


def test_session_script_uses_same_connection_and_returns_last_result(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = [("missing_start",)]
    cursor.fetchmany.side_effect = [[], [("2026-11-14 08:00:00",)]]
    sql = "SET time_zone = 'Asia/Shanghai'; WITH a AS (SELECT 1) SELECT * FROM a;"
    with patch.object(doris_sql.pymysql, "connect", return_value=connection) as connect:
        result = doris_sql.execute_doris_sql({"cluster_id": 40, "sql": sql, "readonly": False, "confirmed": True})[
            "data"
        ]
    connect.assert_called_once()
    assert [call.args[0].strip() for call in cursor.execute.call_args_list] == [
        "SET query_timeout = 30",
        "SET time_zone = 'Asia/Shanghai';",
        "WITH a AS (SELECT 1) SELECT * FROM a;",
    ]
    assert result["rows"] == [["2026-11-14 08:00:00"]]
    assert result["statement_type"] == "SELECT"
    connection.close.assert_called_once()


def test_intermediate_streaming_results_are_drained(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = [("value",)]
    cursor.fetchmany.side_effect = [[(1,)], [], [(2,)]]
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        result = doris_sql.execute_doris_sql({"cluster_id": 40, "sql": "SELECT 1; SELECT 2", "readonly": True})["data"]
    assert result["rows"] == [[2]]
    assert cursor.fetchmany.call_count == 3


def test_script_stops_at_first_failure(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = None
    cursor.execute.side_effect = [None, None, doris_sql.pymysql.ProgrammingError(1064, "bad SQL")]
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        with pytest.raises(Exception, match="第 2/3 条语句执行失败"):
            doris_sql.execute_doris_sql(
                {"cluster_id": 40, "sql": "SELECT 1; SELECT invalid; SELECT 3", "readonly": True}
            )
    assert cursor.execute.call_count == 3
    connection.close.assert_called_once()


def test_last_result_read_failure_reports_statement_and_closes_connection(cluster):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.description = [("value",)]
    cursor.fetchmany.side_effect = [[], doris_sql.pymysql.OperationalError(2013, "connection lost")]
    with patch.object(doris_sql.pymysql, "connect", return_value=connection):
        with pytest.raises(Exception, match="第 2/2 条语句执行失败"):
            doris_sql.execute_doris_sql({"cluster_id": 40, "sql": "SELECT 1; SELECT 2", "readonly": True})
    connection.close.assert_called_once()
