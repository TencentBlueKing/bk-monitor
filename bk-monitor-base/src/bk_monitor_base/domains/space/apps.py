from typing import final

from django.apps import AppConfig


@final
class SpaceConfig(AppConfig):
    name = "bk_monitor_base.domains.space"
    verbose_name = "空间"
    default_auto_field = "django.db.models.BigAutoField"
