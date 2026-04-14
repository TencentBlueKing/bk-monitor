import base64
import json
from unittest.mock import patch

from django.test import TestCase

from apps.exceptions import ValidationError
from apps.log_clustering.constants import StorageTypeEnum
from apps.log_clustering.exceptions import PlaceholderAnalysisNotSupportedException
from apps.log_clustering.handlers.placeholder_analysis import PlaceholderAnalysisHandler
from apps.log_clustering.models import ClusteringConfig

INDEX_SET_ID = 9527


def encode_predefined_variables(variables):
    return base64.b64encode(json.dumps(variables).encode("utf-8")).decode("utf-8")


class TestPlaceholderAnalysisHandler(TestCase):
    def setUp(self):
        self.predefined_variables = encode_predefined_variables(
            [
                r"PATH:[^ ]+",
                r"NUMBER:\d+",
            ]
        )
        ClusteringConfig.objects.create(
            index_set_id=INDEX_SET_ID,
            min_members=1,
            max_dist_list="0.1,0.3,0.5",
            predefined_varibles=self.predefined_variables,
            delimeter="",
            max_log_length=1024,
            clustering_fields="log",
            bk_biz_id=2,
            group_fields=["service_name"],
            storage_type=StorageTypeEnum.DORIS.value,
            clustered_rt="2_bklog_1_clustered",
        )

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_distribution_returns_distribution_for_doris(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}, {"val": "500", "cnt": 4}]},
            {"list": [{"unique_count": 3}]},
            {"list": [{"total_count": 10}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
            "limit": 2,
            "groups": {"service_name": "api"},
            "addition": [{"field": "level", "operator": "is", "value": "error"}],
            "keyword": "request failed",
        }

        result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

        self.assertEqual(
            result,
            {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "unique_count": 3,
                "total_count": 10,
                "values": [
                    {"value": "404", "count": 6, "percentage": 60.0},
                    {"value": "500", "count": 4, "percentage": 40.0},
                ],
            },
        )
        first_call_params = mock_chart_handler.call_args_list[0].args[0]
        self.assertEqual(first_call_params["bk_biz_id"], 2)
        self.assertEqual(
            first_call_params["addition"],
            [
                {"field": "level", "operator": "is", "value": "error"},
                {"field": "service_name", "operator": "is", "value": "api", "condition": "and"},
            ],
        )
        self.assertIn("WHERE __dist_05 = 'deadbeef'", first_call_params["sql"])
        self.assertIn("FROM (SELECT regexp_extract(", first_call_params["sql"])
        self.assertIn("GROUP BY val", first_call_params["sql"])
        self.assertIn("ORDER BY cnt DESC", first_call_params["sql"])
        self.assertIn("LIMIT 2", first_call_params["sql"])
        self.assertEqual(mock_chart_handler.call_args_list[0].kwargs["clustered_rt"], "2_bklog_1_clustered")

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_distribution_uses_requested_pattern_level(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}]},
            {"list": [{"unique_count": 1}]},
            {"list": [{"total_count": 6}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "03",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

        first_call_params = mock_chart_handler.call_args_list[0].args[0]
        self.assertIn("WHERE __dist_03 = 'deadbeef'", first_call_params["sql"])
        self.assertNotIn("__dist_05 = 'deadbeef'", first_call_params["sql"])

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_distribution_supports_value_keyword_fuzzy_search(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}]},
            {"list": [{"unique_count": 1}]},
            {"list": [{"total_count": 6}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "value_keyword": "40",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

        distribution_sql = mock_chart_handler.call_args_list[0].args[0]["sql"]
        unique_count_sql = mock_chart_handler.call_args_list[1].args[0]["sql"]
        total_count_sql = mock_chart_handler.call_args_list[2].args[0]["sql"]
        self.assertIn("AND INSTR(val, '40') > 0", distribution_sql)
        self.assertIn("AND INSTR(val, '40') > 0", unique_count_sql)
        self.assertIn("AND INSTR(val, '40') > 0", total_count_sql)

    def test_get_distribution_raises_for_non_doris_storage(self):
        ClusteringConfig.objects.filter(index_set_id=INDEX_SET_ID).update(
            storage_type=StorageTypeEnum.ELASTICSEARCH.value
        )
        params = {
            "signature": "deadbeef",
            "pattern": "#NUMBER#",
            "placeholder_index": 0,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        with self.assertRaises(PlaceholderAnalysisNotSupportedException):
            PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

    def test_merge_groups_accepts_temporary_group_fields(self):
        params = {
            "signature": "deadbeef",
            "pattern": "#NUMBER#",
            "placeholder_index": 0,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
            "groups": {"temporary_group": "api", "service_name": "web"},
        }

        handler = PlaceholderAnalysisHandler(INDEX_SET_ID, params)
        self.assertEqual(
            handler._merge_groups_into_addition(),
            [
                {"field": "temporary_group", "operator": "is", "value": "api", "condition": "and"},
                {"field": "service_name", "operator": "is", "value": "web", "condition": "and"},
            ],
        )

    def test_get_distribution_raises_when_placeholder_index_out_of_range(self):
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #NUMBER#",
            "placeholder_index": 1,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        with self.assertRaises(ValidationError):
            PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

    def test_value_keyword_filter_uses_instr_with_escaped_literal(self):
        handler = PlaceholderAnalysisHandler(
            INDEX_SET_ID,
            {
                "signature": "deadbeef",
                "pattern": "#NUMBER#",
                "placeholder_index": 0,
                "value_keyword": r"100%_o'clock\path",
                "start_time": 1710000000000,
                "end_time": 1710003600000,
            },
        )

        self.assertEqual(
            handler._build_value_keyword_filter(),
            r" AND INSTR(val, '100%_o''clock\\path') > 0",
        )

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_trend_returns_overall_and_selected_series(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"bucket": 1710000000000, "cnt": 10}, {"bucket": 1710003600000, "cnt": 15}]},
            {"list": [{"bucket": 1710000000000, "cnt": 3}, {"bucket": 1710003600000, "cnt": 5}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "03",
            "value": "404",
            "interval": "4h",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_trend()

        self.assertEqual(
            result,
            {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "selected_value": "404",
                "interval": "4h",
                "overall": [
                    {"time": 1710000000000, "count": 10},
                    {"time": 1710003600000, "count": 15},
                ],
                "selected": [
                    {"time": 1710000000000, "count": 3},
                    {"time": 1710003600000, "count": 5},
                ],
            },
        )

        overall_sql = mock_chart_handler.call_args_list[0].args[0]["sql"]
        selected_sql = mock_chart_handler.call_args_list[1].args[0]["sql"]
        self.assertIn("WHERE __dist_03 = 'deadbeef'", overall_sql)
        self.assertIn("GROUP BY CAST(FLOOR(dtEventTimeStamp / 14400000) * 14400000 AS BIGINT)", overall_sql)
        self.assertNotIn("= '404'", overall_sql)
        self.assertIn("= '404'", selected_sql)

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_trend_auto_interval_uses_date_histogram_style_resolution(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [{"list": []}]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "interval": "auto",
            "start_time": 1710000000000,
            "end_time": 1710001800000,
        }

        result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_trend()

        self.assertEqual(result["interval"], "1m")
        overall_sql = mock_chart_handler.call_args_list[0].args[0]["sql"]
        self.assertIn("GROUP BY CAST(FLOOR(dtEventTimeStamp / 60000) * 60000 AS BIGINT)", overall_sql)

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_trend_skips_selected_query_when_value_is_empty(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"bucket": 1710000000000, "cnt": 10}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "value": "",
            "interval": "1h",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_trend()

        self.assertEqual(result["selected"], [])
        self.assertEqual(len(mock_chart_handler.call_args_list), 1)

    def test_get_trend_raises_when_interval_is_invalid(self):
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "interval": "abc",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        with self.assertRaises(ValidationError):
            PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_trend()

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_trend_auto_interval_uses_histogram_boundaries(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": []},
            {"list": []},
            {"list": []},
            {"list": []},
            {"list": []},
            {"list": []},
            {"list": []},
            {"list": []},
        ]
        cases = [
            (60 * 60 * 1000, "1m", 60000),
            (6 * 60 * 60 * 1000, "5m", 300000),
            (72 * 60 * 60 * 1000, "1h", 3600000),
            (72 * 60 * 60 * 1000 + 1, "1d", 86400000),
        ]

        for duration_ms, expected_interval, expected_bucket_ms in cases:
            params = {
                "signature": "deadbeef",
                "pattern": "prefix #PATH# middle #NUMBER# suffix",
                "placeholder_index": 1,
                "value": "404",
                "interval": "auto",
                "start_time": 1710000000000,
                "end_time": 1710000000000 + duration_ms,
            }

            result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_trend()
            self.assertEqual(result["interval"], expected_interval)
            overall_sql = mock_chart_handler.call_args_list[-2].args[0]["sql"]
            self.assertIn(
                f"GROUP BY CAST(FLOOR(dtEventTimeStamp / {expected_bucket_ms}) * {expected_bucket_ms} AS BIGINT)",
                overall_sql,
            )

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_samples_returns_logs_for_selected_value(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.return_value = {
            "list": [
                {
                    "dtEventTimeStamp": "1710000000000",
                    "serverIp": "1.1.1.1",
                    "message": "request failed, code=404",
                },
                {
                    "dtEventTimeStamp": "1709996400000",
                    "serverIp": "1.1.1.2",
                    "message": "request failed again, code=404",
                },
            ],
            "total_records": 2,
            "result_schema": [
                {"field_alias": "dtEventTimeStamp"},
                {"field_alias": "serverIp"},
                {"field_alias": "message"},
            ],
            "select_fields_order": ["dtEventTimeStamp", "serverIp", "message"],
        }
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "03",
            "value": "404",
            "limit": 2,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        result = PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_samples()

        self.assertEqual(
            result,
            {
                "placeholder_name": "NUMBER",
                "placeholder_index": 1,
                "selected_value": "404",
                "samples": [
                    {
                        "dtEventTimeStamp": "1710000000000",
                        "serverIp": "1.1.1.1",
                        "message": "request failed, code=404",
                    },
                    {
                        "dtEventTimeStamp": "1709996400000",
                        "serverIp": "1.1.1.2",
                        "message": "request failed again, code=404",
                    },
                ],
                "total_records": 2,
                "result_schema": [
                    {"field_alias": "dtEventTimeStamp"},
                    {"field_alias": "serverIp"},
                    {"field_alias": "message"},
                ],
                "select_fields_order": ["dtEventTimeStamp", "serverIp", "message"],
            },
        )
        sql = mock_chart_handler.call_args.args[0]["sql"]
        self.assertIn("SELECT *", sql)
        self.assertIn("WHERE __dist_03 = 'deadbeef'", sql)
        self.assertIn("AND regexp_extract(log,", sql)
        self.assertIn("= '404'", sql)
        self.assertIn("ORDER BY dtEventTimeStamp DESC", sql)
        self.assertIn("LIMIT 2", sql)

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_get_samples_injects_groups_into_addition(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.return_value = {
            "list": [],
            "total_records": 0,
            "result_schema": [],
            "select_fields_order": [],
        }
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "value": "404",
            "limit": 5,
            "groups": {"service_name": "api"},
            "addition": [{"field": "level", "operator": "is", "value": "error"}],
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_samples()

        call_params = mock_chart_handler.call_args.args[0]
        self.assertEqual(
            call_params["addition"],
            [
                {"field": "level", "operator": "is", "value": "error"},
                {"field": "service_name", "operator": "is", "value": "api", "condition": "and"},
            ],
        )
        self.assertIn("LIMIT 5", call_params["sql"])

    def test_get_samples_raises_when_value_is_empty(self):
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "value": "",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        with self.assertRaises(ValidationError):
            PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_samples()

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_export_distribution_returns_distribution_csv(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}, {"val": "500", "cnt": 4}]},
            {"list": [{"total_count": 10}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "pattern_level": "03",
            "limit": 2,
            "groups": {"service_name": "api"},
            "addition": [{"field": "level", "operator": "is", "value": "error"}],
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        export_bytes = b"".join(PlaceholderAnalysisHandler(INDEX_SET_ID, params).export_distribution())
        export_text = export_bytes.decode("utf-8")

        self.assertIn("value,count,percentage", export_text)
        self.assertIn("404,6,60.00%", export_text)
        self.assertIn("500,4,40.00%", export_text)
        call_params = mock_chart_handler.call_args_list[0].args[0]
        self.assertIn("WHERE __dist_03 = 'deadbeef'", call_params["sql"])
        self.assertIn("ORDER BY cnt DESC", call_params["sql"])
        self.assertIn("LIMIT 10000", call_params["sql"])
        self.assertEqual(
            call_params["addition"],
            [
                {"field": "level", "operator": "is", "value": "error"},
                {"field": "service_name", "operator": "is", "value": "api", "condition": "and"},
            ],
        )

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_export_distribution_ignores_request_limit(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}]},
            {"list": [{"total_count": 6}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "limit": 2,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        b"".join(PlaceholderAnalysisHandler(INDEX_SET_ID, params).export_distribution())

        call_params = mock_chart_handler.call_args_list[0].args[0]
        self.assertIn("LIMIT 10000", call_params["sql"])
        self.assertNotIn("LIMIT 2", call_params["sql"])

    @patch("apps.log_clustering.handlers.placeholder_analysis.ClusteringUnifyQueryChartHandler")
    def test_export_distribution_supports_value_keyword_fuzzy_search(self, mock_chart_handler):
        mock_chart_handler.return_value.get_chart_data.side_effect = [
            {"list": [{"val": "404", "cnt": 6}]},
            {"list": [{"total_count": 6}]},
        ]
        params = {
            "signature": "deadbeef",
            "pattern": "prefix #PATH# middle #NUMBER# suffix",
            "placeholder_index": 1,
            "value_keyword": "40",
            "start_time": 1710000000000,
            "end_time": 1710003600000,
        }

        b"".join(PlaceholderAnalysisHandler(INDEX_SET_ID, params).export_distribution())

        distribution_sql = mock_chart_handler.call_args_list[0].args[0]["sql"]
        total_count_sql = mock_chart_handler.call_args_list[1].args[0]["sql"]
        self.assertIn("AND INSTR(val, '40') > 0", distribution_sql)
        self.assertIn("AND INSTR(val, '40') > 0", total_count_sql)
