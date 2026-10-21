import pytest

from bkmonitor.utils.base62 import decode_identifier, get_dimension_display_name


@pytest.mark.parametrize(
    ("name", "display_name", "expected"),
    [
        ("base62Mm45BOZ5eM2yBMRzB", None, "所属品牌"),
        ("base62L6Z57G75BOZ5pm45", "base62L6Z57G75BOZ5pm45", "物品类型"),
        ("tags.base62Mm45BOZ5eM2yBMRzB", "base62Mm45BOZ5eM2yBMRzB", "所属品牌"),
        ("tags.base62Mm45BOZ5eM2yBMRzB", "tags.base62Mm45BOZ5eM2yBMRzB", "所属品牌"),
        ("base62Mm45BOZ5eM2yBMRzB", "品牌别名", "品牌别名"),
        ("app_name", "APM 应用（app_name）", "APM 应用（app_name）"),
        ("namespace", None, "namespace"),
        ("tags.namespace", "namespace", "namespace"),
        ("base62", None, "base62"),
        ("base62invalid!", "base62invalid!", "base62invalid!"),
    ],
)
def test_dimension_display_name(name, display_name, expected):
    assert get_dimension_display_name(name, display_name) == expected


def test_dimension_decoding_reuses_bounded_cache():
    decode_identifier.cache_clear()
    name = "base62Mm45BOZ5eM2yBMRzB"

    assert get_dimension_display_name(name) == "所属品牌"
    assert get_dimension_display_name(f"tags.{name}", name) == "所属品牌"
    assert decode_identifier.cache_info().misses == 1
    assert decode_identifier.cache_info().hits == 1
    assert decode_identifier.cache_info().maxsize == 1024
