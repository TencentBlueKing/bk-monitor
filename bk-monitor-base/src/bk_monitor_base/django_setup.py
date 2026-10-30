import django
from django.conf import settings

from bk_monitor_base.config import get_config
from bk_monitor_base.infras.symmetric_field import ensure_symmetric_field_copy_compatibility


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
    ensure_symmetric_field_copy_compatibility()
    django.setup()
