from typing import Any

from django.conf import settings

from bk_monitor_base.infras.i18n.language import get_language


def clean_model_i18n_db_field(entity: Any, field: str) -> dict[str, str]:
    """
    从模型中清理指定字段的i18n信息并生成多语言DB字段信息
    return: {"name_zh_hans": "中文名称", "name_en": "en name"}
    """
    i18n_field = f"{field}_i18n"
    i18n_db_info: dict[str, str] = {}
    default_language = get_language(code=settings.LANGUAGE_CODE)
    default_name_value = getattr(entity, i18n_field, {}).get(default_language.frontend_code)
    if not default_name_value:
        raise AttributeError("default language value not set")
    for lang_tuple in settings.LANGUAGES:
        language = get_language(code=lang_tuple[0])
        value = getattr(entity, i18n_field, {}).get(language.frontend_code) or default_name_value
        i18n_db_info[language.format_db_field_key(field)] = value
    return i18n_db_info
