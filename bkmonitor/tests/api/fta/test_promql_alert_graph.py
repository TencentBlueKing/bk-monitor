"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from fta_web.alert.promql import can_push_down_alert_labels, get_alert_graph_filter


@pytest.mark.parametrize(
    ("expression", "labels", "expected"),
    [
        ('metric{pod=~"api.*"} offset 1m', {"pod": "api1"}, True),
        ("(metric @ 123)", {"pod": "api1"}, True),
        ("sum by (pod)(rate(metric[5m])) > 0", {"pod": "api1"}, True),
        ("100 * sum without(instance)(metric)", {"pod": "api1"}, True),
        ("sum by (pod)(sum without(pod)(metric))", {"pod": "api1"}, False),
        ("sum(metric)", {"pod": "api1"}, False),
        ("topk by (cluster)(1, metric)", {"cluster": "east"}, True),
        ("topk by (cluster)(1, metric)", {"cluster": "east", "pod": "api1"}, False),
        ("bottomk by (pod)(scalar(n), metric)", {"pod": "api1"}, False),
        ('label_replace(metric, "dst", "$1", "pod", "(.*)")', {"pod": "api1"}, True),
        ('label_replace(metric, "dst", "$1", "pod", "(.*)")', {"dst": "api1"}, False),
        ('label_join(metric, "dst", ".", "pod", "ns")', {"dst": "api1"}, False),
        ('label_replace(metric, ("dst"), "$1", "pod", "(.*)")', {"pod": "api1"}, False),
        ("a + on(pod) group_left(version) b", {"pod": "api1"}, False),
        ("a unless b", {"pod": "api1"}, False),
        ("rate(metric[5m:1m])", {"pod": "api1"}, False),
        ("absent(metric)", {"pod": "api1"}, False),
        ("unsupported_extension(metric)", {"pod": "api1"}, False),
        ('{job="test"}', {"pod": "api1"}, False),
        ("metric", {"pod": ""}, False),
        ("metric", {"__name__": "metric"}, False),
        ("metric", {}, False),
    ],
)
def test_push_down(expression, labels, expected):
    assert can_push_down_alert_labels(expression, labels) is expected


@pytest.mark.parametrize("from_panel", [False, True])
@pytest.mark.parametrize("safe", [False, True])
def test_alert_graph_only_queries_when_labels_can_be_pushed_down(mocker, from_panel, safe):
    from bkmonitor.documents import AlertDocument
    from fta_web.alert.resources import AlertGraphQueryResource

    expr = (
        'label_replace(m,"display","$1","version","(.*)")'
        if safe
        else 'label_replace(m,"version","$1","release","(.*)")'
    )
    query = {
        "data_source_label": "prometheus",
        "data_type_label": "time_series",
        "promql": expr,
        "agg_interval": 60,
        "metric_id": "prometheus.m",
    }
    origin = {"data": {"dimension_fields": ["version"], "dimensions": {"version": "v2"}, "value": 2}}
    snapshot = {"origin_alarm": origin, "strategy": {"items": [{"query_configs": [query], "algorithms": []}]}}
    alert = AlertDocument(extra_info=snapshot, first_anomaly_time=120, event={"bk_biz_id": 2, "extra_info": snapshot})
    mocker.patch.object(AlertDocument, "get", return_value=alert)
    graph = mocker.patch(
        "fta_web.alert.resources.resource.grafana.graph_unify_query",
        return_value={
            "series": [
                {"dimensions": {"version": v}, "datapoints": [[2, 120000]], "metric_field": "_result_"} for v in ["v2"]
            ]
        },
    )
    params = {"id": 42, "bk_biz_id": 2, "start_time": 60, "end_time": 180}
    if from_panel:
        params["query_configs"] = [{**query, "promql": expr.replace("$1", "null"), "filter_dict": {"version": "v2"}}]
    result = AlertGraphQueryResource().perform_request(params)
    if not safe:
        graph.assert_not_called()
        assert result["series"] == []
        return
    sent = graph.call_args.args[0]["query_configs"][0]
    assert sent["promql"] == expr
    assert sent["filter_dict"] == {"version": "v2"}
    assert [row["dimensions"] for row in result["series"]] == [{"version": "v2"}]
    assert result["series"][0]["markPoints"] == [[2, 120000]]


def test_non_promql_graph_keeps_filters_and_series(mocker):
    from bkmonitor.documents import AlertDocument
    from fta_web.alert.resources import AlertGraphQueryResource

    config = {"data_source_label": "bk_monitor", "data_type_label": "time_series", "filter_dict": {"pod": "p"}}
    alert = AlertDocument(extra_info={"strategy": {"items": [{"query_configs": [config]}]}}, first_anomaly_time=120)
    mocker.patch.object(AlertDocument, "get", return_value=alert)
    graph = mocker.patch("fta_web.alert.resources.resource.grafana.graph_unify_query", return_value={"series": []})
    mocker.patch("fta_web.alert.resources.resource.grafana.graph_trace_query", return_value={"series": []})
    params = {"id": 42, "bk_biz_id": 2, "start_time": 60, "end_time": 180, "query_configs": [config]}
    result = AlertGraphQueryResource().perform_request(params)
    assert graph.call_args.args[0]["query_configs"][0]["filter_dict"] == {"pod": "p"}
    assert result["series"] == []


@pytest.mark.parametrize(
    ("fields", "expression", "expected"),
    [
        (["pod", "version"], "sum by (pod, version)(metric)", {"pod": "p", "version": "v2"}),
        (["pod", "missing"], "metric", None),
        (["pod", "__NO_DATA_DIMENSION__"], "metric", None),
        ([], "metric", None),
        (["pod", "version"], "topk by (pod)(1, metric)", None),
    ],
)
def test_alert_detail_visibility(mocker, fields, expression, expected):
    from bkmonitor.documents import AlertDocument
    from fta_web.alert.resources import AlertDetailResource

    config = {"data_source_label": "prometheus", "promql": expression}
    origin = {"data": {"dimension_fields": fields, "dimensions": {"pod": "p"}}}
    alert = AlertDocument(
        extra_info={"strategy": {"items": [{"query_configs": [config]}]}},
        event={"bk_biz_id": 2, "extra_info": {"origin_alarm": origin}, "tags": [{"key": "version", "value": "v2"}]},
    )
    assert get_alert_graph_filter(alert) == expected
    mocker.patch.object(AlertDocument, "get", return_value=alert)
    mocker.patch("fta_web.alert.resources.AIOPSManager.get_graph_panel", return_value={"targets": []})
    mocker.patch.object(AlertDetailResource, "get_relation_info", return_value="")
    mocker.patch(
        "fta_web.alert.resources.AlertQueryHandler.clean_document", return_value={"plugin_id": "test", "dimensions": []}
    )
    mocker.patch("fta_web.alert.resources.PluginTranslator.translate", return_value={"test": "test"})
    mocker.patch("fta_web.alert.resources.resource.alert.alert_related_info", return_value={})
    result = AlertDetailResource().perform_request({"id": "42", "bk_biz_id": 2})
    assert result["hide_graph"] is (expected is None)
