"""Doris SQL for the superuser web console. Not exposed by the Admin CLI."""

import datetime
import decimal
import time

import pymysql
import sqlparse
from sqlparse import tokens as T

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id
from metadata import models


def classify_sql(sql: str) -> tuple[str, bool]:
    statements = [
        statement
        for statement in sqlparse.parse(sql)
        if any(
            not token.is_whitespace and token.ttype not in T.Comment and token.value != ";"
            for token in statement.flatten()
        )
    ]
    if len(statements) != 1:
        raise CustomException(message="每次只能执行一条 SQL")
    statement = statements[0]
    tokens = [token for token in statement.flatten() if not token.is_whitespace and token.ttype not in T.Comment]
    first = tokens[0].normalized.upper()
    kind = statement.get_type()
    if any(token.value.startswith(("/*!", "/*M!")) for token in statement.flatten()):
        return kind, True
    if kind == "SELECT":
        # SELECT INTO OUTFILE and data-changing CTEs are not read-only queries.
        changes = any(
            token.ttype in T.Keyword
            and (token.normalized == "INTO" or token.ttype in T.DML and token.normalized != "SELECT")
            for token in tokens
        )
        return kind, changes
    if first in {"SHOW", "DESC", "DESCRIBE"}:
        return first, False
    return kind if kind != "UNKNOWN" else first, True


def serialize_cell(value):
    if isinstance(value, datetime.date | datetime.time | datetime.datetime | decimal.Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, int) and abs(value) > 9007199254740991:
        return str(value)
    return value


@KernelRPCRegistry.register(
    "admin.doris_sql.execute",
    summary="Doris 超级管理员网页 SQL 执行",
    description="仅供 Admin 超级管理员网页专用代理；不进入 CLI catalog。变更 SQL 必须 confirmed=true；每次执行一个独立连接中的单条语句。",
    params_schema={
        "bk_tenant_id": "租户",
        "cluster_id": "Doris 集群",
        "sql": "单条 SQL",
        "database": "可选默认库",
        "confirmed": "变更二次确认",
        "readonly": "由 Admin 环境配置确定",
        "max_rows": "默认500，最大5000",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": 40, "sql": "SHOW DATABASES"},
)
def execute_doris_sql(params):
    tenant = get_bk_tenant_id(params)
    sql = str(params.get("sql") or "").strip()
    if not sql or len(sql) > 100000:
        raise CustomException(message="SQL 不能为空且最多 100000 字符")
    kind, requires_confirmation = classify_sql(sql)
    try:
        cluster_id = int(params.get("cluster_id"))
        max_rows = int(params.get("max_rows", 500))
    except (ValueError, TypeError) as error:
        raise CustomException(message="cluster_id 和 max_rows 必须是整数") from error
    if not 1 <= max_rows <= 5000:
        raise CustomException(message="max_rows 必须在 1 到 5000 之间")
    cluster = models.ClusterInfo.objects.get(
        bk_tenant_id=tenant, cluster_id=cluster_id, cluster_type=models.ClusterInfo.TYPE_DORIS
    )
    if requires_confirmation and params.get("readonly") is not False:
        raise CustomException(message="当前环境只读，不能执行变更 SQL")
    result = {
        "status": "confirmation_required",
        "statement_type": kind,
        "columns": [],
        "rows": [],
        "affected_rows": None,
        "elapsed_ms": 0,
        "truncated": False,
    }
    if requires_confirmation and params.get("confirmed") is not True:
        return build_sql_response(tenant, result)
    started = time.monotonic()
    connection = pymysql.connect(
        host=cluster.domain_name,
        port=int(cluster.port),
        user=cluster.username or "",
        password=cluster.password or "",
        database=params.get("database") or None,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSCursor,
        autocommit=True,
        connect_timeout=10,
        read_timeout=35,
        write_timeout=10,
    )
    try:
        cursor = connection.cursor()
        cursor.execute("SET query_timeout = 30")
        cursor.execute(sql)
        result["status"] = "executed"
        if cursor.description:
            result["columns"] = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(max_rows + 1)
            result["rows"] = [[serialize_cell(cell) for cell in row] for row in rows[:max_rows]]
            result["truncated"] = len(rows) > max_rows
        else:
            result["affected_rows"] = cursor.rowcount
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    except pymysql.MySQLError as error:
        raise CustomException(message=f"Doris SQL 执行失败: {error}") from error
    finally:
        # Closing the connection avoids draining a potentially large streaming result.
        connection.close()
    return build_sql_response(tenant, result)


def build_sql_response(tenant, result):
    response = build_response(
        operation="doris_sql.execute",
        func_name="admin.doris_sql.execute",
        bk_tenant_id=tenant,
        data=result,
        warnings=[],
    )
    response["meta"]["safety_level"] = "destructive"
    return response
