"""SurrealDB active-edge event definition and reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from metadata.models.data_link.constants import DataLinkResourceStatus

if TYPE_CHECKING:
    from metadata.models.data_link.data_link_configs import SurrealDBBindingConfig

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCOPE_ANNOTATION_KEYS = {
    "namespace": ("surrealdbnamespace", "surrealnamespace"),
    "database": ("surrealdbdatabase", "surrealdatabase"),
}


@dataclass(frozen=True)
class SurrealDBScope:
    namespace: str
    database: str


def _normalize_key(value: str) -> str:
    return value.replace("_", "").replace("-", "").lower()


def _require_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field} 不是合法的 SurrealDB 标识符: {value!r}")
    return value


def _quote_identifier(value: str) -> str:
    return f"`{value}`"


def _string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def resolve_surrealdb_scope(config: dict[str, Any]) -> SurrealDBScope:
    metadata = config.get("metadata") if isinstance(config, dict) else None
    annotations = metadata.get("annotations") if isinstance(metadata, dict) else None
    if not isinstance(annotations, dict):
        annotations = {}
    normalized_annotations = {_normalize_key(key): value for key, value in annotations.items() if isinstance(key, str)}

    resolved = {}
    for field, keys in _SCOPE_ANNOTATION_KEYS.items():
        value = next((normalized_annotations.get(key) for key in keys if normalized_annotations.get(key)), None)
        if value is not None:
            resolved[field] = _require_identifier(value, f"metadata.annotations.{field}")

    status = config.get("status") if isinstance(config, dict) else None
    scope = status.get("storage") if isinstance(status, dict) else None
    if isinstance(scope, dict):
        for field in ("namespace", "database"):
            if field not in resolved and scope.get(field):
                resolved[field] = _require_identifier(scope[field], f"status.storage.{field}")

    if set(resolved) != {"namespace", "database"}:
        raise ValueError("SurrealDBBinding 缺少 SurrealDB namespace/database annotations")
    return SurrealDBScope(namespace=resolved["namespace"], database=resolved["database"])


def _snapshot_expression(record_link: str, fields: list[str], field: str) -> str:
    projections = []
    for index, item in enumerate(fields):
        identifier = _require_identifier(item, f"{field}[{index}]")
        projections.append(f"    {identifier}: {record_link}.{identifier}")
    return "{\n" + ",\n".join(projections) + "\n  }"


def _index_ddl(name: str, table: str, fields: str, *, unique: bool = False) -> str:
    unique_clause = " UNIQUE" if unique else ""
    return "\n".join(
        [
            f"DEFINE INDEX OVERWRITE {_quote_identifier(name)}",
            f"ON TABLE {_quote_identifier(table)}",
            f"FIELDS {fields}{unique_clause};",
        ]
    )


def _snapshot_index_fields(prefix: str, fields: list[str], field: str, period_field: str) -> str:
    snapshot_fields = []
    for index, item in enumerate(fields):
        identifier = _require_identifier(item, f"{field}[{index}]")
        snapshot_fields.append(f"{prefix}.{identifier}")
    snapshot_fields.append(period_field)
    return ", ".join(snapshot_fields)


def build_materialized_view_ddl(binding: SurrealDBBindingConfig, scope: SurrealDBScope) -> str:
    binding._validate_graph_definitions()
    vertices = {vertex["name"]: vertex for vertex in binding.vertices}
    statements = [
        f"USE NS {_quote_identifier(scope.namespace)} DB {_quote_identifier(scope.database)};",
        "BEGIN TRANSACTION;",
    ]

    for index, relation in enumerate(binding.relations):
        relation_name = _require_identifier(relation["name"], f"relations[{index}].name")
        source_type = _require_identifier(relation["from"], f"relations[{index}].from")
        target_type = _require_identifier(relation["to"], f"relations[{index}].to")
        source_vertex = vertices.get(source_type)
        target_vertex = vertices.get(target_type)
        if source_vertex is None or target_vertex is None:
            raise ValueError(f"relation[{relation_name}] 引用了未定义的顶点")

        view_name = f"{relation_name}_active_edge_view"
        liveness_table = f"{relation_name}_liveness_record"
        liveness_index = f"idx_{relation_name}_liveness_relation_active_created"
        materialize_event = f"materialize_{relation_name}_active_edge"
        delete_event = f"delete_{relation_name}_active_edge"
        remove_invalid_event = f"remove_invalid_{relation_name}_active_edge"
        source_snapshot = _snapshot_expression(
            "$edge.in", source_vertex["id_fields"], f"vertices[{source_type}].id_fields"
        )
        target_snapshot = _snapshot_expression(
            "$edge.out", target_vertex["id_fields"], f"vertices[{target_type}].id_fields"
        )

        # SurrealDBBinding creates the relation and liveness tables. Metadata owns the
        # liveness-to-serving projection used by active-edge queries.
        statements.extend(
            [
                f"DEFINE TABLE IF NOT EXISTS {_quote_identifier(view_name)} SCHEMALESS;",
                _index_ddl(
                    liveness_index,
                    liveness_table,
                    "relation_id, is_active, created_at",
                ),
                _index_ddl(
                    f"uniq_{relation_name}_active_edge_source_liveness",
                    view_name,
                    "source_liveness_id",
                    unique=True,
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_source_start",
                    view_name,
                    "source_id, active_period_start_ms",
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_source_end",
                    view_name,
                    "source_id, active_period_end_ms",
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_target_start",
                    view_name,
                    "target_id, active_period_start_ms",
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_target_end",
                    view_name,
                    "target_id, active_period_end_ms",
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_source_data_start",
                    view_name,
                    _snapshot_index_fields(
                        "source_data",
                        source_vertex["id_fields"],
                        f"vertices[{source_type}].id_fields",
                        "active_period_start_ms",
                    ),
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_source_data_end",
                    view_name,
                    _snapshot_index_fields(
                        "source_data",
                        source_vertex["id_fields"],
                        f"vertices[{source_type}].id_fields",
                        "active_period_end_ms",
                    ),
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_target_data_start",
                    view_name,
                    _snapshot_index_fields(
                        "target_data",
                        target_vertex["id_fields"],
                        f"vertices[{target_type}].id_fields",
                        "active_period_start_ms",
                    ),
                ),
                _index_ddl(
                    f"idx_{relation_name}_active_edge_target_data_end",
                    view_name,
                    _snapshot_index_fields(
                        "target_data",
                        target_vertex["id_fields"],
                        f"vertices[{target_type}].id_fields",
                        "active_period_end_ms",
                    ),
                ),
                "\n".join(
                    [
                        f"DEFINE EVENT OVERWRITE {_quote_identifier(materialize_event)}",
                        f"ON TABLE {_quote_identifier(liveness_table)}",
                        "WHEN ($event = 'CREATE' OR $event = 'UPDATE')",
                        "  AND $after.is_active = true",
                        "  AND $after.period_start <= $after.period_end",
                        "THEN {",
                        "  LET $edge = (SELECT * FROM ONLY $after.relation_id);",
                        f"  UPSERT {_quote_identifier(view_name)} SET",
                        "    source_liveness_id = $after.id,",
                        "    relation_id = $after.relation_id,",
                        "    source_id = $edge.in,",
                        f"    source_type = {_string_literal(source_type)},",
                        f"    source_data = {source_snapshot},",
                        "    target_id = $edge.out,",
                        f"    target_type = {_string_literal(target_type)},",
                        f"    target_data = {target_snapshot},",
                        "    active_period_start_ms = $after.period_start,",
                        "    active_period_end_ms = $after.period_end",
                        "  WHERE source_liveness_id = $after.id;",
                        "};",
                    ]
                ),
                "\n".join(
                    [
                        f"DEFINE EVENT OVERWRITE {_quote_identifier(delete_event)}",
                        f"ON TABLE {_quote_identifier(liveness_table)}",
                        "WHEN $event = 'DELETE' OR ($event = 'UPDATE' AND $after.is_active != true)",
                        "THEN {",
                        "  IF $event = 'DELETE' {",
                        f"    DELETE {_quote_identifier(view_name)} WHERE source_liveness_id = $before.id;",
                        "  } ELSE {",
                        f"    DELETE {_quote_identifier(view_name)} WHERE source_liveness_id = $after.id;",
                        "  };",
                        "};",
                    ]
                ),
                "\n".join(
                    [
                        f"DEFINE EVENT OVERWRITE {_quote_identifier(remove_invalid_event)}",
                        f"ON TABLE {_quote_identifier(liveness_table)}",
                        "WHEN ($event = 'CREATE' OR $event = 'UPDATE')",
                        "  AND $after.period_start > $after.period_end",
                        f"THEN (DELETE {_quote_identifier(view_name)} WHERE source_liveness_id = $after.id);",
                    ]
                ),
            ]
        )
    statements.append("COMMIT TRANSACTION;")
    return "\n\n".join(statements)


def _mark_materialized_view_failed(binding: SurrealDBBindingConfig, error: Exception) -> None:
    binding.materialized_view_status = DataLinkResourceStatus.FAILED.value
    binding.materialized_view_last_error = str(error)[:4096]
    binding.save(update_fields=["materialized_view_status", "materialized_view_last_error", "last_modify_time"])


def reconcile_materialized_views(binding: SurrealDBBindingConfig, remote_config: dict[str, Any]) -> bool:
    from django.utils import timezone

    from core.drf_resource import api

    if binding.status != DataLinkResourceStatus.OK.value:
        return False

    try:
        scope = resolve_surrealdb_scope(remote_config)
        ddl = build_materialized_view_ddl(binding, scope)
        definition_hash = hashlib.sha256(ddl.encode("utf-8")).hexdigest()
        if (
            binding.materialized_view_status == DataLinkResourceStatus.OK.value
            and binding.materialized_view_definition_hash == definition_hash
        ):
            return False
        # Events only project subsequent liveness changes. Historical rows require a
        # separately controlled backfill before a relation is routed to this table.
        api.bkdata.query_data(sql=ddl, prefer_storage="surrealdb")
    except Exception as error:
        _mark_materialized_view_failed(binding, error)
        raise

    binding.materialized_view_definition_hash = definition_hash
    binding.materialized_view_status = DataLinkResourceStatus.OK.value
    binding.materialized_view_last_error = ""
    binding.materialized_view_last_apply_time = timezone.now()
    binding.save(
        update_fields=[
            "materialized_view_definition_hash",
            "materialized_view_status",
            "materialized_view_last_error",
            "materialized_view_last_apply_time",
            "last_modify_time",
        ]
    )
    return True
