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
from rest_framework.exceptions import ValidationError

from fta_web.alert.promql import can_push_down_alert_labels, prepare_alert_labels, select_alert_series


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


def test_snapshot_labels_and_query_scope():
    labels = {"pod": "p", "published": "v2", "app_id": "app"}
    origin = {"dimension_fields": list(labels), "dimensions": {"pod": "p", "published": "v2", "workload": "w"}}
    extra = {"scope": "s"}
    configs = [{"promql": "a + on(app_id) group_left(published) b", "filter_dict": {**labels, **extra}}]
    assert prepare_alert_labels(configs, origin, [{"key": "app_id", "value": "app"}], []) == (labels, True)
    assert configs[0]["filter_dict"] == extra
    rows = [
        {"dimensions": {**labels, "published": "v1"}},
        {"dimensions": labels, "time_offset": "current"},
        {"dimensions": labels, "time_offset": "1d"},
        {"dimensions": {**labels, "extra": "another"}},
    ]
    assert select_alert_series(rows, labels, True) == rows[1:3]


def test_simple_query_keeps_input_matchers():
    config = {"promql": "rate(metric[1m])", "filter_dict": {"scope": "s"}}
    labels = {"pod": "p"}
    assert prepare_alert_labels([config], {"dimensions": labels, "dimension_fields": ["pod"]}, [], []) == (labels, True)
    assert config["filter_dict"] == {"scope": "s", **labels}


def test_empty_label_matches_absent_label():
    rows = [{"dimensions": {"pod": "p"}}, {"dimensions": {"pod": "p", "version": "other"}}]
    assert select_alert_series(rows, {"pod": "p", "version": ""}, True) == rows[:1]


def test_unlabelled_and_missing_historical_identity():
    config = {"promql": "sum(metric)"}
    rows = [{"dimensions": {}}, {"dimensions": {"pod": "p"}}]
    assert prepare_alert_labels([config], {"dimension_fields": []}, [], []) == ({}, True)
    assert select_alert_series(rows, {}, True) == rows[:1]
    assert prepare_alert_labels([config], {}, [], []) == ({}, False)
    assert select_alert_series(rows[1:], {}, False) == rows[1:]
    with pytest.raises(ValidationError, match="无法唯一匹配"):
        select_alert_series(rows, {}, False)


@pytest.mark.parametrize("from_panel", [False, True])
def test_alert_graph_uses_snapshot_and_filters_before_marking(mocker, from_panel):
    from bkmonitor.documents import AlertDocument
    from fta_web.alert.resources import AlertGraphQueryResource

    expr = 'label_replace(m,"version","$1","release","(.*)")'
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
                {"dimensions": {"version": v}, "datapoints": [[2, 120000]], "metric_field": "_result_"}
                for v in ["v1", "v2"]
            ]
        },
    )
    params = {"id": 42, "bk_biz_id": 2, "start_time": 60, "end_time": 180}
    if from_panel:
        params["query_configs"] = [{**query, "promql": expr.replace("$1", "null"), "filter_dict": {"version": "v2"}}]
    result = AlertGraphQueryResource().perform_request(params)
    sent = graph.call_args.args[0]["query_configs"][0]
    assert sent["promql"] == expr
    assert sent["filter_dict"] == {}
    assert [row["dimensions"] for row in result["series"]] == [{"version": "v2"}]
    assert result["series"][0]["markPoints"] == [[2, 120000]]


def test_non_promql_graph_keeps_filters_and_series(mocker):
    from bkmonitor.documents import AlertDocument
    from fta_web.alert.resources import AlertGraphQueryResource

    config = {"data_source_label": "bk_monitor", "data_type_label": "time_series", "filter_dict": {"pod": "p"}}
    alert = AlertDocument(extra_info={"strategy": {"items": [{"query_configs": [config]}]}}, first_anomaly_time=120)
    mocker.patch.object(AlertDocument, "get", return_value=alert)
    mocker.patch("fta_web.alert.resources.prepare_alert_labels", side_effect=AssertionError)
    graph = mocker.patch("fta_web.alert.resources.resource.grafana.graph_unify_query", return_value={"series": []})
    mocker.patch("fta_web.alert.resources.resource.grafana.graph_trace_query", return_value={"series": []})
    params = {"id": 42, "bk_biz_id": 2, "start_time": 60, "end_time": 180, "query_configs": [config]}
    result = AlertGraphQueryResource().perform_request(params)
    assert graph.call_args.args[0]["query_configs"][0]["filter_dict"] == {"pod": "p"}
    assert result["series"] == []
