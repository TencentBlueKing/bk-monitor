"""
动态分组应用配置
"""

from typing import final

from django.apps import AppConfig


@final
class DynamicGroupConfig(AppConfig):
    """动态分组应用配置"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "bk_monitor_base.domains.dynamic_group"
    label = "base_dynamic_group"
    verbose_name = "动态分组(Base)"
