from apm_web.llm.resources import ListSpansResource, ListTracesResource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class LLMViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", ListTracesResource, endpoint="list_traces"),
        ResourceRoute("POST", ListSpansResource, endpoint="list_spans"),
    ]
