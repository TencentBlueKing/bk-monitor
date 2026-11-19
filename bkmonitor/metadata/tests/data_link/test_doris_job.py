from unittest.mock import MagicMock

import pymysql
import pytest

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import DataLink, DorisJobConfig, ResultTableConfig
from metadata.models.storage import ClusterInfo
from metadata.service.doris_job import reconcile_job, request_action
from metadata.service.doris_job_config import render_configs, save_configs
from metadata.task.tasks import reconcile_doris_jobs

pytestmark = pytest.mark.django_db(databases=[DATABASE_CONNECTION_NAME])


@pytest.fixture
def job():
    link = DataLink.objects.create(data_link_name="job_link", bk_tenant_id="system")
    ClusterInfo.objects.create(
        cluster_id=42,
        cluster_name="doris",
        cluster_type="doris",
        bk_tenant_id="system",
        domain_name="localhost",
        port=9030,
        is_default_cluster=False,
    )
    source = ResultTableConfig.objects.create(name="src", status="Pending", bk_tenant_id="system", bk_biz_id=2)
    ids = save_configs(
        "system",
        link.pk,
        {
            "cluster_id": 42,
            "name": "rollup",
            "database": "agg",
            "interval_minutes": 5,
            "insert_sql": "INSERT INTO dst SELECT * FROM src",
            "sources": {"src": {"kind": "ResultTable", "id": source.pk}},
            "targets": {"dst": {"database": "agg", "table": "dst"}},
        },
    )
    return DorisJobConfig.objects.get(pk=ids[0])


@pytest.fixture
def fe(mocker):
    connection = MagicMock()
    mocker.patch("metadata.service.doris_job.connect", return_value=connection)
    return connection.cursor.return_value.__enter__.return_value


def test_three_rounds(job, fe):
    request_action("system", job.pk, "create")
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert job.reconcile_status == "pending"
    assert "Pending" in job.status_reason
    fe.execute.assert_not_called()

    ResultTableConfig.objects.filter(name="src").update(status="Ok")
    fe.fetchone.side_effect = [{"1": 1}, None, {"Id": 77}]
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id, job.pending_action) == ("ready", 77, "")
    sql = [call.args[0] for call in fe.execute.call_args_list]
    assert len([statement for statement in sql if statement.startswith("CREATE JOB")]) == 1
    fe.reset_mock()
    reconcile_doris_jobs.run()
    fe.execute.assert_not_called()


def test_conflict_and_transient_error(job, fe):
    ResultTableConfig.objects.update(status="Ok")
    request_action("system", job.pk, "create")
    fe.execute.side_effect = pymysql.OperationalError(2013, "lost connection")
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert job.reconcile_status == "pending"
    fe.execute.side_effect = None
    fe.fetchone.side_effect = [{"1": 1}, {"Id": 9}]
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert job.reconcile_status == "failed"
    assert "同名" in job.status_reason
    assert job.remote_id is None


def test_pause_and_drop_while_dependency_unavailable(job, fe):
    job.remote_id, job.reconcile_status = 77, "ready"
    job.save()
    fe.fetchone.return_value = {"Id": 77, "Status": "PAUSED"}
    request_action("system", job.pk, "pause")
    reconcile_job(job.pk)
    assert fe.execute.call_count == 1
    request_action("system", job.pk, "drop")
    reconcile_job(job.pk)
    fe.execute.assert_called_with("DROP JOB WHERE jobName=%s", (job.name,))
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id, job.table_relations.count()) == ("draft", None, 2)


def test_template_per_output():
    config = dict(
        template_key="window_projection",
        name="copy",
        sources={"s": {"database": "raw", "table": "src"}},
        targets={
            "a": {"source": "s", "database": "agg", "table": "a"},
            "b": {"source": "s", "database": "agg", "table": "b"},
        },
        params={"time_column": "ts", "columns": ["ts", "value"], "lookback_minutes": 5},
    )
    first, second = render_configs(config)
    assert first["name"] == "copy_a"
    assert list(second["targets"]) == ["b"]
    assert "INSERT INTO `agg`.`b`" in second["insert_sql"]
    assert "FROM `raw`.`src`" in second["insert_sql"]
