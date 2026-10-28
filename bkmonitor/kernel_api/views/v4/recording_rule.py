from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.recording_rule import (
    ApplyConfigResource,
    CreateConfigResource,
    DeleteConfigResource,
    GetConfigResource,
    ListConfigsResource,
    PreviewConfigResource,
    UpdateConfigResource,
)


class RecordingRuleViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", PreviewConfigResource, endpoint="preview_config"),
        ResourceRoute("POST", CreateConfigResource, endpoint="create_config"),
        ResourceRoute("POST", UpdateConfigResource, endpoint="update_config"),
        ResourceRoute("POST", DeleteConfigResource, endpoint="delete_config"),
        ResourceRoute("GET", GetConfigResource, endpoint="get_config"),
        ResourceRoute("POST", ApplyConfigResource, endpoint="apply_config"),
        ResourceRoute("GET", ListConfigsResource, endpoint="list_configs"),
    ]
