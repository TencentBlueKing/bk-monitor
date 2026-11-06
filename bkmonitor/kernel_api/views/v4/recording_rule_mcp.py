"""强制用户鉴权的 RecordingRule MCP 入口。"""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource import recording_rule_mcp as _recording_rule_mcp


class RecordingRuleMCPViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", _recording_rule_mcp.PreviewConfigResource, endpoint="preview_config"),
        ResourceRoute("POST", _recording_rule_mcp.CreateConfigResource, endpoint="create_config"),
        ResourceRoute("POST", _recording_rule_mcp.UpdateConfigResource, endpoint="update_config"),
        ResourceRoute("POST", _recording_rule_mcp.DeleteConfigResource, endpoint="delete_config"),
        ResourceRoute("POST", _recording_rule_mcp.GetConfigResource, endpoint="get_config"),
        ResourceRoute("POST", _recording_rule_mcp.ApplyConfigResource, endpoint="apply_config"),
        ResourceRoute("POST", _recording_rule_mcp.ListConfigsResource, endpoint="list_configs"),
    ]
