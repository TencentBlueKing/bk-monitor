"""从监控进程的 Django settings 读取 NodeMan 运行时配置。"""

from django.conf import settings as django_settings

NODEMAN_V3_GATEWAY_PATH = "api/bk-nodemgr/prod/"


def nodeman_v3_enabled() -> bool:
    """只有监控 settings 显式启用时才选择 V3。"""
    return django_settings.configured and getattr(django_settings, "ENABLE_NODEMAN_V3", False) is True


def nodeman_v3_base_url(bk_api_url: str) -> str:
    """沿用监控 settings 的可选覆盖地址，否则从网关根地址推导。"""
    if django_settings.configured:
        override = getattr(django_settings, "BKNODEMAN_V3_API_BASE_URL", "").strip()
        bk_api_url = getattr(django_settings, "BK_COMPONENT_API_URL", bk_api_url)
        if override:
            return f"{override.rstrip('/')}/"
    return f"{bk_api_url.rstrip('/')}/{NODEMAN_V3_GATEWAY_PATH}"
