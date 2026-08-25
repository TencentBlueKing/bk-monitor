from apm_web.llm.resources import ListSpansResource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class LLMViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", ListSpansResource, endpoint="list_spans"),
    ]
