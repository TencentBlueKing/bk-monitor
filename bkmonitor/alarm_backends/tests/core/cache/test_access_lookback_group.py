import copy

import pytest

from alarm_backends.core.cache.strategy import StrategyCacheManager

from .test_named_output_query_md5 import BASE_ITEM, named_config


@pytest.mark.parametrize(
    "expression,named,legacy",
    [
        ("A", False, "4ca8defa2aed29a8371e665b610a2044"),
        ("A", True, "d8a1552078c98c6bd7d3187f4f20d1cc"),
        ("A+B", False, "72ece83414d03e832776ce2af4b52b24"),
        ("A+B", True, "a42d078cd6dece1e8f752d3642fbf2ad"),
    ],
)
def test_omitted_or_null_lookback_keeps_existing_query_identity(expression, named, legacy):
    item = copy.deepcopy(BASE_ITEM)
    item["expression"] = expression
    if named:
        item["query_output_config"] = named_config()
    # 固定值来自变更前的 get_query_md5，避免以新实现自证兼容。
    assert StrategyCacheManager.get_query_md5(2, item) == legacy
    assert StrategyCacheManager.get_query_md5(2, dict(item, access_lookback_periods=None)) == legacy
    explicit = dict(item, access_lookback_periods=1)
    assert StrategyCacheManager.get_query_md5(2, explicit) != legacy
    assert StrategyCacheManager.get_query_md5(2, dict(item, access_lookback_periods=15)) != legacy
    assert StrategyCacheManager.get_query_md5(2, dict(item, access_lookback_periods=15)) != (
        StrategyCacheManager.get_query_md5(2, explicit)
    )
    assert "access_lookback_periods" not in item


def test_same_query_and_lookback_can_share_across_items():
    first = dict(copy.deepcopy(BASE_ITEM), id=1, access_lookback_periods=15)
    second = dict(copy.deepcopy(BASE_ITEM), id=2, access_lookback_periods=15)
    assert StrategyCacheManager.get_query_md5(2, first) == StrategyCacheManager.get_query_md5(2, second)


def test_default_setting_does_not_change_unconfigured_group(settings):
    settings.NUM_OF_COUNT_FREQ_ACCESS = 15
    assert StrategyCacheManager.get_query_md5(2, BASE_ITEM) == "4ca8defa2aed29a8371e665b610a2044"
