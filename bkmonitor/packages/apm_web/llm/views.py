from apm_web.llm.resources import (
    CalculateByRangeResource,
    ListFlowsResource,
    ListSpansResource,
    ListTracesResource,
    TimeSeriesResource,
)
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class LLMViewSet(ResourceViewSet):
    INSTANCE_ID = "app_name"

    def get_permissions(self) -> list[InstanceActionForDataPermission]:
        return [
            InstanceActionForDataPermission(
                self.INSTANCE_ID,
                [ActionEnum.VIEW_APM_APPLICATION],
                ResourceEnum.APM_APPLICATION,
                get_instance_id=Application.get_application_id_by_app_name,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", ListTracesResource, endpoint="list_traces"),
        ResourceRoute("POST", ListSpansResource, endpoint="list_spans"),
        ResourceRoute("POST", ListFlowsResource, endpoint="list_flows"),
        ResourceRoute("POST", TimeSeriesResource, endpoint="time_series"),
        ResourceRoute("POST", CalculateByRangeResource, endpoint="calculate_by_range"),
    ]
