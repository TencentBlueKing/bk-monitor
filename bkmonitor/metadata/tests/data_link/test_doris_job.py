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
    fe.fetchone.return_value = None
    request_action("system", job.pk, "create")
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert job.reconcile_status == "pending"
    assert "Pending" in job.status_reason
    assert fe.execute.call_count == 1  # 仅观察远端，尚未发送 DDL

    ResultTableConfig.objects.filter(name="src").update(status="Ok")
    fe.fetchone.side_effect = [None, {"1": 1}, {"Id": 77}]
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
    fe.fetchone.return_value = {"Id": 9}
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


def test_missing_target_visible_next_round(job, fe):
    ResultTableConfig.objects.update(status="Ok")
    request_action("system", job.pk, "create")
    # 第一轮目标表还未出现在 information_schema，第二轮 FE 才返回表和 Job。
    fe.fetchone.side_effect = [None, None, None, {"1": 1}, {"Id": 81}]
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert (job.reconcile_status, job.status_reason) == ("pending", "等待物理表 agg.dst")
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id) == ("ready", 81)


@pytest.mark.parametrize("action", ["create", "resume", "pause", "drop"])
def test_lost_ddl_response_is_observed_without_resending(job, fe, action):
    ResultTableConfig.objects.update(status="Ok")
    initial = None if action == "create" else {"Id": 77, "Status": "PAUSED" if action == "resume" else "RUNNING"}
    if initial:
        job.remote_id = 77
        job.reconcile_status = "ready"
        job.save()
    request_action("system", job.pk, action)
    fe.fetchone.side_effect = [initial, {"1": 1}]

    def lose_response(sql, *args):
        if sql.startswith(action.upper()):
            raise pymysql.OperationalError(2013, "DDL response lost")

    fe.execute.side_effect = lose_response
    reconcile_doris_jobs.run()
    job.refresh_from_db()
    assert job.reconcile_status == "verifying"

    # FE 可以先返回旧状态，稍后才对另一连接可见。依赖离线也不能阻止回读。
    ResultTableConfig.objects.update(status="Pending")
    observed = None if action == "drop" else {"Id": 77, "Status": "PAUSED" if action == "pause" else "RUNNING"}
    fe.fetchone.side_effect = [initial, observed]
    reconcile_doris_jobs.run()
    reconcile_doris_jobs.run()
    assert sum(call.args[0].startswith(action.upper()) for call in fe.execute.call_args_list) == 1
    job.refresh_from_db()
    assert job.reconcile_status == {"drop": "draft", "create": "failed"}.get(action, "ready")


def test_crash_before_metadata_writeback(job, fe, mocker):
    from metadata.service import doris_job

    ResultTableConfig.objects.update(status="Ok")
    request_action("system", job.pk, "create")
    fe.fetchone.side_effect = [None, {"1": 1}, {"Id": 77}, None, {"Id": 77}]
    save_state = doris_job._save_state

    def crash_on_success(record):
        if record.reconcile_status == "ready":
            raise RuntimeError("worker interrupted")
        save_state(record)

    mocker.patch.object(doris_job, "_save_state", side_effect=crash_on_success)
    with pytest.raises(RuntimeError, match="worker interrupted"):
        reconcile_job(job.pk)
    reconcile_job(job.pk)
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert job.reconcile_status == "failed"
    assert sum(call.args[0].startswith("CREATE JOB") for call in fe.execute.call_args_list) == 1


@pytest.mark.django_db(transaction=True, databases=[DATABASE_CONNECTION_NAME])
def test_overlapping_workers_send_one_create(job, fe):
    """使用两个独立事务，令第二个 worker 在第一个 FE 调用未返回时扫描同一条记录。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from django.db import connections

    if not connections[DATABASE_CONNECTION_NAME].features.has_select_for_update:
        pytest.skip("需要数据库行锁")
    ResultTableConfig.objects.update(status="Ok")
    request_action("system", job.pk, "create")
    entered, release, competing = Event(), Event(), Event()

    def execute(sql, *args):
        if sql.startswith("CREATE JOB"):
            entered.set()
            assert release.wait(10)

    def run_worker(contender=False):
        db = connections[DATABASE_CONNECTION_NAME]

        def observe_lock(execute, sql, params, many, context):
            if contender and "FOR UPDATE" in sql.upper():
                competing.set()
            return execute(sql, params, many, context)

        try:
            with db.execute_wrapper(observe_lock):
                reconcile_job(job.pk)
        finally:
            db.close()

    fe.execute.side_effect = execute
    fe.fetchone.side_effect = [None, {"1": 1}, {"Id": 77}]
    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(run_worker)
        try:
            assert entered.wait(10)
            second = workers.submit(run_worker, True)
            assert competing.wait(10)
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id) == ("ready", 77)
    assert sum(call.args[0].startswith("CREATE JOB") for call in fe.execute.call_args_list) == 1


def test_binding_and_source_progress_independently(job, fe):
    from metadata.models.data_link import DorisStorageBindingConfig

    binding = DorisStorageBindingConfig.objects.create(name="sink", status="Pending", bk_biz_id=2)
    edge = job.table_relations.get(direction="target")
    edge.doris_binding = binding
    edge.component_kind = "DorisBinding"
    edge.save()
    fe.fetchone.return_value = None
    request_action("system", job.pk, "create")
    reconcile_job(job.pk)
    ResultTableConfig.objects.update(status="Ok")
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert job.reconcile_status == "pending"
    assert binding.name in job.status_reason
    binding.status = "Ok"
    binding.save(update_fields=["status"])
    fe.fetchone.side_effect = [None, {"1": 1}, {"Id": 82}]
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id) == ("ready", 82)


def test_retry_after_operator_confirms_unsent_action(job, fe):
    # 模拟发送权已提交、worker 在发送前退出。自动恢复保持只读。
    job.reconcile_status, job.pending_action = "verifying", "create"
    job.save()
    fe.fetchone.return_value = None
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert job.reconcile_status == "verifying"
    with pytest.raises(ValueError, match="正在确认"):
        request_action("system", job.pk, "create")
    request_action("system", job.pk, "retry")
    ResultTableConfig.objects.update(status="Ok")
    fe.fetchone.side_effect = [None, {"1": 1}, {"Id": 88}]
    reconcile_job(job.pk)
    job.refresh_from_db()
    assert (job.reconcile_status, job.remote_id) == ("ready", 88)
    assert sum(call.args[0].startswith("CREATE JOB") for call in fe.execute.call_args_list) == 1
