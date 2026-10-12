"""Persisted V1/V2 Action compatibility is unrelated to IAM V3/V4 mode."""


def is_v1_compat_enabled():
    from bkmonitor.models import GlobalConfig

    return bool(GlobalConfig.get("IAM_V1_COMPATIBLE", True))
