import copy

import pytest

from alarm_backends.core.cache.strategy import StrategyCacheManager


BASE_ITEM = {
    "query_configs": [
        {
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": alias,
            "promql": f"metric_{alias}",
            "agg_interval": 60,
        }
        for alias in ("a", "b")
    ],
    "expression": "a / b",
}
OUTPUT_CONFIG = {
    "response_contract": "named_outputs/v1",
    "legacy_output_ref": "RESULT",
    "output_list": [
        {"reference_name": "A", "expression": "a"},
        {"reference_name": "RESULT", "expression": "a / b"},
    ],
}


def make_item(named=False, lookback=None, mode="omitted"):
    item = copy.deepcopy(BASE_ITEM)
    if named:
        item["query_output_config"] = copy.deepcopy(OUTPUT_CONFIG)
    if lookback is not None:
        item["access_lookback_periods"] = lookback
    if mode != "omitted":
        for index, query_config in enumerate(item["query_configs"]):
            query_config["expression_mode"] = ("promql" if index == 0 else None) if mode == "partial" else mode
    return item


@pytest.mark.parametrize("mode", ["omitted", None, "", "partial"])
@pytest.mark.parametrize(
    "named,lookback,legacy",
    [
        (False, None, "b0ed3ba59eaaec5d144ebf3c38e5f59a"),
        (False, 3, "9877e8e10d02194e1f42b3d904034369"),
        (True, None, "2fda897fe168a8b1656b5cae278e212d"),
        (True, 3, "219adfea91be9e82f98f94d79a87a922"),
    ],
)
def test_legacy_promql_hashes_remain_unchanged(mode, named, lookback, legacy):
    # 固定值取自修复前的实现，覆盖旧查询及命名输出、回溯窗口的组合。
    item = make_item(named, lookback, mode)
    assert StrategyCacheManager.get_query_md5(2, item) == legacy
    if lookback is None:
        assert StrategyCacheManager.get_query_md5(2, dict(item, access_lookback_periods=None)) == legacy


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("lookback", [None, 3])
def test_new_promql_mode_has_a_separate_query_group(named, lookback):
    legacy = make_item(named, lookback)
    current = make_item(named, lookback, "promql")
    assert StrategyCacheManager.get_query_md5(2, current) != StrategyCacheManager.get_query_md5(2, legacy)


@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("lookback", [None, 3])
def test_promql_alias_bindings_are_part_of_query_identity(named, lookback):
    first = make_item(named, lookback, "promql")
    second = copy.deepcopy(first)
    second["query_configs"][0]["alias"] = "b"
    second["query_configs"][1]["alias"] = "a"
    assert StrategyCacheManager.get_query_md5(2, first) != StrategyCacheManager.get_query_md5(2, second)


def test_promql_query_order_and_item_id_do_not_change_identity():
    first = dict(make_item(mode="promql"), id=1)
    second = copy.deepcopy(first)
    second["id"] = 2
    second["query_configs"].reverse()
    original = copy.deepcopy(first)
    assert StrategyCacheManager.get_query_md5(2, first) == StrategyCacheManager.get_query_md5(2, second)
    assert first == original


@pytest.mark.parametrize("mode", ["omitted", "promql"])
def test_single_promql_query_keeps_legacy_identity(mode):
    item = make_item(mode=mode)
    item["query_configs"] = item["query_configs"][:1]
    item["expression"] = "a"
    assert StrategyCacheManager.get_query_md5(2, item) == "83bd2ff57c1bec1800757880193015e6"


@pytest.mark.parametrize("mode", ["omitted", "promql"])
def test_non_prometheus_queries_keep_legacy_identity(mode):
    item = make_item(mode=mode)
    for query_config in item["query_configs"]:
        query_config["data_source_label"] = "bk_monitor"
    assert StrategyCacheManager.get_query_md5(2, item) == "0771046f64acc47e1aadfce8d1e65fea"
