import copy

import pytest

from alarm_backends.core.cache.strategy import StrategyCacheManager
from bkmonitor.strategy.new_strategy import QueryConfig
from constants.data_source import DataSourceLabel, DataTypeLabel

LOG_QUERY_CONFIG = {
    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
    "data_type_label": DataTypeLabel.TIME_SERIES,
    "alias": "a",
    "index_set_id": 1,
    "result_table_id": "",
    "query_string": "*",
    "agg_method": "COUNT",
    "agg_interval": 60,
    "agg_dimension": [],
    "agg_condition": [
        {"key": "severity_text", "method": "eq", "value": ["ERROR"]},
        {"key": "body", "method": "exclude", "value": ["context canceled"], "condition": "and"},
    ],
    "metric_field": "_index",
}


@pytest.mark.parametrize("bk_biz_id, expected", [(2, []), (1000, ["body"]), (None, ["body"])])
def test_log_exclude_condition_supplements_dimension_only_for_black_biz(mocker, settings, bk_biz_id, expected):
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = [1000]
    strategy_model = mocker.patch("bkmonitor.strategy.new_strategy.StrategyModel")
    strategy_model.objects.filter.return_value.values_list.return_value.first.return_value = bk_biz_id
    query_config = QueryConfig(1, 1, **copy.deepcopy(LOG_QUERY_CONFIG))

    query_config.supplement_adv_condition_dimension()

    assert query_config.agg_dimension == expected


@pytest.mark.parametrize("bk_biz_id, distinguished", [(2, True), (1000, False)])
def test_log_query_md5_distinguishes_exclude_values_unless_black_biz(settings, bk_biz_id, distinguished):
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = [1000]

    def query_md5(exclude_value: str) -> str:
        config = copy.deepcopy(LOG_QUERY_CONFIG)
        config["agg_condition"][1]["value"] = [exclude_value]
        return StrategyCacheManager.get_query_md5(bk_biz_id, {"query_configs": [config], "expression": "a"})

    assert (query_md5("context canceled") != query_md5("not allowed")) is distinguished
