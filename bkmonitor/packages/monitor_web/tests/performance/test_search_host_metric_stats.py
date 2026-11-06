import math
import re
from types import SimpleNamespace

import pytest

from core.errors.share import InvalidParamsError
from monitor_web.performance import host_metric_stats as stats
from monitor_web.performance.resources import SearchHostMetricStatsResource


HOSTS = [
    {"bk_host_id": 1, "bk_host_innerip": "host-a", "bk_cloud_id": 0},
    {"bk_host_id": 2, "bk_host_innerip": "host-a", "bk_cloud_id": 1},
    {"bk_host_id": 3, "bk_host_innerip": "", "bk_host_innerip_v6": "host-v6", "bk_cloud_id": 1},
]


@pytest.mark.parametrize(
    "category,table,field",
    [("cpu", "system.cpu_summary", "usage"), ("mem", "system.mem", "pct_used"), ("disk", "system.disk", "in_use")],
)
def test_stats_query_preserves_metrics_and_exact_cmdb_identity_whitelist(mocker, category, table, field):
    captured = []

    def source(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(**kwargs)

    mocker.patch.object(stats, "load_data_source", return_value=source)
    uq = mocker.patch.object(stats, "UnifyQuery")
    stats.build_host_stats_query(2, category, HOSTS)
    assert len(captured) == 2
    assert all(item["table"] == table and item["metrics"][0]["field"] == field for item in captured)
    assert all(item["interval"] == 180 and item["metrics"][0]["method"] == "MAX" for item in captured)
    assert captured[0]["filter_dict"] == {"bk_host_id": ["1", "2", "3"]}
    assert captured[1]["where"] == [{"key": "bk_host_id", "method": "eq", "value": [""]}]
    assert captured[1]["filter_dict"]["targets"] == [
        {"bk_target_ip": ["host-a"], "bk_target_cloud_id": ["0", ""]},
        {"bk_target_ip": ["", "host-a"], "bk_target_cloud_id": ["1"]},
    ]
    expression = uq.call_args.kwargs["expression"]
    assert "79.995" in expression
    assert "count by (bk_host_id)" in expression
    assert "count by (bk_target_ip, bk_target_cloud_id)" in expression
    assert "==" not in expression
    # 阈值直接排除 NaN；身份计数及重复身份检查仍读取未过滤的 a/b。
    assert "count(a) or vector(0)" in expression
    assert "count(b) or vector(0)" in expression
    assert len(re.findall(r"\ba\b", expression)) == 3
    assert len(re.findall(r"\bb\b", expression)) == 3


@pytest.mark.parametrize(
    "value",
    [0, 79, math.nextafter(79.995, 0), 79.995, math.nextafter(79.995, 100), 80, 100, float("inf"), float("nan")],
)
def test_stats_threshold_matches_python_two_decimal_rounding(value):
    assert (value >= 79.995) == (round(value, 2) >= 80)


def make_query(mocker, values=None, partial=False):
    if values is None:
        values = {"value": 2, "id_count": 3, "ip_count": 0, "duplicates": 0}
    query = mocker.Mock()
    query.is_partial = partial
    query.query_data.return_value = [{"stat": key, "_result_": value} for key, value in values.items()]
    mocker.patch.object(stats, "build_host_stats_query", return_value=query)
    return query


def test_stats_one_instant_query_uses_list_time_anchor_and_device_processing(mocker):
    query = make_query(mocker)
    result = stats.query_host_metric_stats(2, "disk", HOSTS, start_time=100, end_time=400)
    assert result == {"category": "disk", "value": 2, "complete": True}
    query.query_data.assert_called_once_with(start_time=220000, end_time=400000, instant=True)


@pytest.mark.parametrize(
    "values,partial,reason",
    [
        ({"value": 0, "id_count": 0, "ip_count": 0, "duplicates": 0}, True, "partial"),
        ({"value": 2, "id_count": 2, "ip_count": 1, "duplicates": 0}, False, "ambiguous_identity"),
        ({"value": 2, "id_count": 2, "ip_count": 0, "duplicates": 1}, False, "ambiguous_identity"),
        ({"value": 2, "id_count": 0, "ip_count": 2, "duplicates": 1}, False, "ambiguous_identity"),
        ({}, False, "invalid_result"),
    ],
)
def test_stats_incomplete_is_unknown_instead_of_zero(mocker, values, partial, reason):
    make_query(mocker, values, partial)
    assert stats.query_host_metric_stats(2, "cpu", HOSTS) == {
        "category": "cpu",
        "value": None,
        "complete": False,
        "reason": reason,
    }


def test_stats_successful_empty_query_is_zero(mocker):
    make_query(mocker, {"value": 0, "id_count": 0, "ip_count": 0, "duplicates": 0})
    assert stats.query_host_metric_stats(2, "cpu", HOSTS)["value"] == 0


def test_stats_empty_cmdb_scope_does_not_query_business_metrics(mocker):
    build_query = mocker.patch.object(stats, "build_host_stats_query")
    assert stats.query_host_metric_stats(2, "mem", []) == {"category": "mem", "value": 0, "complete": True}
    build_query.assert_not_called()


def test_stats_query_error_propagates_without_retry_or_data_source_fallback(mocker):
    query = make_query(mocker)
    query.query_data.side_effect = RuntimeError("query failed")
    with pytest.raises(RuntimeError, match="query failed"):
        stats.query_host_metric_stats(2, "cpu", HOSTS)
    assert query.query_data.call_count == 1


def test_stats_instant_request_satisfies_real_unify_query_serializer(mocker):
    from api.unify_query.default import QueryDataResource
    from bkmonitor.data_source import UnifyQuery

    query = make_query(mocker)
    records = query.query_data.return_value
    query.query_output_config = None
    query.get_unify_query_params.return_value = {
        "query_list": [{"reference_name": "a"}],
        "metric_merge": "count(a)",
        "start_time": "180",
        "end_time": "360",
        "step": "180s",
        "space_uid": "bkcc__2",
    }
    query.process_unify_query_data.return_value = records
    query.process_unify_query_series_stat.return_value = {}
    query.process_data_by_datasource.side_effect = lambda rows: rows

    def validate_request(**params):
        serializer = QueryDataResource.RequestSerializer(data=params)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["down_sample_range"] == ""
        assert serializer.validated_data["instant"] is True
        assert serializer.validated_data["step"] == "1m"
        return {"series": [], "is_partial": False}

    api_query = mocker.patch(
        "bkmonitor.data_source.unify_query.query.api.unify_query.query_data", side_effect=validate_request
    )
    query.query_data.side_effect = lambda **kwargs: UnifyQuery._query_unify_query(query, **kwargs)[0]
    assert stats.query_host_metric_stats(2, "cpu", HOSTS, 100, 400)["value"] == 2
    assert api_query.call_count == 1


@pytest.mark.parametrize(
    "scope,expected",
    [
        ({"bk_host_id": 1}, {"bk_host_id": 1}),
        ({"bk_obj_id": "module", "bk_inst_id": 8}, {"topo_nodes": {"module": [8]}}),
    ],
)
def test_stats_resource_preserves_scope_and_time(mocker, scope, expected):
    identities = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_identities", return_value=HOSTS)
    query = mocker.patch("monitor_web.performance.resources.query_host_metric_stats", return_value={"value": 2})
    assert SearchHostMetricStatsResource().perform_request(
        {"bk_biz_id": 2, "category": "cpu", "start_time": 100, "end_time": 400, **scope}
    ) == {"value": 2}
    identities.assert_called_once_with(bk_biz_id=2, **expected)
    query.assert_called_once_with(2, "cpu", HOSTS, 100, 400)


@pytest.mark.parametrize(
    "params",
    [{"start_time": 1}, {"end_time": 1}, {"start_time": 2, "end_time": 1}, {"bk_obj_id": "module"}, {"bk_inst_id": 8}],
)
def test_stats_rejects_incomplete_scope_and_time(params):
    with pytest.raises(InvalidParamsError):
        SearchHostMetricStatsResource.RequestSerializer().validate(params)


def test_stats_resolves_related_space_before_cmdb_and_metrics(mocker):
    validate = mocker.patch("monitor_web.performance.resources.validate_bk_biz_id", return_value=2)
    identities = mocker.patch("monitor_web.performance.resources.api.cmdb.get_host_identities", return_value=HOSTS)
    query = mocker.patch(
        "monitor_web.performance.resources.query_business_host_metric_stats", return_value={"value": 2}
    )
    SearchHostMetricStatsResource().request({"bk_biz_id": -100, "category": "cpu", "start_time": 100, "end_time": 200})
    validate.assert_called_once_with(-100)
    identities.assert_not_called()
    query.assert_called_once_with(2, "cpu", 100, 200)


def test_stats_rejects_arbitrary_metric_category(mocker):
    mocker.patch("monitor_web.performance.resources.validate_bk_biz_id", side_effect=lambda value: value)
    serializer = SearchHostMetricStatsResource.RequestSerializer(data={"bk_biz_id": 2, "category": "arbitrary_promql"})
    assert not serializer.is_valid()


@pytest.mark.parametrize("id_count,ip_count,complete", [(0, 1, False), (1, 0, True)])
def test_duplicate_cmdb_ip_is_unknown_only_for_fallback_identity(mocker, id_count, ip_count, complete):
    make_query(mocker, {"value": 1, "id_count": id_count, "ip_count": ip_count, "duplicates": 0})
    result = stats.query_host_metric_stats(2, "cpu", [{**HOSTS[0], "has_duplicate_ip": True}])
    assert result["complete"] is complete
    assert result["value"] == (1 if complete else None)


def test_stats_rejects_different_business_root():
    with pytest.raises(InvalidParamsError):
        SearchHostMetricStatsResource.RequestSerializer().validate(
            {"bk_biz_id": 2, "bk_obj_id": "biz", "bk_inst_id": 3}
        )
