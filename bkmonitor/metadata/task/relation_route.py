"""
Runtime route snapshot for Graph Relation V4 business relation writes.
"""

import hashlib
import json
import logging
import time
from typing import Any

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from metadata.models import DataSourceResultTable, ResultTable, ResultTableOption, TimeSeriesGroup
from metadata.models.entity_relation import NAMESPACE_ALL, RelationDefinition
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")

BUILTIN_DATA_RT_REDIS_KEY = "bkmonitorv3:spaces:built_in_result_table_detail"
GRAPH_RELATION_ROUTE_REDIS_KEY = "bkmonitorv3:spaces:graph_relation_route"
GRAPH_RELATION_ROUTE_CHANNEL = f"{GRAPH_RELATION_ROUTE_REDIS_KEY}:channel"
GRAPH_RELATION_ROUTE_EVENT = "graph_relation_route_changed"


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _relation_definition_version(namespace: str) -> str:
    definitions = list(
        RelationDefinition.objects.filter(namespace__in=[namespace, NAMESPACE_ALL]).values(
            "namespace",
            "name",
            "from_resource",
            "to_resource",
            "category",
            "is_directional",
            "is_belongs_to",
            "labels",
            "spec",
        )
    )
    payload = json.dumps(definitions, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _route_for_space(space_uid: str, raw_value: Any) -> dict[str, Any]:
    value = json.loads(_decode(raw_value))
    if not isinstance(value, dict):
        raise ValueError("built-in relation value must be an object")

    if not space_uid.startswith("bkcc__"):
        return {
            "space_uid": space_uid,
            "graph_enabled": False,
            "write_targets": [],
            "status": "disabled",
            "updated_at": int(time.time()),
        }

    bk_biz_id = int(space_uid.split("__", 1)[1])
    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
    data_name = f"{bk_biz_id}_bkcc_built_in_time_series"
    table_id = f"{data_name}.__default__"
    route: dict[str, Any] = {
        "bk_biz_id": bk_biz_id,
        "bk_tenant_id": bk_tenant_id,
        "space_uid": space_uid,
        "relation_table_id": table_id,
        "relation_data_id": None,
        "graph_enabled": False,
        "write_targets": [],
        "relation_token": value.get("token") or "",
        "relation_token_modify_time": value.get("modifyTime"),
        "relation_definition_version": _relation_definition_version(space_uid),
        "updated_at": int(time.time()),
        "status": "degraded",
    }

    result_table = ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
    option_record = ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=ResultTableOption.OPTION_GRAPH_RELATION_V4_DATA_LINK,
    ).first()
    if result_table is None or option_record is None:
        route["status"] = "disabled"
        return route

    try:
        option = option_record.get_value()
        if isinstance(option, str):
            option = json.loads(option)
        write_targets = sorted(option.get("write_targets", []))
    except (TypeError, ValueError, json.JSONDecodeError):
        route["status"] = "degraded"
        return route

    route["write_targets"] = write_targets
    route["graph_enabled"] = "surrealdb" in write_targets

    dsrt = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
    if dsrt is not None:
        route["relation_data_id"] = dsrt.bk_data_id
    tsg = TimeSeriesGroup.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
    if tsg is not None and tsg.token:
        route["relation_token"] = tsg.token

    if route["graph_enabled"] and route["relation_token"] and route["relation_data_id"]:
        route["status"] = "ready"
    elif route["graph_enabled"]:
        route["status"] = "degraded"
    else:
        route["status"] = "disabled"
    version_payload = {key: value for key, value in route.items() if key != "updated_at"}
    route["version"] = hashlib.sha256(
        json.dumps(version_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return route


def refresh_graph_relation_routes(
    builtin_data_rt_redis_key: str = BUILTIN_DATA_RT_REDIS_KEY,
) -> None:
    """Refresh Graph V4 route snapshots and publish only changed business routes."""
    source_data = RedisTools.hgetall(builtin_data_rt_redis_key) or {}
    current_routes = RedisTools.hgetall(GRAPH_RELATION_ROUTE_REDIS_KEY) or {}
    desired_fields: set[str] = set()

    for raw_field, raw_value in source_data.items():
        space_uid = _decode(raw_field)
        desired_fields.add(space_uid)
        try:
            route = _route_for_space(space_uid, raw_value)
            route_json = json.dumps(route, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            logger.exception("build graph relation route failed, space_uid=%s", space_uid)
            route_json = json.dumps(
                {"space_uid": space_uid, "graph_enabled": False, "status": "degraded", "updated_at": int(time.time())},
                sort_keys=True,
            )
        old_json = current_routes.get(raw_field, current_routes.get(space_uid))
        old_json = _decode(old_json) if old_json is not None else ""
        old_route = json.loads(old_json) if old_json else None
        route_changed = not isinstance(old_route, dict) or old_route.get("version") != route.get("version")
        if route_changed:
            RedisTools.hset_to_redis(GRAPH_RELATION_ROUTE_REDIS_KEY, space_uid, route_json)
            RedisTools.publish(
                GRAPH_RELATION_ROUTE_CHANNEL,
                [json.dumps({"event": GRAPH_RELATION_ROUTE_EVENT, "scope": "business", "space_uid": space_uid})],
            )

    stale_fields = {_decode(field) for field in current_routes} - desired_fields
    for space_uid in stale_fields:
        tombstone = json.dumps(
            {"space_uid": space_uid, "graph_enabled": False, "status": "deleted", "updated_at": int(time.time())},
            sort_keys=True,
        )
        RedisTools.hset_to_redis(GRAPH_RELATION_ROUTE_REDIS_KEY, space_uid, tombstone)
        RedisTools.publish(
            GRAPH_RELATION_ROUTE_CHANNEL,
            [json.dumps({"event": GRAPH_RELATION_ROUTE_EVENT, "scope": "business", "space_uid": space_uid})],
        )

    logger.info("graph relation routes refreshed, route_count=%d", len(desired_fields))
