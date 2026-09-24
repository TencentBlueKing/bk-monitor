"""
拨测应用配置
"""

from typing import final

from django.apps import AppConfig


@final
class UptimeCheckConfig(AppConfig):
    """拨测应用配置类"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "bk_monitor_base.domains.uptime_check"
    verbose_name = "拨测"
    label = "uptime_check"
