"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from unittest.mock import patch

import pytest

from apm_web.handlers.metric_group.groups.trpc import TrpcMetricGroup
from apm_web.handlers.metric_group.helper import MetricHelper, PreCalculateHelper
from apm_web.metric.resources import DynamicUnifyQueryResource
from apm_web.models import Application
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource

START = 1_700_000_000
END = START + 300
RAW = "raw.__default__"
PRECAL = "precal.__default__"


def metric_mapping(metric, filtered):
    mapping = {"drop_labels": ["instance"], "metric": f"sum_without_ip_{metric}"}
    if filtered:
        mapping.update(metric="metric_value", filter_dict={"metric_name__eq": [mapping["metric"]]})
    return mapping


@pytest.mark.parametrize("kind", ["caller", "callee"])
@pytest.mark.parametrize(
    "filtered,group_by", [(True, ["service_name"]), (False, ["service_name"]), (True, ["instance"])]
)
def test_avg_duration_routes_each_operand(kind, filtered, group_by):
    fields = TrpcMetricGroup.METRIC_FIELDS[kind]
    metrics = [fields["rpc_handled_seconds_sum"], fields["rpc_handled_seconds_count"]]
    route = {"table_id": PRECAL, "metrics": {metric: [metric_mapping(metric, filtered)] for metric in metrics}}
    with patch.object(Application, "get_metric_table_id", return_value=RAW):
        group = TrpcMetricGroup(
            2,
            "demo",
            group_by=group_by,
            kind=kind,
            metric_helper=MetricHelper(2, "demo"),
            filter_dict={"service_name__eq": ["api"]},
            pre_calculate_helper=PreCalculateHelper(route),
        )
    config = group._export_qs(group._get_qs("avg_duration", START, END), raw=True)

    assert len(config["query_configs"]) == 2
    for query, metric in zip(config["query_configs"], metrics):
        routed = "instance" not in group_by
        expected = metric_mapping(metric, filtered)
        assert query["table"] == (PRECAL if routed else RAW)
        assert query["metrics"][0]["field"] == (expected["metric"] if routed else metric)
        conditions = {cond["key"]: cond["value"] for cond in query["where"]}
        assert conditions.pop("service_name") == ["api"]
        assert conditions == ({"metric_name": [f"sum_without_ip_{metric}"]} if filtered and routed else {})
        functions = {func["id"] for func in query["functions"]}
        assert ("increase" in functions) == (not routed)
        assert ("time_shift" in functions) == routed


@pytest.mark.parametrize("with_metric", [True, False])
def test_graph_route_filters_each_or_branch_and_recovers_logical_metrics(with_metric):
    metrics = ["rpc_client_handled_seconds_sum", "rpc_client_handled_seconds_count"]
    route = {"table_id": PRECAL, "metrics": {metric: [metric_mapping(metric, True)] for metric in metrics}}
    where = [
        {"key": "service_name", "method": "eq", "value": ["api"]},
        {"key": "service_name", "method": "eq", "value": ["worker"], "condition": "or"},
    ]
    params = {
        "start_time": START,
        "end_time": END,
        "bk_biz_id": 2,
        "with_metric": with_metric,
        "expression": "a / b",
        "query_configs": [
            {"data_source_label": "custom", "table": RAW, "metrics": [{"field": metric}], "where": where}
            for metric in metrics
        ],
    }
    original = copy.deepcopy(params)
    state = {"bk_biz_id": 2, "app_name": "demo"}
    with patch.object(DynamicUnifyQueryResource, "get_helper_or_none", return_value=PreCalculateHelper(route)):
        DynamicUnifyQueryResource._process_rpc_pre_calculate(params, None, state)

    for query, metric in zip(params["query_configs"], metrics):
        assert query["table"] == PRECAL
        assert query["metrics"][0]["field"] == "metric_value"
        selector = {"key": "metric_name", "method": "eq", "value": [f"sum_without_ip_{metric}"]}
        assert query["where"] == [
            selector,
            {**where[0], "condition": "and"},
            {**selector, "condition": "or"},
            {**where[1], "condition": "and"},
        ]

    response = {}
    with patch.object(GraphUnifyQueryResource, "get_metric_info", return_value=metrics) as get_metrics:
        DynamicUnifyQueryResource._recovery_query_metadata(params, response, state)
    if with_metric:
        get_metrics.assert_called_once()
        configs = get_metrics.call_args.args[0]["query_configs"]
        assert [(q["table"], q["metrics"][0]["field"]) for q in configs] == [(RAW, metric) for metric in metrics]
    else:
        get_metrics.assert_not_called()
    assert response == {"query_config": original, "metrics": metrics if with_metric else []}


def test_graph_extra_filter_on_dropped_dimension_falls_back_for_that_operand():
    metric = "rpc_server_handled_total"
    route = {"table_id": PRECAL, "metrics": {metric: [metric_mapping(metric, True)]}}
    base = {"table": RAW, "metrics": [{"field": metric}], "functions": [{"id": "increase"}]}
    params = {
        "start_time": START,
        "end_time": END,
        "query_configs": [{**copy.deepcopy(base), "filter_dict": {"instance__eq": ["node"]}}, copy.deepcopy(base)],
    }
    with patch.object(DynamicUnifyQueryResource, "get_helper_or_none", return_value=PreCalculateHelper(route)):
        DynamicUnifyQueryResource._process_rpc_pre_calculate(params, None, {"app_name": "demo", "bk_biz_id": 2})
    raw, filtered = params["query_configs"]
    assert raw == {**base, "filter_dict": {"instance__eq": ["node"]}}
    assert filtered["where"][0]["value"] == [f"sum_without_ip_{metric}"]
    assert filtered["table"] == PRECAL
