from django.conf import settings


_NODEMAN_INTEGRATION_MODE = settings.NODEMAN_INTEGRATION_MODE


def get_nodeman_integration_mode() -> str:
    """Return the NodeMan integration mode fixed when this module was loaded."""

    return _NODEMAN_INTEGRATION_MODE
