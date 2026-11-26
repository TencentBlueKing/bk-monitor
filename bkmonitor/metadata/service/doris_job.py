"""DataLink 的本地 DorisJob 管理与单次调谐。只有调谐任务执行 DDL。"""

from contextlib import ExitStack, closing

import pymysql
from django.db import transaction

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.doris_job import DorisJobConfig
from metadata.models.storage import ClusterInfo


def connect(job):
    return connect_cluster(job.data_link.bk_tenant_id, job.cluster_id)


def connect_cluster(tenant, cluster_id):
    cluster = ClusterInfo.objects.get(bk_tenant_id=tenant, cluster_id=cluster_id, cluster_type=ClusterInfo.TYPE_DORIS)
    return pymysql.connect(
        host=cluster.domain_name,
        port=int(cluster.port),
        user=cluster.username,
        password=cluster.password,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=15,
        write_timeout=15,
    )


def check_dependencies(job, cursor):
    """每轮读取组件最新状态和 FE 表目录。短暂缺表保留 pending，下一轮继续；
    SET_NULL 后仍保留 component_kind，因此删除引用与尚未就绪可以分别处理。
    暂停、删除只依赖已绑定的 FE Job，允许在上游离线时执行。
    """
    if job.pending_action not in ("create", "resume"):
        return ""
    for edge in job.table_relations.select_related("result_table", "doris_binding"):
        component = edge.result_table or edge.doris_binding
        if edge.component_kind and not component:
            raise ValueError(f"{edge.direction} 组件已删除，请重新配置")
        if component and component.status != DataLinkResourceStatus.OK.value:
            return f"{component.kind}/{component.name}: {component.status}"
        if edge.table:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
                (edge.database, edge.table),
            )
            if cursor.fetchone() is None:
                return f"等待物理表 {edge.database}.{edge.table}"
    return ""


def remote_job(cursor, name):
    cursor.execute('SELECT * FROM jobs("type"="insert") WHERE Name=%s', (name,))
    return cursor.fetchone()


def _finish(job):
    """ready 表示管理动作完成。DROP 后保留配置作为可编辑草稿。"""
    job.reconcile_status = "ready" if job.remote_id is not None else "draft"
    job.pending_action = job.status_reason = ""


def _observed(job, remote):
    """先观察远端绑定。相同名称可以被重建，不能据此认领其他 Job。"""
    if remote and int(remote["Id"]) != job.remote_id:
        raise ValueError(f"存在同名 Job，远端 ID 为 {remote['Id']}，请核对归属")
    if job.pending_action == "drop":
        return remote is None
    if job.pending_action == "create":
        return False
    if remote is None:
        raise ValueError(f"远端 Job {job.remote_id} 已不存在")
    return remote["Status"] == {"pause": "PAUSED", "resume": "RUNNING"}[job.pending_action]


def _execute_ddl(job, connection, cursor):
    action = job.pending_action
    if action == "create":
        connection.select_db(job.database)
        name = job.name.replace("`", "``")
        cursor.execute(f"CREATE JOB `{name}` ON SCHEDULE EVERY {job.interval_minutes:d} MINUTE DO {job.insert_sql}")
        remote = remote_job(cursor, job.name)
        if remote is None:
            raise ValueError("FE 已接受 CREATE，但未返回 Job ID，请核实后接管")
        job.remote_id = int(remote["Id"])
    else:
        cursor.execute(f"{action.upper()} JOB WHERE jobName=%s", (job.name,))
        if action == "drop":
            job.remote_id = None
    _finish(job)


def _record_error(job, error):
    # 读请求断线保留 pending；DDL 断线保留 verifying，后者只能回读结果。
    if not (isinstance(error, pymysql.MySQLError) and error.args and error.args[0] in (2002, 2003, 2006, 2013)):
        job.reconcile_status = "failed"
    job.status_reason = str(error)


def _save_state(job):
    job.save(update_fields=["reconcile_status", "pending_action", "status_reason", "remote_id", "last_modify_time"])


def reconcile_job(job_id):
    """领取一次发送权，再执行 FE DDL。两个本地事务之间的提交是崩溃恢复边界。"""
    with ExitStack() as resources:
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            job = (
                DorisJobConfig.objects.select_for_update()
                .filter(pk=job_id, reconcile_status__in=("pending", "verifying"))
                .first()
            )
            if not job:
                return
            try:
                connection = resources.enter_context(closing(connect(job)))
                cursor = resources.enter_context(connection.cursor())
                remote = remote_job(cursor, job.name)
                if _observed(job, remote):
                    if job.pending_action == "drop":
                        job.remote_id = None
                    _finish(job)
                elif job.reconcile_status == "verifying":
                    # 可能仍有 FE 请求在执行。结果不可见时继续观察，绝不自动补发。
                    return
                else:
                    reason = check_dependencies(job, cursor)
                    if reason:
                        job.status_reason = reason
                    else:
                        job.reconcile_status = "verifying"
                        job.status_reason = "等待确认 FE 动作结果；若 worker 中断且结果长期不可见，请核实后显式重试"
            except (pymysql.MySQLError, ValueError, ClusterInfo.DoesNotExist) as error:
                _record_error(job, error)
                if job.reconcile_status != "verifying":
                    _save_state(job)
                return
            _save_state(job)
            if job.reconcile_status != "verifying":
                return
            claimed_at = job.last_modify_time

        # 提交发送意图后才允许执行 DDL。即使 FE 成功后进程退出或回写失败，
        # 下一轮也只会观察；若管理员核实后已显式重试，旧 worker 放弃原发送权。
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            job = (
                DorisJobConfig.objects.select_for_update()
                .filter(
                    pk=job_id,
                    reconcile_status="verifying",
                    last_modify_time=claimed_at,
                )
                .first()
            )
            if not job:
                return
            try:
                _execute_ddl(job, connection, cursor)
            except (pymysql.MySQLError, ValueError) as error:
                _record_error(job, error)
            _save_state(job)


@transaction.atomic(using=DATABASE_CONNECTION_NAME)
def request_action(tenant, job_id, action):
    job = DorisJobConfig.objects.select_for_update().get(pk=job_id, data_link__bk_tenant_id=tenant)
    if action == "cancel":
        if job.reconcile_status not in ("pending", "failed"):
            raise ValueError("只有待执行或失败的请求可以撤销")
        job.reconcile_status = "ready" if job.remote_id is not None else "draft"
        job.pending_action = ""
    else:
        if action == "retry":
            if job.reconcile_status not in ("failed", "verifying"):
                raise ValueError("只有失败或等待确认的动作可以重试")
            action = job.pending_action
        elif job.reconcile_status == "verifying":
            raise ValueError("正在确认 FE 动作结果")
        if job.reconcile_status == "pending":
            if job.pending_action == action:
                return job
            raise ValueError("已有待执行动作")
        if action == "create" and job.remote_id is not None:
            return job
        if action not in ("create", "pause", "resume", "drop") or (action != "create" and job.remote_id is None):
            raise ValueError("当前配置无法执行该动作")
        job.reconcile_status = "pending"
        job.pending_action = action
    job.status_reason = ""
    job.save(update_fields=["reconcile_status", "pending_action", "status_reason", "last_modify_time"])
    return job
