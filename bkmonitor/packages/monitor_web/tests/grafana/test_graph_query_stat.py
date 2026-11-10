"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource.exceptions import CustomException
from core.drf_resource.models import ResourceData
from monitor_web.grafana.resources.unify_query import (
    GraphPromqlQueryResource,
    GraphUnifyQueryResource,
    TimeCompareProcessor,
)

pytestmark = pytest.mark.django_db


def build_graph_unify_params() -> dict[str, Any]:
    return {
        "bk_biz_id": 2,
        "query_configs": [
            {
                "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "metrics": [{"field": "cpu_usage", "method": "AVG", "alias": "a", "display": False}],
                "functions": [],
                "filter_dict": {},
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
    @pytest.mark.parametrize("metric_infos", [None, []])
    def test_preloaded_metadata_keeps_none_and_empty_distinct(
        self, mocker: MockerFixture, metric_infos: list[dict[str, Any]] | None
    ) -> None:
        mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", return_value={})
        mocker.patch.object(GraphUnifyQueryResource, "get_target_instance", return_value=False)
        lookup = mocker.patch.object(GraphUnifyQueryResource, "get_metric_info", return_value=[])

        assert GraphUnifyQueryResource.query_with_metric_info(
            build_graph_unify_params(), metric_infos=metric_infos
        ) == {"series": [], "metrics": []}

        assert lookup.call_count == (1 if metric_infos is None else 0)

    def test_preloaded_metadata_is_isolated_between_requests(self, mocker: MockerFixture, settings: Any) -> None:
        settings.ENABLE_RESOURCE_DATA_COLLECT = False
        barrier = Barrier(2)

        def synchronize_requests() -> dict[str, Any]:
            barrier.wait(timeout=5)
            return {}

        mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", side_effect=synchronize_requests)
        mocker.patch.object(GraphUnifyQueryResource, "get_target_instance", return_value=False)
        lookup = mocker.patch.object(GraphUnifyQueryResource, "get_metric_info", return_value=[])
        metric = {
            "result_table_id": "system.cpu_summary",
            "data_label": "",
            "related_id": "",
            "metric_field": "cpu_usage",
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "extend_fields": {"time_field": "time"},
        }
        metadata = [[{**metric, "unit": unit}] for unit in ["percent", "KiB"]]

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    GraphUnifyQueryResource.query_with_metric_info, build_graph_unify_params(), metric_infos=info
                )
                for info in metadata
            ]
            results = [future.result() for future in futures]

        assert [result["metrics"] for result in results] == metadata
        lookup.assert_not_called()

    def test_preloaded_metadata_preserves_validation_and_call_records(
        self, mocker: MockerFixture, settings: Any
    ) -> None:
        settings.ENABLE_RESOURCE_DATA_COLLECT = True
        settings.RESOURCE_DATA_COLLECT_RATIO = 1
        mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", return_value={})
        target = mocker.patch.object(GraphUnifyQueryResource, "get_target_instance", return_value=False)
        create_record = mocker.patch.object(ResourceData.objects, "create")
        params = build_graph_unify_params()

        result = GraphUnifyQueryResource.query_with_metric_info(params, metric_infos=[])

        create_record.assert_called_once()
        record = create_record.call_args.kwargs
        assert record["name"] == "monitor_web.grafana.resources.unify_query.GraphUnifyQueryResource"
        assert json.loads(record["request_data"]) == {"args": [params], "kwargs": {}}
        assert json.loads(record["response_data"]) == result
        invalid_params = build_graph_unify_params()
        invalid_params.pop("start_time")

        with pytest.raises(CustomException):
            GraphUnifyQueryResource.query_with_metric_info(invalid_params, metric_infos=[])

        assert create_record.call_count == 2
        target.assert_called_once()

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
