import copy

from alarm_backends.core.cache.strategy import StrategyCacheManager


BASE_ITEM = {
    "query_configs": [
        {
            "agg_method": "AVG",
            "agg_dimension": ["ip", "bk_cloud_id"],
            "agg_condition": [
                {"value": "0", "method": "eq", "key": "bk_cloud_id"},
                {"value": "10.0.1.11", "key": "bk_target_ip", "condition": "or", "method": "eq"},
            ],
            "agg_interval": 60,
            "metric_field": "usage",
            "result_table_id": "system.cpu_summary",
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
        }
    ],
    "expression": "A",
}


def named_config(output_list=None):
    return {
        "response_contract": " named_outputs/v1 ",
        "legacy_output_ref": " C ",
        "output_list": output_list
        or [
            {"reference_name": " A ", "expression": " A "},
            {"reference_name": " C ", "expression": " A / B * 100 "},
            {"reference_name": " B ", "expression": " B "},
        ],
    }


def test_query_md5_without_output_config_keeps_legacy_golden():
    assert StrategyCacheManager.get_query_md5(2, copy.deepcopy(BASE_ITEM)) == "4ca8defa2aed29a8371e665b610a2044"


def test_query_md5_canonicalizes_named_output_order_and_outer_whitespace():
    first = copy.deepcopy(BASE_ITEM)
    first["query_output_config"] = named_config()
    second = copy.deepcopy(BASE_ITEM)
    second["query_output_config"] = named_config(
        [
            {"reference_name": "C", "expression": "A / B * 100"},
            {"reference_name": "B", "expression": "B"},
            {"reference_name": "A", "expression": "A"},
        ]
    )

    assert StrategyCacheManager.get_query_md5(2, first) == StrategyCacheManager.get_query_md5(2, second)


def test_query_md5_changes_when_named_output_semantics_change():
    first = copy.deepcopy(BASE_ITEM)
    first["query_output_config"] = named_config()
    second = copy.deepcopy(first)
    second["query_output_config"]["output_list"][1]["expression"] = "A / B"

    assert StrategyCacheManager.get_query_md5(2, first) != StrategyCacheManager.get_query_md5(2, second)
