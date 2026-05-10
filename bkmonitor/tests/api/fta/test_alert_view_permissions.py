from types import SimpleNamespace

from core.drf_resource import resource
from fta_web.alert.views import AlertViewSet
from fta_web.alert_v2.views import AlertV2ViewSet


def test_graph_drill_down_allows_alert_related_user(mocker):
    alert = SimpleNamespace(
        id="alert-1",
        assignee=["operator"],
        appointee=[],
        supervisor=[],
        follower=[],
    )
    mocker.patch("fta_web.alert.views.AlertDocument.mget", return_value=[alert])

    view = AlertViewSet()
    view.action = "alert/graph_drill_down"
    view.request = SimpleNamespace(
        data={"alert_id": "alert-1"},
        query_params={},
        user=SimpleNamespace(username="operator"),
    )

    assert view.check_alert_permission() is True


def test_alert_v2_registers_graph_drill_down_route():
    route = next(
        (route for route in AlertV2ViewSet.resource_routes if route.endpoint == "alert/graph_drill_down"),
        None,
    )

    assert route is not None
    assert route.method == "POST"
    assert route.resource_class is resource.scene_view.graph_drill_down.__class__
