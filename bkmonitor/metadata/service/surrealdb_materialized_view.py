"""SurrealDB relation materialized view definition and reconciliation."""

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

        view_name = f"{relation_name}_materialized_view"
        source_table = f"{relation_name}_liveness_record"
        source_index = f"idx_{relation_name}_mv_source_period"
        target_index = f"idx_{relation_name}_mv_target_period"
        source_snapshot = _snapshot_expression(
            "relation_id.in", source_vertex["id_fields"], f"vertices[{source_type}].id_fields"
        )
        target_snapshot = _snapshot_expression(
            "relation_id.out", target_vertex["id_fields"], f"vertices[{target_type}].id_fields"
        )

        statements.extend(
            [
                f"REMOVE TABLE IF EXISTS {_quote_identifier(view_name)};",
                "\n".join(
                    [
                        f"DEFINE TABLE {_quote_identifier(view_name)} TYPE NORMAL AS",
                        "SELECT",
                        "  id AS liveness_id,",
                        "  relation_id,",
                        "  relation_id.in AS source_id,",
                        "  relation_id.out AS target_id,",
                        f"  {_string_literal(source_type)} AS source_type,",
                        f"  {_string_literal(target_type)} AS target_type,",
                        f"  {source_snapshot} AS source_snapshot,",
                        f"  {target_snapshot} AS target_snapshot,",
                        "  period_start AS relation_period_start_ms,",
                        "  period_end AS relation_period_end_ms",
                        f"FROM {_quote_identifier(source_table)}",
                        "WHERE period_start < period_end;",
                    ]
                ),
                "\n".join(
                    [
                        f"DEFINE INDEX {_quote_identifier(source_index)}",
                        f"ON TABLE {_quote_identifier(view_name)}",
                        "FIELDS source_id, relation_period_start_ms, relation_period_end_ms;",
                    ]
                ),
                "\n".join(
                    [
                        f"DEFINE INDEX {_quote_identifier(target_index)}",
                        f"ON TABLE {_quote_identifier(view_name)}",
                        "FIELDS target_id, relation_period_start_ms, relation_period_end_ms;",
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
