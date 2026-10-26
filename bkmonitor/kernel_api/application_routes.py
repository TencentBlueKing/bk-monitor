"""Explicit application-only aliases for read APIs shared with user MCP resources.

APIGW must verify application resource permission before routing to these aliases.
A signed application identity alone does not attest resource permission. Do not
expose this namespace through a wildcard gateway proxy or an untrusted ingress.
"""

import re

from django.urls import get_resolver, re_path

APPLICATION_PREFIX = "/api/app/"

# Keep this allowlist paired with the application resource definitions. Never
# mount an entire API namespace: it would also expose write/export operations.
APPLICATION_READ_ROUTES = frozenset(
    {
        ("GET", "/api/v3/meta/get_time_series_metrics/"),
        ("GET", "/api/v3/meta/list_spaces/"),
        ("GET", "/api/v3/meta/query_data_link_metadata/"),
        ("GET", "/api/v3/meta/get_data_link_metadata/"),
        ("GET", "/api/v4/alert/alert/detail/"),
        ("POST", "/api/v4/service_web/service_list/"),
        ("POST", "/api/v4/apm_metric_web/calculate_by_range/"),
        ("GET", "/api/v4/grafana/get_directory_tree/"),
        ("GET", "/api/v4/grafana/get_dashboard_detail/"),
    }
)


def application_path(backend_path: str) -> str:
    return APPLICATION_PREFIX + backend_path.removeprefix("/api/")


def resolve_application_route(method: str, path: str) -> str | None:
    for registered_method, backend_path in APPLICATION_READ_ROUTES:
        if (method, path) == (registered_method, application_path(backend_path)):
            return backend_path
    return None


def application_urlpatterns(existing_patterns, *, installed_apis=("meta",)):
    """Bind exact aliases to the original callbacks, preserving resource checks."""
    resolver = get_resolver(tuple(existing_patterns))
    patterns = []
    for method, backend_path in sorted(APPLICATION_READ_ROUTES):
        # INSTALLED_APIS can disable v3 modules. An alias must not re-enable them.
        if backend_path.startswith("/api/v3/") and backend_path.split("/")[3] not in installed_apis:
            continue
        # A missing enabled route is a deployment error, not a silently absent API.
        match = resolver.resolve(backend_path)
        patterns.append(
            re_path(
                "^" + re.escape(application_path(backend_path).lstrip("/")) + "$",
                match.func,
                match.kwargs,
                name="application_" + method.lower() + "_" + backend_path.strip("/").replace("/", "_"),
            )
        )
    return patterns
