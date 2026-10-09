"""Internal BKFARA incident topology availability API."""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.incident.resources import IncidentTopologyAvailabilityResource


class IncidentViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", IncidentTopologyAvailabilityResource, endpoint="topology_availability"),
    ]
