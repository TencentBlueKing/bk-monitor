from copy import deepcopy

import pytest

from bkmonitor.utils.range import load_agg_condition_instance
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource, UnifyQueryRawResource


def preview_params(**overrides):
    payload = {
        "bk_biz_id": 2,
        "target": [
            {"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": 1},
            {"bk_target_ip": "192.0.2.20", "bk_target_cloud_id": 2},
        ],
        "target_filter_type": "post-query",
        "query_configs": [
            {
                "data_source_label": "custom",
                "data_type_label": "event",
                "table": "test_event",
                "metrics": [{"field": "_index", "method": "COUNT", "alias": "a"}],
                "group_by": ["bk_target_ip", "bk_target_cloud_id"],
                "interval": 60,
            }
        ],
        "expression": "a",
        "start_time": 100,
        "end_time": 200,
        **overrides,
    }
    serializer = UnifyQueryRawResource.RequestSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@pytest.fixture
def preview_backend(mocker):
    points = [
        {"id": "first", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": 1, "status": "active"},
        {"id": "second", "bk_target_ip": "192.0.2.20", "bk_target_cloud_id": "2", "status": "inactive"},
        {"id": "cross-cloud", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": 2, "status": "active"},
        {"id": "outside", "bk_target_ip": "192.0.2.30", "bk_target_cloud_id": 3, "status": "active"},
        {"id": "missing-cloud", "bk_target_ip": "192.0.2.10", "status": "active"},
        {"id": "missing-ip", "bk_target_cloud_id": 1, "status": "active"},
        {"id": "missing-both", "status": "active"},
    ]
    points[:] = [{"_time_": 150_000, "_result_": 1, **point} for point in points]
    mocker.patch("monitor_web.grafana.resources.unify_query.get_cookies_filter", return_value={})
    mocker.patch.object(UnifyQueryRawResource, "get_metric_info", return_value=[])
    mocker.patch.object(UnifyQueryRawResource, "get_dimension_combination")
    mocker.patch("monitor_web.grafana.resources.unify_query.unify_query_count")
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch(
        "monitor_web.grafana.resources.unify_query.load_data_source",
        return_value=lambda **kwargs: mocker.Mock(group_by=kwargs["group_by"]),
    )
    query = mocker.patch("monitor_web.grafana.resources.unify_query.UnifyQuery").return_value
    query.query_data_with_stat.side_effect = lambda **kwargs: {"series": deepcopy(points), "series_stat": {}}
    query.query_reference.side_effect = lambda **kwargs: deepcopy(points)
    return points, query


def test_post_filter_preserves_ip_cloud_pairs_and_rejects_missing_identity(preview_backend):
    result = UnifyQueryRawResource().perform_request(preview_params())

    assert [point["id"] for point in result["series"]] == ["first", "second"]


@pytest.mark.parametrize("resource_class", [UnifyQueryRawResource, GraphUnifyQueryResource])
@pytest.mark.parametrize("query_method", [None, "query_reference"])
def test_post_filter_is_shared_by_raw_graph_and_reference_queries(preview_backend, resource_class, query_method):
    result = resource_class()._perform_query(preview_params(), query_method_name=query_method)

    assert [point["id"] for point in result["series"]] == ["first", "second"]


@pytest.mark.parametrize("group_count,post_filter", [(99, False), (100, True)])
def test_auto_threshold_counts_parsed_groups(preview_backend, group_count, post_filter):
    params = preview_params(
        target=[{"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": cloud} for cloud in range(group_count)],
        target_filter_type="auto",
    )

    result = UnifyQueryRawResource().perform_request(params)

    assert bool(params["post_query_filter_dict"]) is post_filter
    if post_filter:
        assert [point["id"] for point in result["series"]] == ["first", "cross-cloud"]
        assert "target" not in params["query_configs"][0]["filter_dict"]
    else:
        assert len(params["query_configs"][0]["filter_dict"]["target"]) == group_count


def test_query_mode_keeps_large_target_in_query(preview_backend):
    params = preview_params(
        target=[{"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": cloud} for cloud in range(100)],
        target_filter_type="query",
    )

    UnifyQueryRawResource().perform_request(params)

    assert len(params["query_configs"][0]["filter_dict"]["target"]) == 100
    assert params["post_query_filter_dict"] == {}


@pytest.mark.parametrize("dimension", ["bk_host_id", "service_instance_id", "bk_target_service_instance_id"])
def test_post_filter_supports_host_and_service_identities(preview_backend, dimension):
    points, _ = preview_backend
    points[:] = [{dimension: 101}, {dimension: "102"}, {"other": 101}]
    params = preview_params(target=[{dimension: 101}])
    params["query_configs"][0]["group_by"] = [dimension]

    result = UnifyQueryRawResource().perform_request(params)

    assert result["series"] == [{dimension: 101}]


def test_post_filter_combines_target_or_groups_with_other_conditions(preview_backend):
    params = preview_params(post_query_filter_dict={"status": "active"})

    result = UnifyQueryRawResource().perform_request(params)

    assert [point["id"] for point in result["series"]] == ["first"]


def test_explicit_post_filter_works_without_target(preview_backend):
    points, _ = preview_backend
    points.append({"id": "missing-status"})
    params = preview_params(target=[], post_query_filter_dict={"status__neq": "active"})

    result = UnifyQueryRawResource().perform_request(params)

    assert [point["id"] for point in result["series"]] == ["second"]


def test_post_filter_also_filters_time_comparison_points(preview_backend):
    _, query = preview_backend
    result = UnifyQueryRawResource().perform_request(preview_params(function={"time_compare": "1h"}))

    assert query.query_data_with_stat.call_count == 2
    assert [(point["id"], point.get("__time_compare")) for point in result["series"]] == [
        ("first", None),
        ("second", None),
        ("first", "1h"),
        ("second", "1h"),
    ]


@pytest.mark.parametrize("target", [[], [[]]])
def test_unconfigured_target_preserves_results(preview_backend, target):
    points, _ = preview_backend

    result = UnifyQueryRawResource().perform_request(preview_params(target=target))

    assert result["series"] == points


def test_empty_resolved_target_stops_before_query(preview_backend, mocker):
    _, query = preview_backend
    mocker.patch("core.drf_resource.resource.cc.parse_topo_target", return_value=None)

    result = UnifyQueryRawResource().perform_request(preview_params())

    assert result["series"] == []
    query.query_data_with_stat.assert_not_called()


def test_condition_loader_keeps_existing_missing_field_default():
    condition = [{"key": "bk_host_id", "method": "eq", "value": [101]}]

    assert load_agg_condition_instance(condition).is_match({})
    assert not load_agg_condition_instance(condition, default_value_if_not_exists=False).is_match({})
