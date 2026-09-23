"""在监控进程与独立 Base 进程之间选择 NodeMan 运行时配置。"""

from django.conf import settings as django_settings

from bk_monitor_base.config.nodeman import NODEMAN_V3_GATEWAY_PATH, is_nodeman_v3_enabled
from bk_monitor_base.config.nodeman import nodeman_v3_base_url as standalone_v3_base_url


def nodeman_v3_enabled() -> bool:
    if django_settings.configured and hasattr(django_settings, "ENABLE_NODEMAN_V3"):
        return django_settings.ENABLE_NODEMAN_V3
    return is_nodeman_v3_enabled()


def nodeman_v3_base_url(bk_api_url: str) -> str:
    if django_settings.configured and hasattr(django_settings, "BKNODEMAN_V3_API_BASE_URL"):
        override = django_settings.BKNODEMAN_V3_API_BASE_URL.strip()
        if override:
            return f"{override.rstrip('/')}/"
        return f"{django_settings.BK_COMPONENT_API_URL.rstrip('/')}/{NODEMAN_V3_GATEWAY_PATH}"
    return standalone_v3_base_url(bk_api_url)
