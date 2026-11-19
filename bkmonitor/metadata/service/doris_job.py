"""DataLink 的本地 DorisJob 管理与单次调谐。只有调谐任务执行 DDL。"""

from contextlib import closing

import pymysql
from django.db import transaction

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.data_link.doris_job import DorisJobConfig
from metadata.models.storage import ClusterInfo


def connect(job):
    cluster = ClusterInfo.objects.get(
        bk_tenant_id=job.data_link.bk_tenant_id, cluster_id=job.cluster_id, cluster_type=ClusterInfo.TYPE_DORIS
    )
    return pymysql.connect(
        host=cluster.domain_name,
        port=int(cluster.port),
        user=cluster.username,
        password=cluster.password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=15,
        write_timeout=15,
    )


def check_dependencies(job, cursor):
    """返回待就绪的依赖说明；空字符串表示可以执行。"""
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


def apply_action(job, connection):
    action = job.pending_action
    with connection.cursor() as cursor:
        reason = check_dependencies(job, cursor)
        if reason:
            job.status_reason = reason
            return
        remote = remote_job(cursor, job.name)
        if remote and int(remote["Id"]) != job.remote_id:
            raise ValueError(f"存在同名 Job，远端 ID 为 {remote['Id']}，请核对归属")
        if action == "create":
            connection.select_db(job.database)
            name = job.name.replace("`", "``")
            cursor.execute(f"CREATE JOB `{name}` ON SCHEDULE EVERY {job.interval_minutes:d} MINUTE DO {job.insert_sql}")
            remote = remote_job(cursor, job.name)
            if remote is None:
                raise ValueError("FE 已接受 CREATE，但未返回 Job ID，请核实后接管")
            job.remote_id = int(remote["Id"])
        elif action == "drop":
            if remote:
                cursor.execute("DROP JOB WHERE jobName=%s", (job.name,))
            job.remote_id = None
        elif action in ("pause", "resume"):
            if not remote:
                raise ValueError(f"远端 Job {job.remote_id} 已不存在")
            target = "PAUSED" if action == "pause" else "RUNNING"
            if remote["Status"] != target:
                cursor.execute(f"{action.upper()} JOB WHERE jobName=%s", (job.name,))
        else:
            raise ValueError(f"未知动作 {action}")
    job.reconcile_status = "ready" if job.remote_id is not None else "draft"
    job.pending_action = job.status_reason = ""


@transaction.atomic(using=DATABASE_CONNECTION_NAME)
def reconcile_job(job_id):
    job = DorisJobConfig.objects.select_for_update().filter(pk=job_id, reconcile_status="pending").first()
    if not job:
        return
    try:
        with closing(connect(job)) as connection:
            apply_action(job, connection)
    except pymysql.MySQLError as error:
        # 网络故障可能发生在 FE 已接受 DDL 之后，下一轮先观察远端状态。
        if error.args[0] not in (2002, 2003, 2006, 2013):
            job.reconcile_status = "failed"
        job.status_reason = str(error)
    except (ValueError, ClusterInfo.DoesNotExist) as error:
        job.reconcile_status = "failed"
        job.status_reason = str(error)
    job.save(update_fields=["reconcile_status", "pending_action", "status_reason", "remote_id", "last_modify_time"])


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
            if job.reconcile_status != "failed":
                raise ValueError("只有失败的动作可以重试")
            action = job.pending_action
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
