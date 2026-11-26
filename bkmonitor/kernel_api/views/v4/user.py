"""Independent user endpoints, authenticated and executed before view dispatch."""

from pathlib import Path

from django.conf import settings
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.user_api import USER_API_PREFIX, build_user_api_paths


class _AuthenticatedUserResource(Resource):
    def perform_request(self, validated_request_data):
        # Never dispatch business code if the gateway authentication middleware was skipped.
        raise PermissionDenied("Independent user APIs require verified gateway authentication.")


class UserViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute(method, _AuthenticatedUserResource, endpoint=path.removeprefix(USER_API_PREFIX).strip("/"))
        for path, methods in build_user_api_paths(
            Path(settings.BASE_DIR) / "support-files/apigw/resources/internal/user"
        ).items()
        for method in methods
    ]
