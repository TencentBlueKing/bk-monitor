"""Unified monitoring MCP facade endpoints."""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.unified_mcp import (
    ExecuteToolResource,
    LookupMetadataResource,
    LookupPermissionsResource,
    LookupToolResource,
    LookupToolSchemaResource,
)


class UnifiedMCPViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", LookupToolResource, endpoint="lookup_tool"),
        ResourceRoute("POST", LookupToolSchemaResource, endpoint="lookup_tool_schema"),
        ResourceRoute("POST", ExecuteToolResource, endpoint="execute_tool"),
        ResourceRoute("POST", LookupMetadataResource, endpoint="lookup_metadata"),
        ResourceRoute("POST", LookupPermissionsResource, endpoint="lookup_permissions"),
    ]
