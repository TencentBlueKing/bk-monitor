RELATION_MULTI_RESOURCE_PATH = "/api/v1/relation/multi_resource"
RELATION_MULTI_RESOURCE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource"
RELATION_MULTI_RESOURCE_RANGE_PATH = "/api/v1/relation/multi_resource_range"
RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH = "/api/v1/relation/v1beta3/multi_resource_range"


def resolve_relation_query_path(
    legacy_path: str,
    v1beta3_path: str,
    schema_version: str,
) -> str:
    return v1beta3_path if v1beta3_path and schema_version else legacy_path
