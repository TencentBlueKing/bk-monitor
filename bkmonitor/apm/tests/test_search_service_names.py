import datetime
from unittest import mock

from django.db.models import Q

from apm.models import TopoNode
from apm.resources import SearchServiceNamesResource


def node(name, biz=2, application="app"):
    return {
        "bk_biz_id": biz,
        "app_name": application,
        "topo_key": name,
    }


def query_data(**kwargs):
    return {
        "bk_biz_ids": [2],
        "query": "demo",
        **kwargs,
    }


def test_search_merges_topology_and_profiling():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value = [
        node("demo"),
        node("http:demo"),
    ]
    profiles = mock.MagicMock()
    profiles.order_by.return_value.values.return_value.distinct.return_value = [
        {"bk_biz_id": 2, "app_name": "app", "name": "demo"},
        {"bk_biz_id": 2, "app_name": "app", "name": "demo_profile"},
    ]
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes) as topo_filter,
        mock.patch("apm.resources.ProfileService.objects.filter", return_value=profiles) as profile_filter,
    ):
        result = SearchServiceNamesResource().perform_request(query_data())
    assert result == [
        {"bk_biz_id": 2, "app_name": "app", "service_name": "demo"},
        {"bk_biz_id": 2, "app_name": "app", "service_name": "http:demo"},
        {"bk_biz_id": 2, "app_name": "app", "service_name": "demo_profile"},
    ]
    filters = topo_filter.call_args.kwargs
    assert filters["bk_biz_id__in"] == [2]
    assert filters["topo_key__icontains"] == "demo"
    assert "app_name__in" not in filters
    assert abs((datetime.datetime.now() - filters["updated_at__gte"]).days - TopoNode.EXPIRED_DAYS) <= 1
    profile_filter.assert_called_once()
    assert profile_filter.call_args.kwargs == {"bk_biz_id__in": [2], "name__icontains": "demo"}


def test_empty_biz_ids_do_not_filter_business_scope():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value = []
    profiles = mock.MagicMock()
    profiles.order_by.return_value.values.return_value.distinct.return_value = []
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes) as topo_filter,
        mock.patch("apm.resources.ProfileService.objects.filter", return_value=profiles) as profile_filter,
    ):
        assert SearchServiceNamesResource().perform_request(query_data(bk_biz_ids=[])) == []
    assert "bk_biz_id__in" not in topo_filter.call_args.kwargs
    assert "bk_biz_id__in" not in profile_filter.call_args.kwargs
    assert topo_filter.call_args.kwargs["topo_key__icontains"] == "demo"
    assert profile_filter.call_args.kwargs["name__icontains"] == "demo"


def test_search_scope_validation():
    serializer = SearchServiceNamesResource.RequestSerializer(data=query_data())
    assert serializer.is_valid()
    assert serializer.validated_data["limit"] == 20
    assert SearchServiceNamesResource.RequestSerializer(data=query_data(bk_biz_ids=[])).is_valid()
    assert SearchServiceNamesResource.RequestSerializer(data=query_data(app_names=["app"])).is_valid()
    assert SearchServiceNamesResource.RequestSerializer(data=query_data(app_names=[])).is_valid()
    assert SearchServiceNamesResource.RequestSerializer(data=query_data(limit=1)).is_valid()
    assert SearchServiceNamesResource.RequestSerializer(data=query_data(limit=100)).is_valid()
    assert not SearchServiceNamesResource.RequestSerializer(data={"query": "demo"}).is_valid()
    assert not SearchServiceNamesResource.RequestSerializer(data=query_data(query="")).is_valid()
    assert not SearchServiceNamesResource.RequestSerializer(data=query_data(limit=0)).is_valid()
    assert not SearchServiceNamesResource.RequestSerializer(data=query_data(limit=101)).is_valid()
    assert not SearchServiceNamesResource.RequestSerializer(
        data=query_data(app_names=[str(i) for i in range(101)])
    ).is_valid()


def test_limit_stops_after_enough_topology_hits():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value = [node(f"demo_{i}") for i in range(5)]
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes),
        mock.patch("apm.resources.ProfileService.objects.filter") as profile_filter,
    ):
        result = SearchServiceNamesResource().perform_request(query_data(limit=3))
    assert [item["service_name"] for item in result] == ["demo_0", "demo_1", "demo_2"]
    profile_filter.assert_not_called()


def test_limit_fills_remaining_from_profiling():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value = [node("demo")]
    profiles = mock.MagicMock()
    profiles.order_by.return_value.values.return_value.distinct.return_value = [
        {"bk_biz_id": 2, "app_name": "app", "name": "demo"},
        {"bk_biz_id": 2, "app_name": "app", "name": "demo_p1"},
        {"bk_biz_id": 2, "app_name": "app", "name": "demo_p2"},
    ]
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes),
        mock.patch("apm.resources.ProfileService.objects.filter", return_value=profiles),
    ):
        result = SearchServiceNamesResource().perform_request(query_data(limit=2))
    assert [item["service_name"] for item in result] == ["demo", "demo_p1"]


def test_app_names_narrow_topology_and_profiling_scope():
    nodes = mock.MagicMock()
    nodes.order_by.return_value.values.return_value = []
    profiles = mock.MagicMock()
    profiles.order_by.return_value.values.return_value.distinct.return_value = []
    with (
        mock.patch("apm.resources.TopoNode.objects.filter", return_value=nodes) as topo_filter,
        mock.patch("apm.resources.ProfileService.objects.filter", return_value=profiles) as profile_filter,
    ):
        SearchServiceNamesResource().perform_request(query_data(app_names=["app", "other"]))
    assert topo_filter.call_args.kwargs["app_name__in"] == ["app", "other"]
    assert profile_filter.call_args.kwargs["app_name__in"] == ["app", "other"]
    assert topo_filter.call_args.kwargs["bk_biz_id__in"] == [2]


def test_underscore_is_literal_in_name_query():
    # 使用真实 ORM 编译，确认下划线不会成为 SQL LIKE 的任意字符；不执行数据库查询。
    query = TopoNode.objects.filter(Q(bk_biz_id__in=[2]), topo_key__icontains="demo_v4").query
    _, params = query.sql_with_params()
    assert "%demo\\_v4%" in params
