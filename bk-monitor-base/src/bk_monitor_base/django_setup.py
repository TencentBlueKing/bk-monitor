import django
from django.conf import settings

from bk_monitor_base.config import get_config


def django_setup() -> None:
    """
    Django 项目初始化
    """

    # 判断是否已经初始化
    if settings.configured:
        return

    settings.configure(
        **get_config().django.model_dump(by_alias=True), **get_config().metadata.model_dump(by_alias=True)
    )
    django.setup()
