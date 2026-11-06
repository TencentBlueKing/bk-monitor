"""The existing BKLog IAM settings/environment contract, shared by both SaaS apps.

Keep string defaults: runtime options perform normalization. Do not infer a V4
gateway from the V3 endpoint. An empty system ID is resolved by product adapters
to their V3 system ID.
"""

import os


IAM_ENVIRONMENT = {
    "BK_IAM_PERMISSION_MODE": ("BKAPP_IAM_PERMISSION_MODE", ""),
    "BK_IAM_V4_SYSTEM_ID": ("BKAPP_IAM_V4_SYSTEM_ID", ""),
    "BK_IAM_V4_APIGATEWAY_URL": ("BKAPP_IAM_V4_API_BASE_URL", ""),
    "BK_IAM_V4_CALLBACK_APP_CODE": ("BKAPP_IAM_V4_CALLBACK_APP_CODE", ""),
    "BK_IAM_V4_CALLBACK_APP_SECRET": ("BKAPP_IAM_V4_CALLBACK_APP_SECRET", ""),
    "BK_IAM_V4_TIMEOUT": ("BK_IAM_V4_TIMEOUT", "10"),
    "BK_IAM_V4_BATCH_CHUNK_SIZE": ("BK_IAM_V4_BATCH_CHUNK_SIZE", "100"),
    "BK_IAM_V4_BATCH_MAX_WORKERS": ("BK_IAM_V4_BATCH_MAX_WORKERS", "4"),
    "BK_IAM_V4_AUTH_TOKEN_PATH": (
        "BK_IAM_V4_AUTH_TOKEN_PATH",
        "api/v1/open/rbac/model/systems/{system_id}/auth-token/",
    ),
    "BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS": ("BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS", "300"),
    "BK_IAM_V4_ADD_AUTHORIZATION_PATH": (
        "BKAPP_IAM_V4_ADD_AUTHORIZATION_PATH",
        "api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/",
    ),
    "BK_IAM_V4_GRANT_EXPIRE_DAYS": ("BK_IAM_V4_GRANT_EXPIRE_DAYS", "365"),
    "BK_IAM_V4_MODEL_BASE_PATH": ("BKAPP_IAM_V4_MODEL_BASE_PATH", "api/v1/open/rbac/model/systems/"),
    "BK_IAM_V4_MODEL_MANAGERS": ("BKAPP_IAM_V4_MODEL_MANAGERS", ""),
    "BK_IAM_V4_CALLBACK_URL": ("BKAPP_IAM_V4_CALLBACK_URL", ""),
}

_STRIPPED = {
    "BK_IAM_PERMISSION_MODE",
    "BK_IAM_V4_SYSTEM_ID",
    "BK_IAM_V4_APIGATEWAY_URL",
    "BK_IAM_V4_CALLBACK_APP_CODE",
    "BK_IAM_V4_CALLBACK_APP_SECRET",
    "BK_IAM_V4_MODEL_MANAGERS",
    "BK_IAM_V4_CALLBACK_URL",
}


def resolve_iam_gateway_url(component_api_url, *overrides, version):
    """Resolve independent gateway roots, preserving the caller's override order."""
    gateway = {"v3": "bk-iam", "v4": "bkiam"}[version]
    for value in overrides:
        if isinstance(value, str) and value.strip():
            return value.strip().rstrip("/") + "/"
    root = component_api_url.strip().rstrip("/") if isinstance(component_api_url, str) else ""
    return f"{root}/api/{gateway}/prod/" if root else ""


def load_iam_settings(environ=None, *, component_api_url=None):
    environ = os.environ if environ is None else environ
    values = {name: environ.get(env_name, default) for name, (env_name, default) in IAM_ENVIRONMENT.items()}
    for name in _STRIPPED:
        values[name] = values[name].strip()
    values["BK_IAM_PERMISSION_MODE"] = values["BK_IAM_PERMISSION_MODE"].lower()
    values["BK_IAM_V4_APIGATEWAY_URL"] = resolve_iam_gateway_url(
        component_api_url if component_api_url is not None else environ.get("BK_COMPONENT_API_URL"),
        values["BK_IAM_V4_APIGATEWAY_URL"],
        version="v4",
    )
    return values
