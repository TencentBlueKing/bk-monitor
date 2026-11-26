from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from kernel_api.rpc.functions.admin import doris_jobs as jobs


@pytest.fixture
def runtime():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    connection = MagicMock()
    connection.cursor.return_value = cursor
    cluster = SimpleNamespace(domain_name="localhost", port=9030, username="u", password="p")
    with (
        patch.object(jobs.models.ClusterInfo, "objects") as objects,
        patch.object(jobs.pymysql, "connect", return_value=connection) as connect,
    ):
        objects.get.return_value = cluster
        yield cursor, connection, objects, connect


def params(**extra):
    return {"bk_tenant_id": "tenant-a", "cluster_id": 40, "job_type": "insert", **extra}


def test_jobs_page_uses_bound_filters_and_preserves_large_ids(runtime):
    cursor, connection, objects, _ = runtime
    cursor.fetchall.side_effect = [
        [{"version": "3.0.7"}],
        [{"total": 23}],
        [{"Id": 9007199254740993, "Name": "job", "Status": "RUNNING", "SucceedTaskCount": 0}],
    ]
    response = jobs.list_doris_jobs(params(page=2, page_size=20, state="RUNNING' OR 1=1 --"))
    assert response["data"]["total"] == 23
    assert response["data"]["items"][0]["id"] == "9007199254740993"
    assert response["data"]["items"][0]["success_count"] == 0
    sql, args = cursor.execute.call_args.args
    assert "RUNNING" not in sql
    assert args == ("RUNNING' OR 1=1 --", 20, 20)
    objects.get.assert_called_once_with(bk_tenant_id="tenant-a", cluster_id=40, cluster_type="doris")
    connection.close.assert_called_once()


def test_mv_tasks_filter_by_job_and_database(runtime):
    cursor, _, _, _ = runtime
    cursor.fetchall.side_effect = [
        [{"version": "3.0.7"}],
        [{"total": 1}],
        [{"TaskId": 9, "Status": "FAILED", "ErrorMsg": "failed"}],
    ]
    response = jobs.list_doris_tasks(params(job_type="mv", database="apm", job_id="123", job_name="mv"))
    sql, args = cursor.execute.call_args.args
    assert 'tasks("type"="mv") WHERE JobId = %s AND MvDatabaseName = %s' in sql
    assert "CreateTime DESC, TaskId DESC" in sql
    assert args == ("123", "apm", 20, 0)
    assert response["data"]["items"][0]["error"] == "failed"


def test_routine_streams_and_pages_without_returning_credentials(runtime):
    cursor, connection, _, _ = runtime
    cursor.fetchall.return_value = [{"version": "2.1.7"}]
    cursor.fetchmany.side_effect = [
        [
            {"Id": 1, "Name": "first", "State": "RUNNING"},
            {"Id": 2, "Name": "second", "State": "PAUSED"},
            {"Id": 3, "Name": "third", "State": "RUNNING", "CustomProperties": {"password": "secret"}},
        ],
        [],
    ]
    response = jobs.list_doris_jobs(
        params(job_type="routine_load", database="db`quoted", state="RUNNING", page=2, page_size=1)
    )
    assert response["data"]["total"] == 2
    assert [item["id"] for item in response["data"]["items"]] == ["3"]
    assert "secret" not in str(response)
    connection.select_db.assert_called_once_with("db`quoted")


def test_routine_tasks_are_bound_to_selected_job_id(runtime):
    cursor, _, _, _ = runtime
    cursor.fetchall.return_value = [{"version": "3.0"}]
    cursor.fetchmany.side_effect = [[{"JobId": 7, "TaskId": "a"}, {"JobId": 8, "TaskId": "b"}], []]
    result = jobs.list_doris_tasks(params(job_type="routine_load", database="db", job_id="8", job_name="same_name"))
    assert [row["id"] for row in result["data"]["items"]] == ["b"]
    assert "当前子任务" in result["data"]["scope"]
    cursor.execute.assert_called_with("SHOW ROUTINE LOAD TASK WHERE JobName = %s", ("same_name",))


def test_unsupported_query_is_error_not_empty_result_and_closes_connection(runtime):
    cursor, connection, _, _ = runtime
    cursor.execute.side_effect = pymysql.ProgrammingError(1105, "unknown table function")
    with pytest.raises(Exception, match="版本是否支持及账号权限"):
        jobs.list_doris_jobs(params())
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "extra",
    [
        {"bk_tenant_id": ""},
        {"job_type": "other"},
        {"job_type": "routine_load"},
        {"database": "db"},
        {"page_size": 101},
        {"page": 0},
    ],
)
def test_invalid_request_does_not_connect(runtime, extra):
    with pytest.raises(Exception):
        jobs.list_doris_jobs(params(**extra))
    runtime[3].assert_not_called()
