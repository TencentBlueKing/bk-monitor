"""在监控进程与独立 Base 进程之间选择 NodeMan 运行时配置。"""

from django.conf import settings as django_settings

from bk_monitor_base.config.nodeman import NODEMAN_V3_GATEWAY_PATH, NodeManConfig


def nodeman_v3_enabled(config: NodeManConfig) -> bool:
    if django_settings.configured and hasattr(django_settings, "ENABLE_NODEMAN_V3"):
        return django_settings.ENABLE_NODEMAN_V3
    return config.v3_enabled


def nodeman_v3_base_url(config: NodeManConfig, bk_api_url: str) -> str:
    if django_settings.configured and hasattr(django_settings, "BKNODEMAN_V3_API_BASE_URL"):
        override = django_settings.BKNODEMAN_V3_API_BASE_URL.strip()
        if override:
            return f"{override.rstrip('/')}/"
        return f"{django_settings.BK_COMPONENT_API_URL.rstrip('/')}/{NODEMAN_V3_GATEWAY_PATH}"
    return config.resolved_v3_api_base_url(bk_api_url)
