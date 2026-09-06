from django.conf import settings


_NODEMAN_INTEGRATION_MODE = settings.NODEMAN_INTEGRATION_MODE
NODEMAN_V2_BACKEND = "v2"
NODEMAN_V3_BACKEND = "v3"


def get_nodeman_integration_mode() -> str:
    """Return the NodeMan integration mode fixed when this module was loaded."""

    return _NODEMAN_INTEGRATION_MODE


def is_nodeman_v3_runtime_enabled() -> bool:
    """Whether this process must load the NodeMan V3 runtime."""

    return _NODEMAN_INTEGRATION_MODE in {"v3_fresh", "v3_gray"}


def get_new_collect_config_backend(bk_biz_id: int) -> str:
    """Select and persist the backend for a newly-created collection config."""

    if _NODEMAN_INTEGRATION_MODE == "v3_fresh":
        return NODEMAN_V3_BACKEND
    if _NODEMAN_INTEGRATION_MODE != "v3_gray":
        return NODEMAN_V2_BACKEND

    gray_biz_ids = {str(item) for item in settings.NODEMAN_V3_GRAY_BIZ_LIST}
    if str(bk_biz_id) in gray_biz_ids:
        return NODEMAN_V3_BACKEND
    return NODEMAN_V2_BACKEND
