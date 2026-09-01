import json
import logging

from django.conf import settings

from bkmonitor.utils.graph_relation import is_graph_relation_v4_enabled


logger = logging.getLogger("bkmonitor")

RELATION_MULTI_RESOURCE_PATH = "/api/v1/relation/multi_resource"
RELATION_MULTI_RESOURCE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource"
RELATION_MULTI_RESOURCE_RANGE_PATH = "/api/v1/relation/multi_resource_range"
RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource_range"
DEFAULT_GRAPH_RELATION_V4_BINDING_REDIS_KEY = "bkmonitorv3:spaces:surrealdb_binding"


def get_graph_relation_v4_binding_route(redis_key: str, redis_field: str) -> bytes | None:
    from metadata.utils.redis_tools import RedisTools

    return RedisTools.hget(redis_key, redis_field)


def is_graph_relation_v4_query_ready(space_uid: str, bk_biz_id: int | str | None, bk_tenant_id: str | None) -> bool:
    if not space_uid:
        return False

    try:
        normalized_biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return False

    redis_key = getattr(
        settings,
        "GRAPH_RELATION_V4_BINDING_REDIS_KEY",
        DEFAULT_GRAPH_RELATION_V4_BINDING_REDIS_KEY,
    )
    redis_field = f"{space_uid}|{bk_tenant_id}" if bk_tenant_id else space_uid
    try:
        raw_binding_route = get_graph_relation_v4_binding_route(redis_key, redis_field)
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "failed to read Graph Relation V4 binding route, key=%s, field=%s",
            redis_key,
            redis_field,
            exc_info=True,
        )
        return False

    if not raw_binding_route:
        return False

    try:
        binding_route = json.loads(raw_binding_route)
    except (TypeError, ValueError, UnicodeError):
        logger.warning(
            "invalid Graph Relation V4 binding route ignored, key=%s, field=%s",
            redis_key,
            redis_field,
        )
        return False
    if not isinstance(binding_route, dict):
        return False

    binding_biz_id = binding_route.get("bk_biz_id")
    if binding_biz_id not in (None, ""):
        try:
            if int(binding_biz_id) != normalized_biz_id:
                return False
        except (TypeError, ValueError):
            return False

    return (
        binding_route.get("phase") == "Ok"
        and bool(binding_route.get("database"))
        and bool(binding_route.get("namespace"))
    )


def resolve_relation_query_path(
    legacy_path: str,
    v1beta3_path: str,
    bk_biz_id: int | str | None,
    space_uid: str = "",
    bk_tenant_id: str | None = None,
) -> str:
    if (
        v1beta3_path
        and is_graph_relation_v4_enabled(bk_biz_id)
        and is_graph_relation_v4_query_ready(space_uid, bk_biz_id, bk_tenant_id)
    ):
        return v1beta3_path
    return legacy_path
