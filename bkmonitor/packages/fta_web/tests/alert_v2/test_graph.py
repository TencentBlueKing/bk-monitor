import pytest
from django.urls import resolve

from fta_web.alert.resources import AIOPSManager
from constants.apm import ApmAlertHelper
from bkmonitor.documents import AlertDocument
from fta_web.alert_v2.resources import AlertGraphDrillDownResource, AlertGraphQueryResource
from monitor_web.scene_view.resources.custom_metric import GraphDrillDownResource


TABLE = "2_bkapm_metric_demo.__default__"
STRATEGY = {"labels": ["APM-APP(demo)"]}
SUCCESS_RATE = "(a or b * 0) / (b >= 100) * 100"
DISPLAY_RATE = "(a or b * 0) / (b > 0) * 100"


@pytest.mark.parametrize(
    ("endpoint", "resource_class"),
    [("graph_query", AlertGraphQueryResource), ("graph_drill_down", AlertGraphDrillDownResource)],
)
def test_v2_graph_routes(endpoint, resource_class):
    view = resolve(f"/fta/alert/v2/alert/{endpoint}/").func.cls
    route = next(route for route in view.resource_routes if route.endpoint == f"alert/{endpoint}")
    assert route.resource_class is resource_class


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (SUCCESS_RATE, DISPLAY_RATE),
        ("(a or b < bool 0) / (b > 10) * 100", "(a or b < bool 0) / (b > 0) * 100"),
        ("b == 0 or (a / (b > 10)) * 1000", "b == 0 or (a / (b > 0)) * 1000"),
        ("(b > bool 10) * a * 1000", "(b > bool 0) * a * 1000"),
        ("(b > bool 10) * a", "(b > bool 0) * a"),
        ("(a>bool 10)*a", "(a>bool 0)*a"),
        ("(a / (b > 0) - 1) * 100 and (a >= 60000)", "(a / (b > 0) - 1) * 100 and (a >= 0)"),
        ("(a/(b>0)-1)*100 and (a>50)", "(a/(b>0)-1)*100 and (a>0)"),
        ("(a / (b > 0) - 1) * 100 and (b >= 60000)", "(a / (b > 0) - 1) * 100 and (b >= 60000)"),
        ("(b > bool 10) * a + 5", "(b > bool 10) * a + 5"),
        (DISPLAY_RATE, DISPLAY_RATE),
    ],
)
def test_prepare_apm_graph_query(expression, expected):
    params = {"expression": expression, "query_configs": [{"data_label": "APM"}]}
    assert ApmAlertHelper.prepare_graph_query(params, STRATEGY)["expression"] == expected
    assert params["expression"] == expression


@pytest.mark.parametrize("strategy", [None, {}, {"labels": ["host"]}])
def test_other_queries(strategy):
    params = {"expression": SUCCESS_RATE, "query_configs": [{"table": TABLE}]}
    assert ApmAlertHelper.prepare_graph_query(params, strategy) == params


def test_graph_query_panel_fallback(mocker):
    panel_data = {"expression": SUCCESS_RATE, "query_configs": [{"table": TABLE}]}
    mocker.patch.object(AIOPSManager, "get_graph_panel", return_value={"targets": [{"data": panel_data}]})
    result = AlertGraphQueryResource().get_graph_query_params({"query_configs": []}, mocker.Mock(strategy=STRATEGY))
    assert result["expression"] == DISPLAY_RATE
    assert panel_data["expression"] == SUCCESS_RATE


def test_drill_down_forwards_display_expression(mocker):
    query = mocker.patch.object(GraphDrillDownResource, "perform_request")
    mocker.patch.object(AlertDocument, "get", return_value=mocker.Mock(strategy=STRATEGY))
    params = {"alert_id": 123, "expression": SUCCESS_RATE, "query_configs": [{"table": TABLE}], "group_by": ["code"]}
    AlertGraphDrillDownResource().perform_request(params)
    query.assert_called_once_with({**params, "expression": DISPLAY_RATE})
