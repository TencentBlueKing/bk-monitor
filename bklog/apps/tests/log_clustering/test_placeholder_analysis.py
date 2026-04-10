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
        self.assertNotIn("FROM (", first_call_params["sql"])
        self.assertIn("GROUP BY regexp_extract(", first_call_params["sql"])
        self.assertIn("ORDER BY cnt DESC", first_call_params["sql"])
        self.assertIn("LIMIT 2", first_call_params["sql"])
        self.assertEqual(mock_chart_handler.call_args_list[0].kwargs["clustered_rt"], "2_bklog_1_clustered")

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

    def test_get_distribution_raises_when_groups_conflict_with_addition(self):
        params = {
            "signature": "deadbeef",
            "pattern": "#NUMBER#",
            "placeholder_index": 0,
            "start_time": 1710000000000,
            "end_time": 1710003600000,
            "groups": {"service_name": "api"},
            "addition": [{"field": "service_name", "operator": "is", "value": "web"}],
        }

        with self.assertRaises(ValidationError):
            PlaceholderAnalysisHandler(INDEX_SET_ID, params).get_distribution()

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
