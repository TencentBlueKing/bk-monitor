from django.conf import settings


_NODEMAN_INTEGRATION_MODE = settings.NODEMAN_INTEGRATION_MODE
NODEMAN_V3_FRESH_MODE = "v3_fresh"


def get_nodeman_integration_mode() -> str:
    """Return the NodeMan integration mode fixed when this module was loaded."""

    return _NODEMAN_INTEGRATION_MODE


def is_nodeman_v3() -> bool:
    """Whether this process is bound to the NodeMan V3-only backend."""

    return get_nodeman_integration_mode() == NODEMAN_V3_FRESH_MODE
