from alarm_backends.core.cache.strategy import StrategyCacheManager
from constants.data_source import DataSourceLabel, DataTypeLabel


def test_ip_target_agg_dimensions_are_sorted_and_unique():
    dimensions = ["zone", "service", "host", "cluster", "namespace", "pod", "bk_target_ip", "zone"]
    item = {
        "query_configs": [
            {
                "metric_id": "bk_monitor.system.cpu.usage",
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "agg_dimension": dimensions,
            }
        ]
    }

    StrategyCacheManager.handle_special_query_config(2, True, item)

    assert item["query_configs"][0]["agg_dimension"] == sorted(set(dimensions))
