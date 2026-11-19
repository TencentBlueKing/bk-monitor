"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from bkmonitor.data_source.utils.apm import LevelTarget, TraceDatasourceTarget
from core.drf_resource.exceptions import CustomException
from rum_web.handlers.level.factory import RumLevelHandlerFactory
from rum_web.query.resources import RumTimeSeriesResource, RumTotalResource


REQUEST = {"bk_biz_id": 2, "app_name": "test", "start_time": 1785999600, "end_time": 1786000200}
FILTERS = [{"key": "attributes.span_type", "operator": "equal", "value": ["resource", "error"]}]


@pytest.mark.parametrize(
    "mode,precomputed", [("span", False), ("view", False), ("session", False), ("view", True), ("session", True)]
)
@pytest.mark.parametrize("count", [0, 12345])
def test_overview_uses_list_scope_and_storage_count(mocker, mode, precomputed, count):
    target = TraceDatasourceTarget.build(
        bk_biz_id=2,
        app_name="test",
        table_id="bk_rum.test.span",
        retention=3,
        levels=[LevelTarget(mode, [f"bk_rum.test.{mode}"])] if precomputed else [],
    )
    handler = RumLevelHandlerFactory.create(mode, [target])
    execute = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])
    start, end = REQUEST["start_time"], REQUEST["end_time"]
    assert handler.list_records(start, end, filters=FILTERS, query_string="status.code:2") == []
    list_config = execute.call_args.kwargs["query_body"]["query_configs"][0]
    execute.reset_mock()
    execute.return_value = [{"_result_": count}]
    assert handler.total(start, end, FILTERS, "status.code:2") == {"total": count}
    execute.assert_called_once()
    total_config = execute.call_args.kwargs["query_body"]["query_configs"][0]

    graph = mocker.patch(
        "rum_web.handlers.level.base.resource.grafana.graph_unify_query", return_value={"series": [], "metrics": []}
    )
    group_by = ["attributes.span_type"] if mode == "span" else []
    assert handler.time_series(start, end, 30, group_by, FILTERS, "status.code:2") == {
        "series": [],
        "metrics": [],
        "query_config": {"interval": 30},
    }
    graph.assert_called_once()
    request = graph.call_args.args[0]
    trend_config = request["query_configs"][0]
    field, method = ("_index", "count") if mode == "span" else (f"attributes.{mode}.id", "distinct")
    for config in (total_config, trend_config):
        assert config["table"] == list_config["table"]
        assert config["filter_dict"] == list_config["filter_dict"]
        assert config["query_string"] == list_config["query_string"] == "status.code:2"
        assert config["time_field"] == list_config["time_field"] == ("start_time" if precomputed else "end_time")
        assert config["metrics"] == [{"field": field, "method": method, "alias": "a"}]
    assert trend_config["group_by"] == (["attributes.span_type"] if mode == "span" else [])
    assert trend_config["interval"] == 30
    assert request["start_time"] == start and request["end_time"] == end
    assert request["null_as_zero"] is True and request["time_alignment"] is False


@pytest.fixture
def application(mocker):
    return mocker.patch(
        "rum_web.query.resources._get_application",
        return_value=SimpleNamespace(
            bk_biz_id=2, app_name="test", span_result_table_id="bk_rum.test.span", retention_days=3
        ),
    )


@pytest.mark.parametrize("mode,group_by", [("span", ["attributes.span_type"]), ("view", []), ("session", [])])
@pytest.mark.parametrize("interval,expected_interval", [(None, 300), ("auto", 300), (30, 30)])
def test_time_series_response_and_defaults(mocker, application, mode, group_by, interval, expected_interval):
    graph = mocker.patch(
        "rum_web.handlers.level.base.resource.grafana.graph_unify_query",
        return_value={
            "metrics": [],
            "series": [
                {
                    "target": "count",
                    "dimensions": {"attributes.span_type": "resource"} if mode == "span" else {},
                    "datapoints": [[2, 1785999600000], [0, 1785999660000]],
                }
            ],
        },
    )
    request = {**REQUEST, "mode": mode, "end_time": REQUEST["start_time"] + 10 * 3600}
    if interval is not None:
        request["interval"] = interval
    result = RumTimeSeriesResource().request(request)
    assert result == {**graph.return_value, "query_config": {"interval": expected_interval}}
    assert result["series"][0]["target"] == "count"
    config = graph.call_args.args[0]["query_configs"][0]
    assert config["interval"] == expected_interval
    assert config["group_by"] == group_by
    application.assert_called_once_with(2, "test")


def test_total_request_defaults_and_error_propagation(mocker, application):
    execute = mocker.patch(
        "bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[{"_result_": 4}]
    )
    assert RumTotalResource().request(REQUEST) == {"total": 4}
    application.assert_called_once_with(2, "test")
    execute.side_effect = RuntimeError("query failed")
    with pytest.raises(RuntimeError, match="query failed"):
        RumTotalResource().request(REQUEST)


@pytest.mark.parametrize("resource", [RumTotalResource, RumTimeSeriesResource])
@pytest.mark.parametrize("overrides", [{"mode": "invalid"}, {"start_time": None}, {"end_time": None}])
def test_overview_validates_search_parameters(resource, overrides):
    with pytest.raises(CustomException):
        resource().request({**REQUEST, **overrides})


@pytest.mark.parametrize("interval", [0, -1, 1.5])
def test_time_series_rejects_invalid_interval(interval):
    with pytest.raises(CustomException):
        RumTimeSeriesResource().request({**REQUEST, "interval": interval})
