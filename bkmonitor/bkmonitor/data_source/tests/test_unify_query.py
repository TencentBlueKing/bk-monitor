"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import nullcontext
from unittest.mock import MagicMock

import pytest

from bkmonitor.data_source.unify_query.query import UnifyQuery


@pytest.fixture
def mock_query_metrics(mocker):
    time_metric = mocker.patch("bkmonitor.data_source.unify_query.query.metrics.DATASOURCE_QUERY_TIME")
    time_metric.labels.return_value.time.return_value = nullcontext()

    count_metric = mocker.patch("bkmonitor.data_source.unify_query.query.metrics.DATASOURCE_QUERY_COUNT")
    count_metric.labels.return_value.inc.return_value = None

    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.StatusEnum.from_exc", return_value="success")


def build_unify_query() -> UnifyQuery:
    data_source = MagicMock()
    data_source.metrics = [{"field": "cpu_usage"}]
    data_source.data_source_label = "bk_monitor"
    data_source.data_type_label = "time_series"
    data_source.table = "system.cpu_summary"
    return UnifyQuery(bk_biz_id=2, data_sources=[data_source], expression="a")


class TestUnifyQuery:
    def test_query_unify_query_extracts_series_stat(self, mocker):
        query = build_unify_query()
        span = MagicMock()
        mocker.patch.object(query, "get_unify_query_params", return_value={"query_list": [{"reference_name": "a"}]})
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.tracer.start_as_current_span", return_value=nullcontext(span)
        )
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_data",
            return_value={
                "series": [
                    {
                        "columns": ["_time", "_value"],
                        "types": ["float", "float"],
                        "group_keys": ["bk_target_ip"],
                        "group_values": ["127.0.0.1"],
                        "values": [[1774525980000, 1]],
                        "stat": {"count": [0, 1]},
                    }
                ],
                "is_partial": False,
            },
        )
        mocker.patch.object(query, "process_data_by_datasource", side_effect=lambda records: records)

        records, is_partial, series_stat = query._query_unify_query(start_time=1774525980000, end_time=1774526040000)

        assert is_partial is False
        assert records == [{"bk_target_ip": "127.0.0.1", "_time_": 1774525980000, "_result_": 1}]
        assert series_stat == {((("bk_target_ip", "127.0.0.1"),), "_result_"): {"count": [0, 1]}}

    def test_query_unify_query_compatible_without_series_stat(self, mocker):
        query = build_unify_query()
        span = MagicMock()
        mocker.patch.object(query, "get_unify_query_params", return_value={"query_list": [{"reference_name": "a"}]})
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.tracer.start_as_current_span", return_value=nullcontext(span)
        )
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_data",
            return_value={
                "series": [
                    {
                        "columns": ["_time", "_value"],
                        "types": ["float", "float"],
                        "group_keys": [],
                        "group_values": [],
                        "values": [[1774525980000, 1]],
                    }
                ],
                "is_partial": False,
            },
        )
        mocker.patch.object(query, "process_data_by_datasource", side_effect=lambda records: records)

        _, _, series_stat = query._query_unify_query(start_time=1774525980000, end_time=1774526040000)

        assert series_stat == {(((), "_result_")): {}}

    def test_query_unify_query_maps_reference_name_stat_to_result_field(self, mocker):
        query = build_unify_query()
        span = MagicMock()
        mocker.patch.object(query, "get_unify_query_params", return_value={"query_list": [{"reference_name": "a"}]})
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.tracer.start_as_current_span", return_value=nullcontext(span)
        )
        mocker.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_data",
            return_value={
                "series": [
                    {
                        "columns": ["_time", "a"],
                        "types": ["float", "float"],
                        "group_keys": [],
                        "group_values": [],
                        "values": [[1774525980000, 1]],
                        "stat": {"count": [0, 1]},
                    }
                ],
                "is_partial": False,
            },
        )
        mocker.patch.object(query, "process_data_by_datasource", side_effect=lambda records: records)

        _, _, series_stat = query._query_unify_query(start_time=1774525980000, end_time=1774526040000)

        assert series_stat == {(((), "_result_")): {"count": [0, 1]}}

    def test_query_data_with_stat_returns_series_stat_for_datasource_query(self, mocker, mock_query_metrics):
        query = build_unify_query()
        mocker.patch.object(query, "process_data_sources")
        mocker.patch.object(query, "get_observe_labels", return_value={"data_source_label": "bk_monitor"})
        mocker.patch.object(query, "use_unify_query", return_value=False)
        stat = {((("device_name", "/dev/vda1"),), "_result_"): {"count": [0, 1]}}
        mocker.patch.object(query, "_query_data_using_datasource", return_value=([{"_result_": 1}], stat))

        result = query.query_data_with_stat(start_time=1774525980000, end_time=1774526040000)

        assert result == {"series": [{"_result_": 1}], "series_stat": stat}

    def test_query_data_keeps_original_return_type(self, mocker, mock_query_metrics):
        query = build_unify_query()
        mocker.patch.object(query, "process_data_sources")
        mocker.patch.object(query, "get_observe_labels", return_value={"data_source_label": "bk_monitor"})
        mocker.patch.object(query, "use_unify_query", return_value=True)
        mocker.patch.object(
            query, "_query_unify_query", return_value=([{"_result_": 1}], False, {((), "_result_"): {}})
        )

        result = query.query_data(start_time=1774525980000, end_time=1774526040000)

        assert result == [{"_result_": 1}]

    def test_query_data_using_datasource_with_stat(self, mocker, mock_query_metrics):
        """当 datasource 提供 query_data_with_stat 时，_query_data_using_datasource 应提取 series_stat。"""
        query = build_unify_query()
        datasource = query.data_sources[0]
        stat = {((("device_name", "/dev/vda1"),), "_result_"): {"count": [0, 61]}}
        datasource.query_data_with_stat = MagicMock(return_value=([{"_result_": 1, "_time_": 100}], stat))
        datasource.metrics = []

        data, series_stat = query._query_data_using_datasource(
            start_time=1774525980000, end_time=1774526040000, with_series_stat=True
        )

        datasource.query_data_with_stat.assert_called_once()
        datasource.query_data.assert_not_called()
        assert series_stat == stat

    def test_query_data_using_datasource_without_stat_falls_back(self, mocker, mock_query_metrics):
        """当 with_series_stat=False 或 datasource 无 query_data_with_stat 时，走原有 query_data 路径。"""
        query = build_unify_query()
        datasource = query.data_sources[0]
        datasource.query_data = MagicMock(return_value=[{"_result_": 1, "_time_": 100}])
        datasource.metrics = []
        del datasource.query_data_with_stat

        data, series_stat = query._query_data_using_datasource(
            start_time=1774525980000, end_time=1774526040000, with_series_stat=True
        )

        datasource.query_data.assert_called_once()
        assert series_stat == {}
