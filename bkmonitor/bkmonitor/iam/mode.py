"""Monitor configuration-center adapter; mode rules are shared with BKLog."""

import os
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from iam_engine.core.config import DEFAULT_DUAL_STACK
from iam_engine.mode import FeatureToggleModeProvider


def get_mode_provider():
    configured = os.getenv("BKAPP_IAM_PERMISSION_MODE", "").strip().lower()
    if configured and configured not in DEFAULT_DUAL_STACK.valid_mode_values:
        raise ImproperlyConfigured(f"invalid BKAPP_IAM_PERMISSION_MODE: {configured!r}")

    def load_toggle(name):
        # DynamicSettings reads this registered field through GlobalConfig.
        # Only read it when the explicit environment override is empty.
        return SimpleNamespace(status="on", feature_config={"mode": settings.BK_IAM_PERMISSION_MODE or "v3"})

    return FeatureToggleModeProvider(load_toggle, env_loader=lambda: configured)


def get_deployment_mode_provider():
    """Read the authoritative deployment mode after DB migrations, without stale caches."""
    configured = os.getenv("BKAPP_IAM_PERMISSION_MODE", "").strip().lower()

    def load_toggle(name):
        if settings.USE_DYNAMIC_SETTINGS:
            from bkmonitor.models import GlobalConfig

            mode = GlobalConfig.get("BK_IAM_PERMISSION_MODE", "v3", raise_exception=True)
        else:
            mode = settings.BK_IAM_PERMISSION_MODE or "v3"
        return SimpleNamespace(status="on", feature_config={"mode": mode})

    return FeatureToggleModeProvider(load_toggle, env_loader=lambda: configured, raise_on_load_error=True)
