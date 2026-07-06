from bkmonitor.utils.metric_id import build_metric_check_key, build_metric_id_filter_queries
from constants.data_source import DataSourceLabel, DataTypeLabel


def test_build_metric_id_filter_queries_adds_custom_time_series_data_label_fallback():
    queries = build_metric_id_filter_queries(
        {
            "data_source_label": DataSourceLabel.CUSTOM,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "result_table_id": "system_base",
            "metric_field": "host_timesync_query_seconds_min",
        }
    )

    assert len(queries) == 2
    assert dict(queries[0].children) == {
        "data_source_label": DataSourceLabel.CUSTOM,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "result_table_id": "system_base",
        "metric_field": "host_timesync_query_seconds_min",
    }
    assert dict(queries[1].children) == {
        "data_source_label": DataSourceLabel.CUSTOM,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_label": "system_base",
        "metric_field": "host_timesync_query_seconds_min",
    }


def test_build_metric_id_filter_queries_adds_bk_monitor_time_series_data_label_fallback():
    queries = build_metric_id_filter_queries(
        {
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "result_table_id": "system_base",
            "metric_field": "host_timesync_query_seconds_min",
        }
    )

    assert len(queries) == 2
    assert dict(queries[1].children) == {
        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "data_label": "system_base",
        "metric_field": "host_timesync_query_seconds_min",
    }


def test_build_metric_id_filter_queries_normalizes_index_set_id():
    queries = build_metric_id_filter_queries(
        {
            "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "index_set_id": "123",
            "metric_field": "log_count",
        }
    )

    assert len(queries) == 1
    assert dict(queries[0].children) == {
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "related_id": "123",
        "metric_field": "log_count",
    }


def test_build_metric_check_key_is_isolated_by_biz():
    metric_id = "custom.system_base.host_timesync_query_seconds_min"

    assert build_metric_check_key("system", 2, metric_id) != build_metric_check_key("system", 3, metric_id)
