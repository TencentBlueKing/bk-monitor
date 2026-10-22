"""Persisted V1/V2 Action compatibility is unrelated to IAM V3/V4 mode."""

from cachetools.func import ttl_cache


@ttl_cache(ttl=60)
def is_v1_compat_enabled():
    # 开关由 iam_upgrade_action_v2 写入 monitor 的 GlobalConfig；未安装 monitor 的角色或无记录时保持兼容
    try:
        from monitor.models import GlobalConfig

        return bool(GlobalConfig.objects.get(key="IAM_V1_COMPATIBLE").value)
    except Exception:  # pylint: disable=broad-except
        return True
