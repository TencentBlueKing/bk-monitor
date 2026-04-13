"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock

import pytest

from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.grafana.resources.unify_query import (
    GraphPromqlQueryResource,
    GraphUnifyQueryResource,
    TimeCompareProcessor,
)

pytestmark = pytest.mark.django_db


def build_graph_unify_params():
    return {
        "bk_biz_id": 2,
        "query_configs": [
            {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "metrics": [{"field": "cpu_usage", "method": "AVG", "alias": "a", "display": False}],
                "functions": [],
                "group_by": [],
                "interval": 60,
            }
        ],
        "expression": "a",
        "stack": "",
        "function": {},
        "functions": [],
        "start_time": 1774525980,
        "end_time": 1774529580,
        "limit": 1000,
        "slimit": 1000,
        "down_sample_range": "",
        "format": "time_series",
        "type": "range",
        "time_alignment": True,
        "null_as_zero": False,
        "query_method": "query_data_with_stat",
        "unit": "",
        "with_metric": True,
        "not_time_align": False,
    }


class TestGraphPromqlQueryResource:
    def test_promql_query_transfers_series_stat(self, mocker):
        mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", return_value={})
        mocker.patch(
            "api.unify_query.default.QueryDataByPromqlResource.perform_request",
            return_value={
                "series": [
                    {
                        "group_keys": [],
                        "group_values": [],
                        "values": [[1774525980000, 1]],
                        "stat": {"count": [0, 1]},
                    }
                ]
            },
        )

        result = GraphPromqlQueryResource().perform_request(
            {
                "bk_biz_id": 2,
                "promql": "sum(a)",
                "start_time": 1774525980,
                "end_time": 1774529580,
                "step": "1m",
                "format": "time_series",
                "type": "range",
                "down_sample_range": "",
                "time_alignment": True,
            }
        )

        assert result["series"][0]["stat"] == {"count": [0, 1]}

    def test_promql_query_fallbacks_to_empty_stat(self, mocker):
        mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", return_value={})
        mocker.patch(
            "api.unify_query.default.QueryDataByPromqlResource.perform_request",
            return_value={"series": [{"group_keys": [], "group_values": [], "values": [[1774525980000, 1]]}]},
        )

        result = GraphPromqlQueryResource().perform_request(
            {
                "bk_biz_id": 2,
                "promql": "sum(a)",
                "start_time": 1774525980,
                "end_time": 1774529580,
                "step": "1m",
                "format": "time_series",
                "type": "range",
                "down_sample_range": "",
                "time_alignment": True,
            }
        )

        assert result["series"][0]["stat"] == {}

    def test_promql_query_returns_empty_series_when_promql_is_blank(self):
        result = GraphPromqlQueryResource().perform_request(
            {
                "bk_biz_id": 2,
                "promql": "",
                "start_time": 1774525980,
                "end_time": 1774529580,
                "step": "1m",
                "format": "time_series",
                "type": "range",
                "down_sample_range": "",
                "time_alignment": True,
            }
        )

        assert result == {"metrics": [], "series": []}


class TestGraphUnifyQueryResource:
    def test_graph_unify_query_transfers_series_stat(self, mocker):
        perform_query = mocker.patch.object(
            GraphUnifyQueryResource,
            "_perform_query",
            return_value={
                "series": [{"_time_": 1774525980000, "_result_": 1}],
                "metrics": [],
                "series_stat": {((), "_result_"): {"count": [0, 1]}},
            },
        )

        result = GraphUnifyQueryResource().perform_request(build_graph_unify_params())

        perform_query.assert_called_once_with(build_graph_unify_params(), query_method_name="query_data_with_stat")
        assert result["series"][0]["stat"] == {"count": [0, 1]}

    def test_graph_unify_query_fallbacks_to_empty_stat(self, mocker):
        mocker.patch.object(
            GraphUnifyQueryResource,
            "_perform_query",
            return_value={"series": [{"_time_": 1774525980000, "_result_": 1}], "metrics": [], "series_stat": {}},
        )

        result = GraphUnifyQueryResource().perform_request(build_graph_unify_params())

        assert result["series"][0]["stat"] == {}

    def test_graph_unify_query_keeps_query_reference_behavior(self, mocker):
        params = build_graph_unify_params()
        params["query_method"] = "query_reference"
        perform_query = mocker.patch.object(
            GraphUnifyQueryResource,
            "_perform_query",
            return_value={"series": [{"_time_": 1774525980000, "_result_": 1}], "metrics": [], "series_stat": {}},
        )

        result = GraphUnifyQueryResource().perform_request(params)

        perform_query.assert_called_once_with(params, query_method_name="query_reference")
        assert result["series"][0]["stat"] == {}

    def test_graph_unify_query_handles_empty_series(self, mocker):
        mocker.patch.object(
            GraphUnifyQueryResource,
            "_perform_query",
            return_value={"series": [], "metrics": [], "series_stat": {}},
        )

        result = GraphUnifyQueryResource().perform_request(build_graph_unify_params())

        assert result == {"series": [], "metrics": []}


class TestTimeCompareProcessorStat:
    def test_process_origin_data_merges_time_compare_series_stat(self, mocker):
        mocker.patch("monitor_web.grafana.resources.unify_query.load_data_source", return_value=MagicMock())
        mock_query_cls = mocker.patch("monitor_web.grafana.resources.unify_query.UnifyQuery")
        mock_query_instance = mock_query_cls.return_value
        mock_query_instance.query_data_with_stat.return_value = {
            "series": [{"_time_": 1774439580000, "_result_": 2, "bk_target_ip": "127.0.0.1"}],
            "series_stat": {((("bk_target_ip", "127.0.0.1"),), "_result_"): {"count": [0, 2]}},
        }

        params = build_graph_unify_params()
        params["function"] = {"time_compare": ["1d"]}

        data = [{"_time_": 1774525980000, "_result_": 1, "bk_target_ip": "127.0.0.1"}]
        series_stat = {((("bk_target_ip", "127.0.0.1"),), "_result_"): {"count": [0, 1]}}

        TimeCompareProcessor.process_origin_data(params, data, series_stat)

        assert series_stat[((("bk_target_ip", "127.0.0.1"),), "_result_")] == {"count": [0, 1]}
        compare_key = ((("__time_compare", "1d"), ("bk_target_ip", "127.0.0.1")), "_result_")
        assert series_stat[compare_key] == {"count": [0, 2]}
        assert len(data) == 2
        assert data[1]["__time_compare"] == "1d"

    def test_process_origin_data_without_series_stat_uses_query_data(self, mocker):
        mocker.patch("monitor_web.grafana.resources.unify_query.load_data_source", return_value=MagicMock())
        mock_query_cls = mocker.patch("monitor_web.grafana.resources.unify_query.UnifyQuery")
        mock_query_instance = mock_query_cls.return_value
        mock_query_instance.query_data.return_value = [{"_time_": 1774439580000, "_result_": 2}]

        params = build_graph_unify_params()
        params["function"] = {"time_compare": ["1d"]}

        data = [{"_time_": 1774525980000, "_result_": 1}]

        TimeCompareProcessor.process_origin_data(params, data)

        mock_query_instance.query_data.assert_called_once()
        mock_query_instance.query_data_with_stat.assert_not_called()
