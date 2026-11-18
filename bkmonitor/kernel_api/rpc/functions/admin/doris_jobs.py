"""Read-only, on-demand Doris job and task metadata queries."""

import json

import pymysql

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, require_bk_tenant_id
from metadata import models


def text(value):
    if value is None:
        return None
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def job_row(row, job_type, database):
    routine = job_type == "routine_load"
    return {
        "id": str(row["Id"]),
        "name": str(row["Name"]),
        "state": text(row.get("State" if routine else "Status")),
        "database": text(row.get("DbName", database) if routine else row.get("MvDatabaseName")),
        "target": text(row.get("TableName") if routine else row.get("MvName")),
        "schedule": text(row.get("RecurringStrategy") or row.get("ExecuteType")),
        "create_time": text(row.get("CreateTime")),
        "success_count": int(row["SucceedTaskCount"]) if row.get("SucceedTaskCount") is not None else None,
        "failed_count": int(row["FailedTaskCount"]) if row.get("FailedTaskCount") is not None else None,
        "error": text(row.get("ReasonOfStateChanged") or row.get("OtherMsg")),
        "sql": text(row.get("ExecuteSql")),
        "progress": text(row.get("Progress")),
    }


def task_row(row, job_type):
    routine = job_type == "routine_load"
    return {
        "id": str(row["TaskId"]),
        "state": text(row.get("TxnStatus" if routine else "Status")),
        "create_time": text(row.get("CreateTime")),
        "start_time": text(row.get("ExecuteStartTime" if routine else "StartTime")),
        "finish_time": text(row.get("FinishTime")),
        "error": text(row.get("ErrorMsg")),
        # Routine Load DataSourceProperties contains partition offsets, not job credentials.
        "progress": text(row.get("DataSourceProperties") if routine else row.get("Progress")),
    }


def query_jobs(params, *, tasks=False):
    tenant = require_bk_tenant_id(params)
    job_type = params.get("job_type")
    database = str(params.get("database") or "").strip()
    state = str(params.get("state") or "").strip()
    if job_type not in {"insert", "mv", "routine_load"}:
        raise CustomException(message="job_type 必须是 insert、mv 或 routine_load")
    if job_type == "routine_load" and not database:
        raise CustomException(message="Routine Load 查询需要指定数据库")
    if job_type == "insert" and database:
        raise CustomException(message="定时 Job 不支持按数据库筛选")
    try:
        cluster_id = int(params.get("cluster_id"))
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
    except (TypeError, ValueError) as error:
        raise CustomException(message="cluster_id、page、page_size 必须是整数") from error
    if cluster_id < 1 or page < 1 or not 1 <= page_size <= 100:
        raise CustomException(message="cluster_id、page 必须为正数，page_size 必须在 1 到 100 之间")
    job_id = str(params.get("job_id") or "")
    job_name = str(params.get("job_name") or "")
    if tasks and (not job_id.isascii() or not job_id.isdigit() or not job_name):
        raise CustomException(message="执行记录需要 job_id（数字字符串）及 job_name")
    cluster = models.ClusterInfo.objects.get(
        bk_tenant_id=tenant, cluster_id=cluster_id, cluster_type=models.ClusterInfo.TYPE_DORIS
    )
    connection = pymysql.connect(
        host=cluster.domain_name,
        port=int(cluster.port),
        user=cluster.username or "",
        password=cluster.password or "",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSDictCursor,
        connect_timeout=10,
        read_timeout=35,
        write_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET query_timeout = 30")
            cursor.execute("SELECT VERSION() AS version")
            version = str(cursor.fetchall()[0]["version"])
            offset = (page - 1) * page_size
            if job_type == "routine_load":
                connection.select_db(database)
                if tasks:
                    cursor.execute("SHOW ROUTINE LOAD TASK WHERE JobName = %s", (job_name,))
                else:
                    cursor.execute("SHOW ALL ROUTINE LOAD")
                # SHOW has no portable LIMIT support. Stream the metadata and retain only this page.
                total, items = 0, []
                while batch := cursor.fetchmany(200):
                    for row in batch:
                        if tasks and str(row.get("JobId")) != job_id:
                            continue
                        item = task_row(row, job_type) if tasks else job_row(row, job_type, database)
                        if state and item["state"] != state:
                            continue
                        if offset <= total < offset + page_size:
                            items.append(item)
                        total += 1
            else:
                function = "tasks" if tasks else "jobs"
                source = f'{function}("type"="{job_type}")'
                conditions, values = [], []
                if tasks:
                    conditions.append("JobId = %s")
                    values.append(job_id)
                if database:
                    conditions.append("MvDatabaseName = %s")
                    values.append(database)
                if state:
                    conditions.append("Status = %s")
                    values.append(state)
                where = " WHERE " + " AND ".join(conditions) if conditions else ""
                cursor.execute(f"SELECT COUNT(*) AS total FROM {source}{where}", tuple(values))
                total = int(cursor.fetchall()[0]["total"])
                order = "CreateTime DESC, TaskId DESC" if tasks else "Id DESC"
                cursor.execute(
                    f"SELECT * FROM {source}{where} ORDER BY {order} LIMIT %s OFFSET %s",
                    (*values, page_size, offset),
                )
                items = [
                    task_row(row, job_type) if tasks else job_row(row, job_type, database) for row in cursor.fetchall()
                ]
    except pymysql.MySQLError as error:
        raise CustomException(
            message=f"Doris {job_type} 查询失败，请检查当前版本是否支持及账号权限：{error}"
        ) from error
    finally:
        connection.close()
    operation = "cluster_info.doris_task_list" if tasks else "cluster_info.doris_job_list"
    scope = "当前连接账号可见任务；历史保留范围由 Doris 配置决定"
    if tasks:
        scope = (
            "仅当前子任务，不包含历史执行记录"
            if job_type == "routine_load"
            else "Doris 当前保留的执行记录，按创建时间倒序"
        )
    return build_response(
        operation=operation,
        func_name=f"admin.{operation}",
        bk_tenant_id=tenant,
        data={
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "server_version": version,
            "scope": scope,
        },
        warnings=[],
    )


PARAMS = {
    "bk_tenant_id": "必填，租户 ID",
    "cluster_id": "必填，Doris ClusterInfo.cluster_id",
    "job_type": "必填，insert / mv / routine_load",
    "database": "Routine Load 必填；mv 可选精确库名；insert 不支持",
    "state": "可选，精确匹配 Doris 原始状态",
    "page": "页码，默认 1",
    "page_size": "每页条数，默认 20，最大 100",
}


@KernelRPCRegistry.register(
    "admin.cluster_info.doris_job_list",
    summary="Admin 按需查询 Doris 任务",
    description="只读分页查询 Job 定义；不自动遍历数据库，不修改任务。",
    params_schema=PARAMS,
    example_params={"bk_tenant_id": "system", "cluster_id": 40, "job_type": "insert", "page": 1, "page_size": 20},
)
def list_doris_jobs(params):
    return query_jobs(params)


@KernelRPCRegistry.register(
    "admin.cluster_info.doris_task_list",
    summary="Admin 按需查询 Doris 执行记录",
    description="只读查询指定 Job 的执行记录；Routine Load 仅返回当前子任务。",
    params_schema={**PARAMS, "job_id": "必填，任务 ID，数字字符串", "job_name": "必填，任务名称"},
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": 40,
        "job_type": "insert",
        "job_id": "1001",
        "job_name": "apm_preaggregate",
    },
)
def list_doris_tasks(params):
    return query_jobs(params, tasks=True)
