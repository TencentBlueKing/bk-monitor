import pytest

from bk_monitor_base.infras.i18n.language import Language, get_language, languages


class TestLanguage:
    """测试Language NamedTuple"""

    def test_language_creation(self):
        """测试Language对象创建"""
        lang = Language(code="en", name="en_name", frontend_code="en_f_code")
        assert lang.code == "en"
        assert lang.name == "en_name"
        assert lang.frontend_code == "en_f_code"

    def test_language_immutable(self):
        """测试Language对象不可变性"""
        lang = Language(code="en", name="en_name", frontend_code="en_f_code")
        with pytest.raises(AttributeError):
            lang.code = "zh-hans"  # type: ignore

    def test_format_db_field_key_with_chinese(self):
        """测试中文语言的format_db_field_key方法"""
        lang = Language(code="zh-hans", name="zh_hans", frontend_code="zh-cn")
        assert lang.format_db_field_key("title") == "title_zh_hans"

        lang = Language(code="zh-hant", name="zh_hant", frontend_code="zh-tw")
        assert lang.format_db_field_key("title") == "title_zh_hant"


class TestLanguagesList:
    """测试languages列表"""

    def test_languages_list_not_empty(self):
        """测试languages列表不为空"""
        assert len(languages) > 0

    def test_languages_list_contains_english(self):
        """测试languages列表包含的语言"""
        codes = [lang.code for lang in languages]
        assert "en" in codes
        assert "zh-hans" in codes
        assert "zh-hant" in codes

    def test_all_languages_have_required_fields(self):
        """测试所有语言都有必需的字段"""
        for lang in languages:
            assert lang.code
            assert lang.name
            assert lang.frontend_code


class TestGetLanguage:
    """测试get_language函数"""

    def test_get_language_by_code(self):
        """测试通过code获取语言"""
        lang = get_language(code="en")
        assert lang.code == "en"
        assert lang.name == "en"
        assert lang.frontend_code == "en"

    def test_get_language_by_code_chinese_simplified(self):
        """测试通过code获取简体中文"""
        lang = get_language(code="zh-hans")
        assert lang.code == "zh-hans"
        assert lang.name == "zh_hans"
        assert lang.frontend_code == "zh-cn"

    def test_get_language_by_code_chinese_traditional(self):
        """测试通过code获取繁体中文"""
        lang = get_language(code="zh-hant")
        assert lang.code == "zh-hant"
        assert lang.name == "zh_hant"
        assert lang.frontend_code == "zh-tw"

    def test_get_language_by_name(self):
        """测试通过name获取语言"""
        lang = get_language(name="en")
        assert lang.code == "en"
        assert lang.name == "en"

    def test_get_language_by_name_chinese(self):
        """测试通过name获取中文语言"""
        lang = get_language(name="zh_hans")
        assert lang.code == "zh-hans"
        assert lang.name == "zh_hans"

        lang = get_language(name="zh_hant")
        assert lang.code == "zh-hant"
        assert lang.name == "zh_hant"

    def test_get_language_by_frontend_code(self):
        """测试通过frontend_code获取语言"""
        lang = get_language(frontend_code="en")
        assert lang.code == "en"
        assert lang.frontend_code == "en"

    def test_get_language_by_frontend_code_chinese(self):
        """测试通过frontend_code获取中文语言"""
        lang = get_language(frontend_code="zh-cn")
        assert lang.code == "zh-hans"
        assert lang.frontend_code == "zh-cn"

        lang = get_language(frontend_code="zh-tw")
        assert lang.code == "zh-hant"
        assert lang.frontend_code == "zh-tw"

    def test_get_language_with_multiple_params(self):
        """测试同时传入多个参数（只要满足一个即可）"""
        lang = get_language(code="en", name="wrong", frontend_code="wrong")
        assert lang.code == "en"

        lang = get_language(code="wrong", name="en", frontend_code="wrong")
        assert lang.code == "en"

        lang = get_language(code="wrong", name="wrong", frontend_code="en")
        assert lang.code == "en"

    def test_get_language_invalid_code(self):
        """测试无效的code"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language(code="invalid")

    def test_get_language_invalid_name(self):
        """测试无效的name"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language(name="invalid")

    def test_get_language_invalid_frontend_code(self):
        """测试无效的frontend_code"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language(frontend_code="invalid")

    def test_get_language_no_params(self):
        """测试不传入任何参数"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language()

    def test_get_language_empty_string_params(self):
        """测试传入空字符串参数"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language(code="", name="", frontend_code="")

    def test_get_language_case_sensitive(self):
        """测试get_language是大小写敏感的"""
        with pytest.raises(ValueError, match="Invalid language"):
            get_language(code="EN")

        with pytest.raises(ValueError, match="Invalid language"):
            get_language(code="ZH-HANS")


class TestLanguageIntegration:
    """集成测试"""

    def test_language_roundtrip(self):
        """测试通过不同参数获取相同的Language对象"""
        lang1 = get_language(code="zh-hans")
        lang2 = get_language(name="zh_hans")
        lang3 = get_language(frontend_code="zh-cn")

        assert lang1 == lang2 == lang3
        assert lang1 is lang2 is lang3  # 应该是同一个对象

    def test_format_db_field_key_for_all_languages(self):
        """测试所有语言的format_db_field_key方法"""
        field_name = "title"
        expected_results = {
            "en": "title_en",
            "zh-hans": "title_zh_hans",
            "zh-hant": "title_zh_hant",
        }

        for code, expected in expected_results.items():
            lang = get_language(code=code)
            assert lang.format_db_field_key(field_name) == expected
