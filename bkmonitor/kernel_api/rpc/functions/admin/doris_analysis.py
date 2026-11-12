"""Read-only Doris physical table usage snapshot; no business-table queries."""

from collections import defaultdict
from typing import Any

import pymysql
from django.db.models import Q

from metadata import models

SYSTEM_DATABASES = {"information_schema", "mysql", "__internal_schema"}


def quote_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def build_ownership(cluster_id: int, tenant: str, warnings: list) -> dict:
    from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig

    owners = defaultdict(dict)
    records = list(models.StorageClusterRecord.objects.filter(bk_tenant_id=tenant, cluster_id=cluster_id))
    storages = list(
        models.DorisStorage.objects.filter(
            Q(origin_table_id="") | Q(origin_table_id__isnull=True), bk_tenant_id=tenant, storage_cluster_id=cluster_id
        )
    )
    virtual_ids = set(
        models.DorisStorage.objects.filter(bk_tenant_id=tenant, table_id__in=[record.table_id for record in records])
        .exclude(Q(origin_table_id="") | Q(origin_table_id__isnull=True))
        .values_list("table_id", flat=True)
    )
    current = [storage for storage in storages if storage.storage_cluster_id == cluster_id]
    missing_ids = [storage.table_id for storage in current if not storage.physical_tables]
    bindings = {}
    for binding in DorisStorageBindingConfig.objects.filter(bk_tenant_id=tenant, table_id__in=missing_ids).order_by(
        "-last_modify_time", "-id"
    ):
        bindings.setdefault(binding.table_id, binding)

    def add(table_id, physical_tables, state):
        for physical in (physical_tables or {}).values():
            if not isinstance(physical, str) or "." not in physical:
                continue
            # Current and historical evidence for the same owner counts once.
            previous = owners[physical].get(table_id)
            owners[physical][table_id] = "current" if "current" in (previous, state) else "historical"

    for storage in current:
        physical_tables = storage.physical_tables
        if not physical_tables and (binding := bindings.get(storage.table_id)):
            physical_tables = binding.physical_tables
            if not physical_tables:
                try:
                    config = binding.component_config or {}
                except Exception:
                    warnings.append(
                        {
                            "code": "DORIS_BINDING_UNAVAILABLE",
                            "message": f"无法读取 {storage.table_id} 的物理表绑定，归属可能不完整",
                        }
                    )
                    continue
                physical = (config.get("metadata", {}).get("annotations") or {}).get("PhysicalTableName")
                spec = config.get("spec", {}).get("storage_config") or {}
                if not physical and spec.get("db") and spec.get("table"):
                    physical = f"{spec['db']}.{spec['table']}"
                physical_tables = {"main": physical} if physical else {}
        add(storage.table_id, physical_tables, "current")
    for record in records:
        if record.table_id not in virtual_ids:
            add(record.table_id, record.physical_tables, "historical")
    return owners


def associate_table(database: str, table: str, owners: dict) -> dict:
    from kernel_api.rpc.functions.admin.cluster_info import _parse_es_analysis_owner

    candidates = owners.get(f"{database}.{table}", {})
    table_id = next(iter(candidates)) if len(candidates) == 1 else None
    state = candidates[table_id] if table_id else "unmatched"
    return {
        "matched_table_id": table_id,
        "match_status": state,
        "match_reason": "physical_table" if table_id else "ambiguous" if candidates else "not_found",
        **_parse_es_analysis_owner(table_id),
    }


def sum_known(rows: list[dict], field: str) -> int | None:
    values = [row[field] for row in rows if row[field] is not None]
    return sum(values) if values else None


def build_doris_storage_analysis(cluster: Any, tenant: str) -> tuple[dict, list]:
    warnings = []
    owners = build_ownership(cluster.cluster_id, tenant, warnings)
    tables = {}

    def warn(component, database=None):
        warnings.append(
            {
                "code": "DORIS_ANALYSIS_QUERY_FAILED",
                "message": f"Doris {component} 查询失败，结果不完整",
                "details": {"database": database},
            }
        )

    connection = pymysql.connect(
        host=cluster.domain_name,
        port=int(cluster.port),
        user=cluster.username or "",
        password=cluster.password or "",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=10,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW DATABASES")
            databases = [str(next(iter(row.values()))) for row in cursor.fetchall()]
            for database in databases:
                if database.lower() in SYSTEM_DATABASES:
                    continue
                # Successful empty databases remain distinguishable from failed reads via warnings.
                try:
                    cursor.execute(
                        "SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' AND ENGINE IN ('OLAP', 'Doris')",
                        (database,),
                    )
                    for row in cursor.fetchall():
                        table = row["TABLE_NAME"]
                        tables[(database, table)] = {
                            "database": database,
                            "table": table,
                            "store_bytes": None,
                            "replica_count": None,
                            "row_count": int(row["TABLE_ROWS"]) if row.get("TABLE_ROWS") is not None else None,
                        }
                except Exception:  # A database can be visible but not readable by this account.
                    warn("行数元数据", database)
                try:
                    cursor.execute(f"USE {quote_identifier(database)}")
                    cursor.execute("SHOW DATA")
                    usage_rows = cursor.fetchall()
                    if usage_rows and not any("TableName" in row for row in usage_rows):
                        warn("表容量返回格式不支持", database)
                    for row in usage_rows:
                        table = row.get("TableName")
                        if not table or table in {"Total", "Quota", "Left"}:
                            continue
                        item = tables.setdefault(
                            (database, table), {"database": database, "table": table, "row_count": None}
                        )
                        item["store_bytes"] = models.ClusterInfo._parse_doris_size_bytes(row.get("Size"))
                        item["replica_count"] = models.ClusterInfo._parse_check_int(row.get("ReplicaCount"))
                except Exception:
                    warn("表容量", database)
    finally:
        connection.close()
    rows = [{**item, **associate_table(database, table, owners)} for (database, table), item in tables.items()]
    rows.sort(key=lambda item: (-(item["store_bytes"] or 0), item["database"], item["table"]))
    return {
        "cluster": {"cluster_id": cluster.cluster_id, "cluster_name": cluster.cluster_name},
        "summary": {
            "table_count": len(rows),
            "total_store_bytes": sum_known(rows, "store_bytes"),
            "total_row_count": sum_known(rows, "row_count"),
            "matched_table_count": sum(row["matched_table_id"] is not None for row in rows),
        },
        "tables": rows,
        "scope": "当前连接账号可见的内部库物理表；容量包含副本，行数为估算；不含系统库及回收站。",
    }, warnings
