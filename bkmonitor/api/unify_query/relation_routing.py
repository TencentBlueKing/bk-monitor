from bkmonitor.utils.graph_relation import get_relation_schema_version


RELATION_MULTI_RESOURCE_PATH = "/api/v1/relation/multi_resource"
RELATION_MULTI_RESOURCE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource"
RELATION_MULTI_RESOURCE_RANGE_PATH = "/api/v1/relation/multi_resource_range"
RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource_range"


def resolve_relation_query_path(
    legacy_path: str,
    v1beta3_path: str,
    bk_biz_id: int | str | None,
    schema_version: str | None = None,
) -> str:
    if not v1beta3_path:
        return legacy_path
    if schema_version is None:
        schema_version = get_relation_schema_version(bk_biz_id)
    return v1beta3_path if schema_version else legacy_path
