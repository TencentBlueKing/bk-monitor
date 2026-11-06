from types import SimpleNamespace

import pytest

from bkmonitor.models import ApiAuthToken
from bkmonitor.share.handler import HostApiAuthChecker
from core.errors.share import InvalidParamsError, ParamsPermissionDeniedError, SearchLockedError


def make_view(route, action="create"):
    view = type(route, (), {})
    view.__module__ = "monitor_web.performance.views"
    return SimpleNamespace(cls=view, actions={"post": action})


def make_checker(mocker, route, scope=None, lock=False):
    request = SimpleNamespace(method="POST", resolver_match=SimpleNamespace(func=make_view(route)))
    mocker.patch("bkmonitor.share.handler.get_request", return_value=request)
    mocker.patch(
        "bkmonitor.share.handler.api.cmdb.get_host_page",
        return_value={"items": [SimpleNamespace(bk_host_id=7)], "total": 10000},
    )
    token = SimpleNamespace(
        bk_tenant_id="system",
        namespaces=["biz#2"],
        params={
            "lock_search": lock,
            "start_time": 100,
            "end_time": 200,
            "default_time_range": [],
            "data": {"scope": scope or {"version": 1, "target_type": "topo", "bk_obj_id": "set", "bk_inst_id": 8}},
        },
    )
    return HostApiAuthChecker(token)


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_host_list_share_scope_existence_does_not_load_full_hosts(mocker, route):
    get_all = mocker.patch("bkmonitor.share.handler.api.cmdb.get_host_by_topo_node")
    checker = make_checker(mocker, route)
    checker.check({"bk_obj_id": "set", "bk_inst_id": 8, "page": 1, "page_size": 50})
    get_all.assert_not_called()


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_host_list_share_accepts_only_descendant_topology(mocker, route):
    checker = make_checker(mocker, route)
    links = {
        "module|9": [
            SimpleNamespace(bk_obj_id="module", bk_inst_id=9),
            SimpleNamespace(bk_obj_id="set", bk_inst_id=8),
            SimpleNamespace(bk_obj_id="biz", bk_inst_id=2),
        ],
        "module|11": [
            SimpleNamespace(bk_obj_id="module", bk_inst_id=11),
            SimpleNamespace(bk_obj_id="set", bk_inst_id=10),
            SimpleNamespace(bk_obj_id="biz", bk_inst_id=2),
        ],
    }
    mocker.patch(
        "bkmonitor.share.handler.api.cmdb.get_topo_tree",
        return_value=SimpleNamespace(convert_to_topo_link=lambda: links),
    )
    checker.check({"bk_obj_id": "module", "bk_inst_id": 9, "page": 1})
    for target in [{"bk_obj_id": "module", "bk_inst_id": 11}, {"bk_obj_id": "biz", "bk_inst_id": 2}, {}]:
        with pytest.raises((InvalidParamsError, ParamsPermissionDeniedError)):
            checker.check({"page": 1, **target})


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_host_list_share_intersects_single_host_with_authorized_topology(mocker, route):
    checker = make_checker(mocker, route)
    get_page = mocker.patch(
        "bkmonitor.share.handler.api.cmdb.get_host_page",
        return_value={"items": [SimpleNamespace(bk_host_id=7)], "total": 1},
    )
    checker.check({"bk_host_id": 7, "page": 1})
    get_page.assert_called_once_with(bk_biz_id=2, bk_host_id=7, topo_nodes={"set": [8]}, page=1, page_size=1)
    get_page.return_value = {"items": [], "total": 0}
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check({"bk_host_id": 999, "page": 1})


def test_host_stats_share_keeps_absolute_time_lock(mocker):
    checker = make_checker(mocker, "SearchHostMetricStatsViewSet", lock=True)
    scope = {"bk_obj_id": "set", "bk_inst_id": 8, "category": "cpu"}
    checker.check({**scope, "start_time": 100, "end_time": 200})
    with pytest.raises(InvalidParamsError):
        checker.check(scope)
    with pytest.raises(SearchLockedError):
        checker.check({**scope, "start_time": 101, "end_time": 200})


def test_full_info_share_does_not_allow_broader_or_changed_scope(mocker):
    checker = make_checker(mocker, "SearchHostInfoViewSet")
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check({"bk_obj_id": "module", "bk_inst_id": 9})


def test_single_host_share_cannot_select_another_host(mocker):
    checker = make_checker(
        mocker, "SearchHostMetricStatsViewSet", {"version": 1, "target_type": "host", "bk_host_id": 7}
    )
    checker.check({"bk_host_id": 7})
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check({"bk_host_id": 8})


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_unrelated_query_configs_cannot_bypass_actual_host_list_target(mocker, route):
    checker = make_checker(mocker, route, {"version": 1, "target_type": "host", "bk_host_id": 7})
    query_check = mocker.patch.object(checker, "query_configs_check")
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check(
            {"bk_host_id": 8, "page": 1, "query_configs": [{"filter_dict": {"targets": [{"bk_host_id": 7}]}}]}
        )
    query_check.assert_not_called()


@pytest.mark.parametrize("action,allowed", [("create", True), ("destroy", False)])
def test_scoped_host_share_token_stats_route_allowlist(action, allowed):
    token = ApiAuthToken(type="host")
    assert token.is_allowed_view(make_view("SearchHostMetricStatsViewSet", action)) is allowed


def test_host_stats_route_enforces_share_target_and_absolute_time(mocker):
    checker = make_checker(
        mocker, "SearchHostMetricStatsViewSet", {"version": 1, "target_type": "host", "bk_host_id": 100}, lock=True
    )
    checker.check({"bk_host_id": 100, "category": "cpu", "start_time": 100, "end_time": 200})
    with pytest.raises(InvalidParamsError):
        checker.check({"bk_host_id": 100, "category": "cpu"})
    with pytest.raises(SearchLockedError):
        checker.check({"bk_host_id": 100, "category": "cpu", "start_time": 101, "end_time": 200})
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check({"bk_host_id": 101, "category": "cpu", "start_time": 100, "end_time": 200})


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_scoped_info_and_stats_permission_only_load_one_host(mocker, route):
    get_all = mocker.patch("bkmonitor.share.handler.api.cmdb.get_host_by_topo_node")
    checker = make_checker(mocker, route, {"version": 1, "target_type": "topo", "bk_obj_id": "module", "bk_inst_id": 8})
    checker.check({"bk_obj_id": "module", "bk_inst_id": 8})
    from bkmonitor.share import handler

    handler.api.cmdb.get_host_page.assert_called_once_with(bk_biz_id=2, page=1, page_size=1, topo_nodes={"module": [8]})
    get_all.assert_not_called()
    mocker.patch(
        "bkmonitor.share.handler.api.cmdb.get_topo_tree", return_value=SimpleNamespace(convert_to_topo_link=lambda: {})
    )
    with pytest.raises(ParamsPermissionDeniedError):
        checker.check({"bk_obj_id": "module", "bk_inst_id": 9})
