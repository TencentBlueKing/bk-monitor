from typing import NamedTuple


class Language(NamedTuple):
    code: str  # 标准code
    name: str  # 数据库字段使用
    frontend_code: str  # 前端交互使用code

    def format_db_field_key(self, field_name: str) -> str:
        return f"{field_name}_{self.name}"


languages: list[Language] = [
    Language(code="en", name="en", frontend_code="en"),
    Language(code="zh-hans", name="zh_hans", frontend_code="zh-cn"),
    Language(code="zh-hant", name="zh_hant", frontend_code="zh-tw"),
]


def get_language(code: str = "", name: str = "", frontend_code: str = "") -> Language:
    """
    获取Language对象
    code/name/frontend_code满足任一条件即返回
    """

    for lang in languages:
        if any([lang.code == code, lang.name == name, lang.frontend_code == frontend_code]):
            return lang
    else:
        raise ValueError("Invalid language")
