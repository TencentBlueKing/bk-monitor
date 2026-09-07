import datetime
from unittest import mock

import pytest
from django.db.models import Q

from apm.models import ApmTopoDiscoverRule, TopoNode
from apm.resources import SearchServiceNamesResource


def node(name, kind="service", category="http"):
    return {"id": 1, "app_name": "app", "topo_key": name, "extra_data": {"kind": kind, "category": category}}


def query_data(**kwargs):
    return {
        "bk_biz_id": 2,
        "app_names": ["app"],
        "query": "demo",
        "limit": 20,
        **kwargs,
    }


def test_search_service_names_preserves_node_filter_and_deduplicates_profiling():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value.filter.return_value.__getitem__.side_effect = [
        [
            node("demo"),
            node("http:demo", ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE),
            node("mysql:demo", ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE, "mysql"),
        ],
        [],
    ]
    profiles = mock.MagicMock()
    profiles.order_by.return_value.values.return_value.distinct.return_value.__getitem__.return_value = [
        {"app_name": "app", "name": "demo"},
        {"app_name": "app", "name": "demo_profile"},
    ]
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes) as topo_filter,
        mock.patch("apm.resources.ApmApplication.objects.filter") as app_filter,
        mock.patch("apm.resources.ProfileService.objects.filter", return_value=profiles) as profile_filter,
    ):
        result = SearchServiceNamesResource().perform_request(query_data())
    assert [row["service_name"] for row in result] == ["demo", "http:demo", "demo_profile"]
    filters = topo_filter.call_args.kwargs
    assert filters["bk_biz_id"] == 2
    assert filters["app_name__in"] == ["app"]
    assert filters["topo_key__icontains"] == "demo"
    assert abs((datetime.datetime.now() - filters["updated_at__gte"]).days - TopoNode.EXPIRED_DAYS) <= 1
    app_filter.assert_not_called()
    profile_filter.assert_called_once_with(bk_biz_id=2, app_name__in=["app"], name__icontains="demo")


def test_no_profile_query_when_topology_fills_limit():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value.filter.return_value.__getitem__.side_effect = [[node("demo")], []]
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes),
        mock.patch("apm.resources.ApmApplication.objects.filter") as app_filter,
        mock.patch("apm.resources.ProfileService.objects.filter") as profiles,
    ):
        assert SearchServiceNamesResource().perform_request(query_data(limit=1)) == [
            {"app_name": "app", "service_name": "demo"}
        ]
    profiles.assert_not_called()
    app_filter.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        {"app_names": []},
        {"app_names": [str(i) for i in range(101)]},
        {"limit": 0},
        {"limit": 101},
        {"query": ""},
    ],
)
def test_search_scope_validation(overrides):
    serializer = SearchServiceNamesResource.RequestSerializer(data=query_data(**overrides))
    assert not serializer.is_valid()


def test_underscore_is_literal_in_name_query():
    # 使用真实 ORM 编译，确认下划线不会成为 SQL LIKE 的任意字符；不执行数据库查询。
    query = TopoNode.objects.filter(Q(bk_biz_id=2, app_name__in=["app"]), topo_key__icontains="demo_v4").query
    _, params = query.sql_with_params()
    assert "%demo\\_v4%" in params


def test_topology_cursor_advances_past_filtered_nodes_with_bounded_reads():
    filtered = [{**node(f"demo_{i}", ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE, "mysql"), "id": i} for i in range(1, 101)]
    nodes = mock.MagicMock()
    scoped = nodes.order_by.return_value.values.return_value
    scoped.filter.return_value.__getitem__.side_effect = [filtered, [{**node("demo_valid"), "id": 101}]]
    with mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes):
        result = SearchServiceNamesResource().perform_request(query_data(limit=1))
    assert result == [{"app_name": "app", "service_name": "demo_valid"}]
    assert scoped.filter.call_args_list == [mock.call(id__gt=0), mock.call(id__gt=100)]
    assert scoped.filter.return_value.__getitem__.call_args_list == [mock.call(slice(None, 100))] * 2
