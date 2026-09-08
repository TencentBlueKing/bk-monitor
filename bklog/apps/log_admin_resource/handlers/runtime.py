"""Resource Call handlers for BKLog runtime metadata."""

from typing import Any

from django.conf import settings


FUNC_NAME = "bklog.runtime.version.snapshot"


def get_runtime_version_snapshot(_params: dict[str, Any]) -> dict[str, str]:
    """Return runtime metadata backed by existing BKLog settings."""
    return {
        "app_code": str(getattr(settings, "APP_CODE", "") or ""),
        "version": str(getattr(settings, "VERSION", "") or ""),
    }


FUNCTIONS = {
    FUNC_NAME: {
        "func_name": FUNC_NAME,
        "description": "Read the deployed BKLog application identity and version.",
        "notes": (
            "version comes from settings.VERSION, which reads the VERSION file in the deployed artifact; "
            "Git commit and build time are intentionally omitted until the build pipeline provides "
            "authoritative values."
        ),
        "safety_level": "read",
        "validate_params": True,
        "params_schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "response_schema": {
            "type": "object",
            "properties": {
                "app_code": {"type": "string"},
                "version": {"type": "string"},
            },
            "required": ["app_code", "version"],
            "additionalProperties": False,
        },
        "examples": [{"params": {}}],
    }
}


HANDLERS = {FUNC_NAME: get_runtime_version_snapshot}
